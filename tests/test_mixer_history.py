"""Undo/redo shortcuts, drag batching and feedback in the mixer console (offline)."""

from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest import mock

from flow8.command_boundary import Flow8CommandError
from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.components.mixer_console import MixerConsole


class _Case(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._cleanup)
        self.fonts = theme.build_fonts(self.root)
        self.service = Flow8Service(auto_connect=False)
        self.messages: list[str] = []
        self.console = MixerConsole(
            self.root, self.fonts, service=self.service, on_feedback=self.messages.append
        )
        self.console.pack(fill="both", expand=True)

    def _cleanup(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def commanded(self, param_id):
        return self.service.state_store.get_parameter(param_id).commanded_value

    def drag(self, strip, widget_attr, handler, values):
        """Press, drag through *values*, release: what the mouse does."""
        strip._begin_gesture(None)
        for value in values:
            handler(str(value))
        getattr(strip, widget_attr)(None)


class UndoRedoKeyTests(_Case):
    def test_bindings_registered_and_removed_with_the_console(self):
        for sequence in ("<Control-z>", "<Control-Z>", "<Control-y>", "<Control-Y>"):
            self.assertTrue(self.root.bind(sequence), sequence)
        self.console.destroy()
        for sequence in ("<Control-z>", "<Control-y>"):
            self.assertEqual(self.root.bind(sequence), "")

    def test_real_key_events_drive_undo_and_redo(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        self.root.deiconify()
        self.root.update()
        self.root.focus_force()
        self.root.update()

        self.root.event_generate("<Control-z>")
        self.root.update()
        self.assertEqual(self.commanded("ch1.fader"), 40)
        self.root.event_generate("<Control-y>")
        self.root.update()
        self.assertEqual(self.commanded("ch1.fader"), 80)
        self.root.event_generate("<Control-z>")
        self.root.update()
        self.root.event_generate("<Control-Shift-Z>")
        self.root.update()
        self.assertEqual(self.commanded("ch1.fader"), 80)

    def test_shift_bit_on_uppercase_z_means_redo(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        self.assertEqual(self.console._on_undo_key(SimpleNamespace(state=0)), "break")
        self.assertEqual(self.commanded("ch1.fader"), 40)
        self.console._on_undo_key(SimpleNamespace(state=0x1))
        self.assertEqual(self.commanded("ch1.fader"), 80)


class UndoRedoBehaviourTests(_Case):
    def test_undo_refreshes_the_strip_without_dispatching(self):
        self.service.set_fader(1, 40)
        self.drag(self.console.strips[1], "_on_fader_release",
                  self.console.strips[1]._on_fader_drag, (50, 70, 90))
        self.assertEqual(self.commanded("ch1.fader"), 90)
        log_before = len(self.service.command_boundary.command_log)

        self.assertTrue(self.console.undo())

        strip = self.console.strips[1]
        self.assertEqual(strip.fader_val.get(), 40)
        self.assertIn("MIDI 40", strip.midi_label_var.get())
        # The replay is exactly one command; repainting the strip sent nothing more.
        self.assertEqual(len(self.service.command_boundary.command_log), log_before + 1)

    def test_drag_gesture_is_a_single_undo_step(self):
        strip = self.console.strips[1]
        self.service.set_fader(1, 40)
        self.drag(strip, "_on_fader_release", strip._on_fader_drag, (50, 60, 70, 90))
        self.service.set_fader(1, 40)  # known start for a second, separate gesture
        self.service.ledger.clear()

        self.drag(strip, "_on_fader_release", strip._on_fader_drag, (20, 30, 85))
        self.assertEqual(len(self.service.ledger.history), 1)
        record = self.service.ledger.history[0]
        self.assertEqual((record.previous_value, record.new_value), (40, 85))

    def test_pan_gesture_is_batched_too(self):
        strip = self.console.strips[2]
        self.service.set_pan(2, 64)
        self.drag(strip, "_on_pan_release", strip._on_pan_drag, (70, 80, 100))
        self.assertEqual(len(self.service.ledger.history), 1)
        self.service.undo()
        self.assertEqual(self.commanded("ch2.pan"), 64)

    def test_feedback_is_truthful_about_command_not_hardware(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        self.console.undo()
        self.console.redo()
        text = " | ".join(self.messages)
        self.assertIn("UNDO COMMANDED — CH 1 FADER MIDI 40", text)
        self.assertIn("REDO COMMANDED — CH 1 FADER MIDI 80", text)
        for forbidden in ("SYNCED", "HARDWARE APPLIED", "HARDWARE CONFIRMED"):
            self.assertNotIn(forbidden, text.upper())

    def test_nothing_to_undo_or_redo_is_reported_and_sends_nothing(self):
        log_before = len(self.service.command_boundary.command_log)
        self.assertFalse(self.console.undo())
        self.assertFalse(self.console.redo())
        self.assertEqual(self.messages, ["NOTHING TO UNDO", "NOTHING TO REDO"])
        self.assertEqual(len(self.service.command_boundary.command_log), log_before)

    def test_failed_undo_says_not_sent_and_keeps_the_step(self):
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        with mock.patch.object(
            self.service.command_boundary, "execute_command",
            side_effect=Flow8CommandError("driver down"),
        ):
            self.assertFalse(self.console.undo())
        self.assertIn("UNDO FAILED — NOT SENT", self.messages[-1])
        self.assertEqual(self.commanded("ch1.fader"), 80)
        self.assertTrue(self.service.ledger.can_undo)

    def test_undo_never_touches_phantom(self):
        self.service.set_phantom(1, True)
        self.service.set_fader(1, 40)
        self.service.set_fader(1, 80)
        entries_before = [e for e in self.service.command_boundary.command_log
                          if e.param_id.endswith(".phantom")]
        self.console.undo()
        self.console.redo()
        entries_after = [e for e in self.service.command_boundary.command_log
                         if e.param_id.endswith(".phantom")]
        self.assertEqual(len(entries_after), len(entries_before))
        self.assertIs(self.commanded("ch1.phantom"), True)

    def test_console_without_a_service_reports_unavailable(self):
        messages: list[str] = []
        console = MixerConsole(self.root, self.fonts, service=None, on_feedback=messages.append)
        self.assertFalse(console.undo())
        self.assertIn("UNAVAILABLE", messages[-1])


class AppFeedbackTests(unittest.TestCase):
    def test_undo_feedback_reaches_the_status_bar(self):
        from flow8.ui.app import Flow8App

        service = Flow8Service(auto_connect=False)
        app = Flow8App(service=service, show_placeholder=False)
        self.addCleanup(app.close)
        service.set_fader(1, 40)
        service.set_fader(1, 80)
        app.root.focus_force()
        app.mixer_console.undo()
        self.assertEqual(
            app.status_bar.feedback_var.get(), "UNDO COMMANDED — CH 1 FADER MIDI 40"
        )


if __name__ == "__main__":
    unittest.main()
