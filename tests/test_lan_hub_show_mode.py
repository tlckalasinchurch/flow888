"""Show Mode over the LAN hub: save, run in safe order, one undo, refusals."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service

FULL_MC = [
    {"parameter": "send_fx1", "channels": [1], "value": 0},
    {"parameter": "mute", "channels": [2, 3, 4, 5, 6], "value": True},
    {"parameter": "mute", "channels": [1], "value": False},
    {"parameter": "fader", "channels": [1], "value": 95},
    {"parameter": "fader", "channels": [7], "value": 30},
]
EXPECTED_ORDER = [
    ("send_fx1", 1), ("mute", 2), ("mute", 3), ("mute", 4), ("mute", 5), ("mute", 6),
    ("mute", 1), ("fader", 1), ("fader", 7),
]


class ShowModeHubTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(Flow8Service, "is_connected", new_callable=mock.PropertyMock,
                                    return_value=True)
        self.connected = patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0,
                               library_path=Path(self.tmp.name) / "lib.json",
                               show_modes_path=Path(self.tmp.name) / "modes.json")

    def act(self, **payload):
        return self.hub.dispatch_action(payload)

    def raw(self, pid):
        return self.service.state_store.get_parameter(pid).commanded_raw_midi

    def save_full_mc(self):
        code, body = self.act(action="saveShowMode", id="mc", steps=FULL_MC)
        self.assertEqual(code, 200, body)

    def test_session_lists_both_modes_not_ready(self):
        snap = self.hub.session_snapshot()
        self.assertEqual([m["id"] for m in snap["showModes"]], ["mc", "band"])
        self.assertTrue(all(not m["ready"] for m in snap["showModes"]))
        self.assertIsNone(snap["showModesError"])

    def test_run_unset_mode_returns_409_and_sends_nothing(self):
        with mock.patch.object(self.service, "_replay") as replay:
            code, body = self.act(action="runShowMode", id="mc")
        self.assertEqual((code, body["code"]), (409, "show_mode_unset"))
        self.assertEqual(body["unsetSteps"], [3, 4])
        replay.assert_not_called()

    def test_run_ready_mode_sends_in_safe_order_and_one_undo(self):
        self.save_full_mc()
        self.act(action="setFader", channel=1, value=10)
        self.act(action="setFader", channel=7, value=11)
        self.act(action="setMute", channel=1, value=True)
        self.act(action="setFader", channel=8, value=77)
        self.act(action="setMute", channel=2, value=False)
        before_untouched = self.raw("ch3.fader")

        with mock.patch.object(self.service, "_replay", wraps=self.service._replay) as spy:
            code, body = self.act(action="runShowMode", id="mc")
        self.assertEqual(code, 200, body)
        order = [(c.args[0], c.args[1]) for c in spy.call_args_list]
        # Every cut-down change reaches the sender before any raise or unmute.
        self.assertEqual(order[:len(EXPECTED_ORDER)], EXPECTED_ORDER)
        self.assertEqual(self.raw("ch1.fader"), 95)
        self.assertEqual(self.raw("ch7.fader"), 30)
        self.assertEqual(self.raw("main.fader"), 77)       # not listed: untouched
        self.assertEqual(self.raw("ch3.fader"), before_untouched)

        self.assertEqual(self.act(action="undo")[0], 200)
        self.assertEqual(self.raw("ch1.fader"), 10)
        self.assertEqual(self.raw("ch7.fader"), 11)
        self.assertEqual(self.raw("ch1.mute"), 127)
        self.assertEqual(self.raw("ch2.mute"), 0)

    def test_unknown_before_is_reported(self):
        self.save_full_mc()
        code, body = self.act(action="runShowMode", id="mc")
        self.assertEqual(code, 200, body)
        self.assertEqual(body["applied"], 9)
        self.assertEqual(body["unknownBefore"], 9)

    def test_second_run_is_all_skipped(self):
        self.save_full_mc()
        self.assertEqual(self.act(action="runShowMode", id="mc")[0], 200)
        code, body = self.act(action="runShowMode", id="mc")
        self.assertEqual(code, 200, body)
        self.assertEqual((body["applied"], body["skipped"]), (0, 9))

    def test_control_closed_refuses_run_but_allows_save(self):
        self.save_full_mc()
        self.connected.return_value = False
        with mock.patch.object(self.service, "_replay") as replay:
            code, _ = self.act(action="runShowMode", id="mc")
            self.assertEqual(code, 503)
            replay.assert_not_called()
        self.assertEqual(self.act(action="saveShowMode", id="band", steps=[
            {"parameter": "fader", "channels": [7], "value": 20}])[0], 200)

    def test_boundary_failure_rolls_back_and_errors(self):
        self.save_full_mc()
        for p in (dict(action="setFader", channel=1, value=10), dict(action="setFader", channel=7, value=11),
                  dict(action="setMute", channel=1, value=True), dict(action="setSend", channel=1, target="fx1", value=50),
                  *[dict(action="setMute", channel=c, value=False) for c in range(2, 7)]):
            self.assertEqual(self.act(**p)[0], 200)
        real = self.service._replay
        calls = []

        def flaky(parameter, channel, value):
            calls.append((parameter, channel))
            if len(calls) == 3:
                raise RuntimeError("boundary said no")
            return real(parameter, channel, value)

        with mock.patch.object(self.service, "_replay", side_effect=flaky):
            code, body = self.act(action="runShowMode", id="mc")
        self.assertEqual(code, 409, body)
        self.assertIn("error", body)
        self.assertEqual(self.raw("ch1.send_fx1"), 50)   # first two changes put back
        self.assertEqual(self.raw("ch2.mute"), 0)
        self.assertEqual(self.raw("ch1.fader"), 10)

    def test_save_rejects_gain_phantom_and_main_with_400(self):
        for steps in ([{"parameter": "gain", "channels": [1], "value": 5}],
                      [{"parameter": "phantom", "channels": [1], "value": True}],
                      [{"parameter": "fader", "channels": [8], "value": 5}]):
            with self.subTest(steps):
                code, body = self.act(action="saveShowMode", id="mc", steps=steps)
                self.assertEqual((code, body["ok"]), (400, False))
        self.assertFalse(self.hub.show_modes.summaries()[0]["ready"])


class ShowModeConcurrencyAndRollbackTests(ShowModeHubTests):
    BAND = [
        {"parameter": "fader", "channels": [7], "value": 20},
        {"parameter": "mute", "channels": [2, 3], "value": False},
    ]

    def test_two_clients_running_the_same_mode_apply_once(self):
        self.assertEqual(self.act(action="saveShowMode", id="band", steps=self.BAND)[0], 200)
        real_stage = self.service.stage_change_plan

        def slow_stage(plan):
            out = real_stage(plan)
            time.sleep(0.15)  # widen the stage-to-commit window
            return out

        barrier = threading.Barrier(2)
        results = []

        def client():
            barrier.wait()
            results.append(self.act(action="runShowMode", id="band"))

        with mock.patch.object(self.service, "stage_change_plan", side_effect=slow_stage):
            threads = [threading.Thread(target=client) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertEqual([code for code, _ in results], [200, 200], results)
        self.assertEqual(sorted(body["applied"] for _, body in results), [0, 3])

    def test_failed_run_with_unknown_before_values_says_rollback_was_incomplete(self):
        self.save_full_mc()
        real = self.service._replay
        calls = []

        def flaky(parameter, channel, value):
            calls.append(parameter)
            if len(calls) == 3:
                raise RuntimeError("boundary said no")
            return real(parameter, channel, value)

        with mock.patch.object(self.service, "_replay", side_effect=flaky):
            code, body = self.act(action="runShowMode", id="mc")
        self.assertEqual(code, 409, body)
        self.assertFalse(body["rolledBack"])
        self.assertIn("could not be restored", body["error"])


if __name__ == "__main__":
    unittest.main()
