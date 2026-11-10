"""Undo/redo ledger and scene snapshots wired into Flow8Service (offline only).

A real ``Flow8Service(auto_connect=False)`` is used, so every command, replay
and scene dispatch passes through the real command boundary and ends as
``ACCEPTED_OFFLINE``. No MIDI port is opened.
"""

from __future__ import annotations

import unittest
from unittest import mock

from flow8.command_boundary import Flow8CommandError
from flow8.service import LEDGER_CAPACITY, SCENE_CAPACITY, Flow8Service


def _seed(service: Flow8Service) -> None:
    """Command every reversible parameter once so each has a known value."""
    for channel in range(1, 8):
        service.set_fader(channel, 50 + channel)
        service.set_pan(channel, 60 + channel)
        service.set_mute(channel, False)
    service.set_fader(8, 90)
    service.set_pan(8, 64)
    service.ledger.clear()


def _commanded(service: Flow8Service, param_id: str):
    return service.state_store.get_parameter(param_id).commanded_value


class LedgerWiringTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def test_capacities(self):
        self.assertEqual(self.service.ledger.capacity, LEDGER_CAPACITY)
        self.assertEqual(LEDGER_CAPACITY, 50)
        self.assertEqual(self.service.scenes.max_snapshots, SCENE_CAPACITY)
        self.assertEqual(SCENE_CAPACITY, 8)

    def test_change_from_unknown_start_value_is_not_recorded(self):
        # Nothing commanded or observed yet: the state store holds only an app
        # default, which must never become an undo target.
        self.service.set_fader(1, 80)
        self.assertEqual(self.service.ledger.history, ())
        self.assertEqual(self.service.undo(), ())

    def test_undo_and_redo_replay_through_the_command_boundary(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        log_before = len(self.service.command_boundary.command_log)

        undone = self.service.undo()
        self.assertEqual([(r.parameter_type, r.channel_index) for r in undone], [("fader", 1)])
        self.assertEqual(_commanded(self.service, "ch1.fader"), 40)
        log = self.service.command_boundary.command_log
        self.assertEqual(len(log), log_before + 1)
        self.assertEqual((log[-1].param_id, log[-1].target_value), ("ch1.fader", 40))

        self.assertEqual(len(self.service.redo()), 1)
        self.assertEqual(_commanded(self.service, "ch1.fader"), 80)

    def test_replay_is_not_recorded_as_a_new_step(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        self.service.undo()
        self.assertEqual(len(self.service.ledger.history), 0)
        self.assertEqual(len(self.service.ledger.redo_history), 1)
        self.service.redo()
        self.assertEqual(len(self.service.ledger.history), 1)
        self.assertEqual(len(self.service.ledger.redo_history), 0)

    def test_new_command_clears_redo(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        self.service.undo()
        self.service.set_fader(1, 10)
        self.assertEqual(self.service.redo(), ())

    def test_drag_is_one_undoable_transition_from_start_to_release(self):
        self.service.set_fader(1, 40)
        self.service.begin_batch()
        for value in (45, 52, 60, 77):
            self.service.set_fader(1, value)
        self.assertEqual(self.service.end_batch(), 1)

        self.assertEqual(len(self.service.ledger.history), 1)
        record = self.service.ledger.history[0]
        self.assertEqual((record.previous_value, record.new_value), (40, 77))
        self.service.undo()
        self.assertEqual(_commanded(self.service, "ch1.fader"), 40)

    def test_mute_and_main_pan_are_recorded_and_undone(self):
        _seed(self.service)
        self.service.set_mute(2, True)
        self.service.set_pan(8, 100)
        self.service.undo()
        self.assertEqual(_commanded(self.service, "main.balance"), 64)
        self.service.undo()
        self.assertIs(_commanded(self.service, "ch2.mute"), False)

    def test_rejected_command_is_not_recorded(self):
        self.service.set_fader(1, 40)
        with mock.patch.object(
            self.service.command_boundary, "execute_command",
            side_effect=Flow8CommandError("driver down"),
        ):
            with self.assertRaises(Flow8CommandError):
                self.service.set_fader(1, 80)
        self.assertEqual(self.service.ledger.history, ())

    def test_failed_undo_keeps_the_step_available(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        with mock.patch.object(
            self.service.command_boundary, "execute_command",
            side_effect=Flow8CommandError("driver down"),
        ):
            with self.assertRaises(Flow8CommandError):
                self.service.undo()
        self.assertTrue(self.service.ledger.can_undo)
        self.assertEqual(_commanded(self.service, "ch1.fader"), 80)
        self.service.undo()
        self.assertEqual(_commanded(self.service, "ch1.fader"), 40)


class PhantomIsolationTests(unittest.TestCase):
    """+48V must be unreachable from the ledger and from scenes."""

    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def _phantom_entries(self):
        return [e for e in self.service.command_boundary.command_log
                if e.param_id.endswith(".phantom")]

    def test_set_phantom_is_never_recorded(self):
        self.service.set_phantom(1, True)
        self.service.set_phantom(1, False)
        self.service.set_phantom(2, True)
        self.assertEqual(self.service.ledger.history, ())
        self.assertFalse(self.service.ledger.can_undo)

    def test_undo_and_redo_never_touch_phantom(self):
        _seed(self.service)
        self.service.set_phantom(1, True)
        before = len(self._phantom_entries())
        self.service.set_fader(1, 10)
        self.service.set_mute(1, True)
        with mock.patch.object(
            self.service, "set_phantom", wraps=self.service.set_phantom
        ) as spy:
            self.service.undo()
            self.service.undo()
            self.service.redo()
        spy.assert_not_called()
        self.assertEqual(len(self._phantom_entries()), before)
        self.assertIs(_commanded(self.service, "ch1.phantom"), True)

    def test_phantom_commands_cannot_be_forced_into_the_ledger(self):
        record = self.service.ledger.make_record("phantom_power", 1, False, True)
        self.assertFalse(self.service.ledger.push(record))
        with self.assertRaises(ValueError):
            self.service._replay("phantom_power", 1, True)

    def test_scenes_never_store_or_recall_phantom(self):
        _seed(self.service)
        self.service.set_phantom(1, True)
        scene = self.service.capture_scene("A")
        for values in scene.parameters.values():
            self.assertLessEqual(set(values), {"fader", "pan", "mute"})
        self.service.set_phantom(1, False)
        before = len(self._phantom_entries())
        with mock.patch.object(
            self.service, "set_phantom", wraps=self.service.set_phantom
        ) as spy:
            self.service.recall_scene("A")
        spy.assert_not_called()
        self.assertEqual(len(self._phantom_entries()), before)
        self.assertIs(_commanded(self.service, "ch1.phantom"), False)


class SceneWiringTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def test_capture_with_nothing_known_stores_nothing(self):
        with self.assertRaises(ValueError):
            self.service.capture_scene("Empty")
        self.assertEqual(self.service.scenes.names(), ())

    def test_capture_covers_inputs_and_main_without_guessing(self):
        self.service.set_fader(1, 70)
        scene = self.service.capture_scene("Partial")
        self.assertEqual(scene.parameters, {1: {"fader": 70}})

        _seed(self.service)
        scene = self.service.capture_scene("Full")
        self.assertEqual(sorted(scene.parameters), list(range(1, 9)))
        self.assertEqual(set(scene.parameters[1]), {"fader", "pan", "mute"})
        self.assertEqual(set(scene.parameters[8]), {"fader", "pan"})

    def test_recall_dispatches_through_the_boundary_and_restores_values(self):
        _seed(self.service)
        self.service.capture_scene("Show")
        for channel in range(1, 8):
            self.service.set_fader(channel, 5)
            self.service.set_mute(channel, True)
        self.service.set_fader(8, 5)
        log_before = len(self.service.command_boundary.command_log)

        result = self.service.recall_scene("Show")

        self.assertEqual(result.failed, [])
        self.assertEqual(result.applied, 7 * 3 + 2)
        self.assertEqual(len(self.service.command_boundary.command_log), log_before + result.applied)
        for channel in range(1, 8):
            self.assertEqual(_commanded(self.service, f"ch{channel}.fader"), 50 + channel)
            self.assertIs(_commanded(self.service, f"ch{channel}.mute"), False)
        self.assertEqual(_commanded(self.service, "main.fader"), 90)

    def test_recall_is_one_undo_step(self):
        _seed(self.service)
        self.service.capture_scene("Show")
        self.service.set_fader(1, 5)
        self.service.set_fader(2, 6)
        self.service.ledger.clear()
        self.service.recall_scene("Show")
        self.assertGreater(len(self.service.undo()), 1)
        self.assertFalse(self.service.ledger.can_undo)
        self.assertEqual(_commanded(self.service, "ch1.fader"), 5)
        self.assertEqual(_commanded(self.service, "ch2.fader"), 6)

    def test_recall_reports_rejected_commands_and_continues(self):
        _seed(self.service)
        self.service.capture_scene("Show")
        real = self.service.command_boundary.execute_command

        def flaky(param_id, *args, **kwargs):
            if param_id == "ch3.fader":
                raise Flow8CommandError("driver down")
            return real(param_id, *args, **kwargs)

        with mock.patch.object(self.service.command_boundary, "execute_command", side_effect=flaky):
            result = self.service.recall_scene("Show")
        self.assertEqual([(c, p) for c, p, _ in result.failed], [(3, "fader")])
        self.assertEqual(result.applied, 7 * 3 + 2 - 1)

    def test_unknown_scene_and_bounded_scene_count(self):
        with self.assertRaises(KeyError):
            self.service.recall_scene("nope")
        self.service.set_fader(1, 70)
        for index in range(SCENE_CAPACITY + 2):
            self.service.capture_scene(f"S{index}")
        self.assertEqual(len(self.service.scenes.names()), SCENE_CAPACITY)
        self.assertNotIn("S0", self.service.scenes.names())


if __name__ == "__main__":
    unittest.main()
