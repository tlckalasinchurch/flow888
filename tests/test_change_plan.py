"""F7 staged change plan: validation, honest preview, one-step commit, rollback."""

from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request
from unittest import mock

from flow8.change_plan import ChangePlanError, make_plan
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service


def plan_for(*changes, title="Test plan"):
    return make_plan(title, list(changes))


class PlanValidationTests(unittest.TestCase):
    def test_level_parameters_are_never_accepted(self):
        for parameter, value in (("gain", 70), ("phantom", True)):
            with self.subTest(parameter=parameter):
                with self.assertRaises(ChangePlanError) as ctx:
                    plan_for({"channel": 1, "parameter": parameter, "value": value})
                self.assertIn("never part of a plan", str(ctx.exception))

    def test_parameter_must_exist_on_that_channel(self):
        for change in (
            {"channel": 5, "parameter": "compressor", "value": 20},
            {"channel": 6, "parameter": "low_cut", "value": 40},
            {"channel": "mon1", "parameter": "pan", "value": 64},
            {"channel": 8, "parameter": "mute", "value": True},
            {"channel": 9, "parameter": "fader", "value": 10},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ChangePlanError):
                    plan_for(change)

    def test_verified_addresses_are_accepted(self):
        plan = plan_for(
            {"channel": 1, "parameter": "eq_low", "value": 51, "reason": "cut mud", "risk": "medium"},
            {"channel": 8, "parameter": "pan", "value": 70},
            {"channel": "mon1", "parameter": "fader", "value": 100},
            {"channel": 2, "parameter": "mute", "value": True},
        )
        self.assertEqual(len(plan.changes), 4)
        self.assertEqual(plan.changes[0].parameter_id, "ch1.eq_low")
        self.assertEqual(plan.changes[1].parameter_id, "main.balance")
        self.assertEqual(plan.changes[2].parameter_id, "mon1.fader")

    def test_values_and_duplicates_are_validated(self):
        with self.assertRaises(ChangePlanError):
            plan_for({"channel": 1, "parameter": "fader", "value": 128})
        with self.assertRaises(ChangePlanError):
            plan_for({"channel": 1, "parameter": "fader", "value": True})
        with self.assertRaises(ChangePlanError):
            plan_for({"channel": 1, "parameter": "mute", "value": 1})
        with self.assertRaises(ChangePlanError):
            plan_for({"channel": 1, "parameter": "fader", "value": 1, "risk": "extreme"})
        with self.assertRaises(ChangePlanError):
            plan_for(
                {"channel": 1, "parameter": "eq_low", "value": 50},
                {"channel": 1, "parameter": "eq_low", "value": 60},
            )
        with self.assertRaises(ChangePlanError):
            make_plan("Empty", [])


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def test_preview_sends_nothing_and_flags_unknown_current_values(self):
        plan = plan_for({"channel": 1, "parameter": "eq_low", "value": 51})
        rows = self.service.preview_change_plan(plan)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row.from_value)
        self.assertEqual(row.from_provenance, "UNSYNCED")
        self.assertEqual(row.status, "change")
        self.assertIn("undo cannot restore", row.note)
        self.assertEqual(self.service.command_boundary.command_log, [])
        self.assertIsNone(
            self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi
        )

    def test_preview_reports_current_value_and_no_change(self):
        self.service.set_eq_band(1, "low", -3.0, unit="dB")  # raw 51
        self.service.set_eq_band(1, "hi", 0.0, unit="dB")     # raw 64
        rows = self.service.preview_change_plan(
            plan_for(
                {"channel": 1, "parameter": "eq_low", "value": 51},
                {"channel": 1, "parameter": "eq_hi", "value": 70},
            )
        )
        self.assertEqual(rows[0].status, "no_change")
        self.assertEqual(rows[0].from_value, 51)
        self.assertEqual(rows[0].from_provenance, "COMMANDED")
        self.assertIn("nothing would be sent", rows[0].note)
        self.assertEqual(rows[1].status, "change")
        self.assertEqual(rows[1].from_value, 64)


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def _known_baseline(self):
        self.service.set_eq_band(1, "low", -3.0, unit="dB")   # raw 51
        self.service.set_fader(1, 80)
        self.service.set_send(1, "fx1", 30)
        self.service.ledger.clear()

    def test_commit_is_one_undo_step_and_restores_every_value(self):
        self._known_baseline()
        result = self.service.commit_change_plan(
            plan_for(
                {"channel": 1, "parameter": "eq_low", "value": 70, "reason": "add presence"},
                {"channel": 1, "parameter": "send_fx1", "value": 76, "reason": "a little reverb"},
            )
        )
        self.assertEqual(result.applied, 2)
        self.assertEqual(result.skipped, 0)
        self.assertFalse(result.rolled_back)
        self.assertTrue(result.undo_ready)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 70)
        self.assertEqual(self.service.state_store.get_parameter("ch1.send_fx1").commanded_raw_midi, 76)

        undone = self.service.undo()
        self.assertEqual(len(undone), 2, "the plan must undo as one step")
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 51)
        self.assertEqual(self.service.state_store.get_parameter("ch1.send_fx1").commanded_raw_midi, 30)
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi, 80)
        self.assertFalse(self.service.ledger.can_undo)

    def test_commit_captures_the_mix_before_the_change(self):
        self._known_baseline()
        result = self.service.commit_change_plan(
            plan_for({"channel": 1, "parameter": "eq_low", "value": 70}, title="Presence")
        )
        snapshot = self.service.pre_change_snapshot
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.name, "BEFORE Presence")
        self.assertEqual(snapshot.parameters[1]["eq_low"], 51)
        self.assertEqual(snapshot.parameters[1]["fader"], 80)
        self.assertNotIn("gain", snapshot.parameters[1])
        self.assertNotIn("phantom", snapshot.parameters[1])

        recall = self.service.restore_pre_change()
        self.assertGreaterEqual(recall.applied, 1)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 51)

    def test_noop_plan_sends_nothing_and_stores_no_snapshot(self):
        self._known_baseline()
        before = self.service.command_boundary.command_log
        result = self.service.commit_change_plan(
            plan_for({"channel": 1, "parameter": "eq_low", "value": 51})
        )
        self.assertEqual(result.applied, 0)
        self.assertEqual(result.skipped, 1)
        self.assertIsNone(result.snapshot_label)
        self.assertIsNone(self.service.pre_change_snapshot)
        self.assertFalse(self.service.ledger.can_undo)
        self.assertEqual(len(self.service.command_boundary.command_log), len(before))

    def test_preview_guard_blocks_a_commit_after_the_value_moved(self):
        self._known_baseline()   # ch1 eq_low = raw 51
        plan = plan_for({"channel": 1, "parameter": "eq_low", "value": 70})
        rows, guard = self.service.stage_change_plan(plan)
        self.assertEqual(rows[0].from_value, 51)

        # Any later change counts, whichever surface made it.
        self.service.set_eq_band(1, "low", 60, unit="raw")
        self.service.ledger.clear()   # isolate the commit's effect from the baseline edit
        result = self.service.commit_change_plan(plan, guard=guard, require_guard=True)

        self.assertTrue(result.stale)
        self.assertEqual(result.applied, 0)
        self.assertEqual(result.stale_rows[0]["parameterId"], "ch1.eq_low")
        self.assertEqual(result.stale_rows[0]["currentFrom"], 60)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 60)
        self.assertFalse(self.service.ledger.can_undo, "a stale plan must send nothing")

    def test_a_fresh_guard_still_commits(self):
        self._known_baseline()
        plan = plan_for({"channel": 1, "parameter": "eq_low", "value": 70})
        _rows, guard = self.service.stage_change_plan(plan)
        result = self.service.commit_change_plan(plan, guard=guard, require_guard=True)
        self.assertFalse(result.stale)
        self.assertEqual(result.applied, 1)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 70)

    def test_a_guard_without_a_preview_is_refused(self):
        from flow8.change_plan import PreviewRequiredError

        plan = plan_for({"channel": 1, "parameter": "eq_low", "value": 70})
        with self.assertRaises(PreviewRequiredError):
            self.service.commit_change_plan(plan, require_guard=True)

    def test_a_guard_does_not_authorise_a_different_plan(self):
        self._known_baseline()
        plan = plan_for({"channel": 1, "parameter": "eq_low", "value": 70})
        _rows, guard = self.service.stage_change_plan(plan)
        other = plan_for({"channel": 1, "parameter": "eq_low", "value": 71})
        result = self.service.commit_change_plan(other, guard=guard)
        self.assertTrue(result.stale)
        self.assertEqual(result.applied, 0)

    def test_failed_dispatch_rolls_back_and_leaves_no_undo_step(self):
        self._known_baseline()
        real_set_send = self.service.set_send

        def failing_send(channel_index, target, value, unit="raw"):
            if target == "fx2":
                raise RuntimeError("simulated dispatch failure")
            return real_set_send(channel_index, target, value, unit=unit)

        with mock.patch.object(self.service, "set_send", side_effect=failing_send):
            result = self.service.commit_change_plan(
                plan_for(
                    {"channel": 1, "parameter": "eq_low", "value": 70},
                    {"channel": 1, "parameter": "send_fx2", "value": 40},
                )
            )

        self.assertTrue(result.rolled_back)
        self.assertEqual(result.applied, 0)
        self.assertIn("simulated dispatch failure", result.error)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 51)
        self.assertFalse(self.service.ledger.can_undo)

    def test_mute_plan_applies_and_undoes(self):
        self.service.set_mute(2, False)
        self.service.ledger.clear()
        result = self.service.commit_change_plan(
            plan_for({"channel": 2, "parameter": "mute", "value": True})
        )
        self.assertEqual(result.applied, 1)
        self.assertIs(self.service.state_store.get_parameter("ch2.mute").commanded_value, True)
        self.service.undo()
        self.assertIs(self.service.state_store.get_parameter("ch2.mute").commanded_value, False)


class _HubCase(unittest.TestCase):
    connected = True

    def setUp(self):
        patcher = mock.patch.object(
            Flow8Service, "is_connected",
            new_callable=mock.PropertyMock, return_value=self.connected,
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


class HubChangePlanTests(_HubCase):
    def test_preview_returns_rows_and_sends_nothing(self):
        code, res = self.post({
            "action": "previewChangePlan",
            "title": "Review",
            "changes": [{"channel": 1, "parameter": "eq_low", "value": 70, "reason": "presence"}],
        })
        self.assertEqual(code, 200, res)
        self.assertEqual(res["willSend"], 1)
        self.assertEqual(res["rows"][0]["fromProvenance"], "UNSYNCED")
        self.assertEqual(self.service.command_boundary.command_log, [])

    def test_gain_in_a_plan_is_rejected_with_403(self):
        code, res = self.post({
            "action": "commitChangePlan",
            "changes": [{"channel": 1, "parameter": "gain", "value": 90}],
        })
        self.assertEqual(code, 403)
        self.assertFalse(res["ok"])

    def test_commit_applies_plan(self):
        # Give the parameter a known value first: undo never invents a previous value.
        code, _ = self.post({"action": "setEqBand", "channel": 1, "band": "low", "value": 51})
        self.assertEqual(code, 200)
        changes = [{"channel": 1, "parameter": "eq_low", "value": 70}]
        code, preview = self.post({"action": "previewChangePlan", "title": "Presence", "changes": changes})
        self.assertEqual(code, 200, preview)
        code, res = self.post({
            "action": "commitChangePlan", "title": "Presence",
            "changes": changes, "guard": preview["guard"],
        })
        self.assertEqual(code, 200, res)
        self.assertEqual(res["applied"], 1)
        self.assertTrue(res["undoReady"])
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 70)

    def test_malformed_plan_is_a_400(self):
        code, res = self.post({"action": "previewChangePlan", "changes": []})
        self.assertEqual(code, 400)
        self.assertFalse(res["ok"])

    def test_commit_without_a_preview_is_refused(self):
        code, res = self.post({
            "action": "commitChangePlan",
            "changes": [{"channel": 1, "parameter": "eq_low", "value": 70}],
        })
        self.assertEqual(code, 409, res)
        self.assertEqual(res["code"], "preview_required")
        self.assertNotEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 70)

    def test_telemetry_after_preview_makes_the_plan_stale(self):
        self.post({"action": "setEqBand", "channel": 1, "band": "low", "value": 51})
        self.service.ledger.clear()
        changes = [{"channel": 1, "parameter": "eq_low", "value": 70}]
        code, preview = self.post({"action": "previewChangePlan", "changes": changes})
        self.assertEqual(code, 200, preview)

        # The engineer moves that EQ band on the mixer: inbound telemetry changes
        # the value the preview was based on.
        self.service._on_midi_in_event(
            {"status": 0xB0, "channel": 1, "command": 0xB0, "data1": 1, "data2": 60}
        )
        code, res = self.post({
            "action": "commitChangePlan",
            "changes": changes, "guard": preview["guard"],
        })
        self.assertEqual(code, 409, res)
        self.assertEqual(res["code"], "stale_plan")
        self.assertEqual(res["staleParameters"][0]["parameterId"], "ch1.eq_low")
        self.assertEqual(res["staleParameters"][0]["currentFrom"], 60)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").observed_raw_midi, 60)
        self.assertFalse(self.service.ledger.can_undo, "a stale plan must send nothing")

    def test_expired_guard_requires_a_new_preview(self):
        changes = [{"channel": 1, "parameter": "eq_low", "value": 70}]
        code, preview = self.post({"action": "previewChangePlan", "changes": changes})
        self.assertEqual(code, 200, preview)
        self.service._previews[preview["guard"]]["at"] -= 10_000
        code, res = self.post({
            "action": "commitChangePlan", "changes": changes, "guard": preview["guard"],
        })
        self.assertEqual(code, 409, res)
        self.assertEqual(res["code"], "preview_required")


class OfflineHubChangePlanTests(_HubCase):
    connected = False

    def test_commit_is_rejected_while_offline(self):
        code, res = self.post({
            "action": "commitChangePlan",
            "changes": [{"channel": 1, "parameter": "eq_low", "value": 70}],
        })
        self.assertEqual(code, 503)
        self.assertEqual(res["code"], "not_connected")

    def test_preview_stays_allowed_while_offline(self):
        code, res = self.post({
            "action": "previewChangePlan",
            "changes": [{"channel": 1, "parameter": "eq_low", "value": 70}],
        })
        self.assertEqual(code, 200, res)


class WebConsoleContractTests(unittest.TestCase):
    """The review panel is the only way FlowAi applies a suggestion."""

    def setUp(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        self.html = (root / "flow8" / "web_ui" / "index.html").read_text(encoding="utf-8")
        self.js = (root / "flow8" / "web_ui" / "app.js").read_text(encoding="utf-8")

    def test_review_panel_exists_with_commit_and_discard(self):
        for element_id in ("plan-panel", "plan-body", "plan-commit", "plan-discard", "plan-title"):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_console_calls_preview_then_commit(self):
        self.assertIn("action: 'previewChangePlan'", self.js)
        self.assertIn("action: 'commitChangePlan'", self.js)
        self.assertIn("previewPlan(", self.js)
        # A FlowAi card may propose changes but must not post a command itself.
        self.assertNotIn("FlowAi applied to CH", self.js)


if __name__ == "__main__":
    unittest.main()