"""Coalesced drag gestures: one pointer drag becomes one undo step."""

from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request
from unittest import mock

from flow8.lan_hub import GESTURE_MAX_S, Flow8LanHub
from flow8.service import Flow8Service


class _HubCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            Flow8Service, "is_connected",
            new_callable=mock.PropertyMock, return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def post(self, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            try:
                return err.code, json.loads(err.read().decode("utf-8"))
            finally:
                err.close()

    def raw(self, param_id: str):
        return self.service.state_store.get_parameter(param_id).commanded_raw_midi


class FaderGestureTests(_HubCase):
    def test_a_drag_is_one_undo_step_from_start_to_release(self):
        self.post({"action": "setFader", "channel": 1, "value": 80})
        self.service.ledger.clear()

        self.assertEqual(self.post({"action": "beginGesture", "clientId": "a"})[0], 200)
        for value in (82, 85, 88, 90):
            self.assertEqual(self.post({"action": "setFader", "channel": 1, "value": value})[0], 200)
        code, res = self.post({"action": "endGesture", "clientId": "a"})

        self.assertEqual(code, 200)
        self.assertEqual(res["steps"], 1)
        self.assertEqual(len(self.service.ledger.history), 1)
        record = self.service.ledger.history[0]
        self.assertEqual((record.previous_value, record.new_value), (80, 90))

        self.service.undo()
        self.assertEqual(self.raw("ch1.fader"), 80)
        self.assertFalse(self.service.ledger.can_undo)

    def test_eq_knob_drag_coalesces_to_one_step(self):
        self.post({"action": "setEqBand", "channel": 2, "band": "hi_mid", "value": 64})
        self.service.ledger.clear()
        self.post({"action": "beginGesture", "clientId": "a"})
        for value in (70, 72, 75):
            self.post({"action": "setEqBand", "channel": 2, "band": "hi_mid", "value": value})
        _, res = self.post({"action": "endGesture", "clientId": "a"})
        self.assertEqual(res["steps"], 1)
        self.assertEqual(len(self.service.ledger.history), 1)
        self.service.undo()
        self.assertEqual(self.raw("ch2.eq_hi_mid"), 64)

    def test_commands_outside_a_gesture_are_separate_steps(self):
        self.post({"action": "setFader", "channel": 1, "value": 68})
        self.service.ledger.clear()
        self.post({"action": "setFader", "channel": 1, "value": 70})
        self.post({"action": "setFader", "channel": 1, "value": 71})
        self.assertEqual(len(self.service.ledger.history), 2)

    def test_end_without_begin_is_harmless(self):
        code, res = self.post({"action": "endGesture"})
        self.assertEqual(code, 200)
        self.assertEqual(res["steps"], 0)

    def test_stale_gesture_is_closed_before_the_next_command(self):
        self.post({"action": "setFader", "channel": 1, "value": 60})
        self.post({"action": "setFader", "channel": 3, "value": 40})
        self.service.ledger.clear()
        self.post({"action": "beginGesture", "clientId": "a"})
        self.post({"action": "setFader", "channel": 1, "value": 61})
        # Pretend the pointer never lifted.
        self.hub._gesture_started -= (GESTURE_MAX_S + 5)

        self.post({"action": "setFader", "channel": 3, "value": 41})
        self.assertEqual(len(self.service.ledger.history), 2, "old batch closed, new command separate")
        self.assertEqual(self.raw("ch1.fader"), 61)


if __name__ == "__main__":
    unittest.main()
