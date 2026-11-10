"""Scene snapshot bar in the mixer console (UI.2-T5). Offline: no MIDI port is opened."""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest import mock

from flow8.command_boundary import Flow8CommandError
from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.app import Flow8App
from flow8.ui.components import widget_texts
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
        self.bar = self.console.scene_bar

    def _cleanup(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def commanded(self, param_id):
        return self.service.state_store.get_parameter(param_id).commanded_value

    def seed(self):
        for channel in range(1, 8):
            self.service.set_fader(channel, 50 + channel)
            self.service.set_pan(channel, 60 + channel)
            self.service.set_mute(channel, False)
        self.service.set_fader(8, 90)
        self.service.set_pan(8, 64)

    def phantom_entries(self):
        return [e for e in self.service.command_boundary.command_log
                if e.param_id.endswith(".phantom")]


class SlotStateTests(_Case):
    def test_eight_slots_start_empty_and_recall_is_disabled(self):
        self.assertEqual(sorted(self.bar.slot_buttons), list(range(1, 9)))
        for slot, button in self.bar.slot_buttons.items():
            self.assertFalse(self.bar.slot_populated(slot))
            self.assertEqual(button.cget("text"), f"{slot}○")
        self.assertEqual(str(self.bar.capture_button.cget("state")), "normal")
        self.assertEqual(str(self.bar.recall_button.cget("state")), "disabled")

    def test_selecting_a_slot_highlights_only_that_slot(self):
        colors = theme.COLORS
        self.bar.slot_buttons[4].invoke()
        self.assertEqual(self.bar.selected_slot, 4)
        for slot, button in self.bar.slot_buttons.items():
            expected = colors["cyan"] if slot == 4 else colors["border"]
            self.assertEqual(str(button.cget("highlightbackground")), expected, slot)

    def test_a_scene_captured_through_the_api_shows_as_populated_at_startup(self):
        self.service.set_fader(1, 70)
        self.service.capture_scene("SCENE 2")
        console = MixerConsole(self.root, self.fonts, service=self.service)
        self.assertTrue(console.scene_bar.slot_populated(2))
        self.assertEqual(console.scene_bar.slot_buttons[2].cget("text"), "2●")
        self.assertFalse(console.scene_bar.slot_populated(1))

    def test_console_without_a_service_disables_the_bar(self):
        console = MixerConsole(self.root, self.fonts, service=None)
        self.assertEqual(str(console.scene_bar.capture_button.cget("state")), "disabled")
        for button in console.scene_bar.slot_buttons.values():
            self.assertEqual(str(button.cget("state")), "disabled")


class CaptureTests(_Case):
    def test_capture_with_nothing_known_is_rejected_truthfully(self):
        with mock.patch.object(self.service, "capture_scene", wraps=self.service.capture_scene) as spy:
            self.bar.capture_button.invoke()
        spy.assert_called_once_with("SCENE 1")
        self.assertEqual(self.messages, ["SCENE CAPTURE REJECTED — NO KNOWN PARAMETERS"])
        self.assertEqual(self.service.scenes.names(), ())
        self.assertFalse(self.bar.slot_populated(1))
        self.assertEqual(str(self.bar.recall_button.cget("state")), "disabled")

    def test_capture_stores_known_values_and_marks_the_slot(self):
        self.seed()
        self.bar.slot_buttons[3].invoke()
        with mock.patch.object(self.service, "capture_scene", wraps=self.service.capture_scene) as spy:
            self.bar.capture_button.invoke()
        spy.assert_called_once_with("SCENE 3")

        self.assertEqual(self.service.scenes.names(), ("SCENE 3",))
        self.assertTrue(self.bar.slot_populated(3))
        self.assertEqual(self.bar.slot_buttons[3].cget("text"), "3●")
        self.assertFalse(self.bar.slot_populated(1))
        self.assertEqual(self.messages[-1], "SCENE CAPTURED — SCENE 3 · 23 VALUES")  # 7x3 + main x2
        self.assertEqual(str(self.bar.recall_button.cget("state")), "normal")

    def test_capturing_into_a_saved_slot_says_it_overwrote(self):
        self.seed()
        self.bar.capture_button.invoke()
        self.bar.capture_button.invoke()
        self.assertTrue(self.messages[-1].startswith("SCENE OVERWRITTEN — SCENE 1"))

    def test_only_known_parameters_are_captured(self):
        self.service.set_fader(2, 70)  # nothing else was ever commanded or observed
        self.bar.capture_button.invoke()
        self.assertEqual(self.service.scenes.get("SCENE 1").parameters, {2: {"fader": 70}})
        self.assertEqual(self.messages[-1], "SCENE CAPTURED — SCENE 1 · 1 VALUES")


class RecallTests(_Case):
    def capture_then_change(self, slot=1):
        self.seed()
        self.bar.slot_buttons[slot].invoke()
        self.bar.capture_button.invoke()
        for channel in range(1, 8):
            self.service.set_fader(channel, 5)
            self.service.set_pan(channel, 10)
            self.service.set_mute(channel, True)
        self.service.set_fader(8, 5)
        self.console._refresh_strips()
        self.service.ledger.clear()

    def test_recall_calls_the_service_and_moves_every_strip_back(self):
        self.capture_then_change(slot=2)
        self.assertEqual(self.console.strips[1].fader_val.get(), 5)

        with mock.patch.object(self.service, "recall_scene", wraps=self.service.recall_scene) as spy:
            self.bar.recall_button.invoke()
        spy.assert_called_once_with("SCENE 2")

        self.assertEqual(self.messages[-1], "SCENE RECALLED — SCENE 2")
        for channel in range(1, 8):
            strip = self.console.strips[channel]
            self.assertEqual(strip.fader_val.get(), 50 + channel)
            self.assertEqual(strip.pan_val.get(), 60 + channel)
            self.assertFalse(strip.is_muted.get())
            self.assertIn(f"MIDI {50 + channel}/127", strip.midi_label_var.get())
        main = self.console.strips[8]
        self.assertEqual(main.fader_val.get(), 90)
        self.assertEqual(main.pan_val.get(), 64)
        self.assertEqual(self.commanded("ch1.fader"), 51)
        self.assertIs(self.commanded("ch3.mute"), False)

    def test_recall_is_a_single_undo_step(self):
        self.capture_then_change()
        self.bar.recall_button.invoke()
        self.assertTrue(self.service.ledger.can_undo)

        self.assertTrue(self.console.undo())
        self.assertIn("CHANGES", self.messages[-1])
        self.assertFalse(self.service.ledger.can_undo, "one Ctrl+Z must undo the whole recall")
        for channel in range(1, 8):
            strip = self.console.strips[channel]
            self.assertEqual(strip.fader_val.get(), 5)
            self.assertTrue(strip.is_muted.get())

    def test_recalling_an_empty_slot_is_rejected_not_silent(self):
        self.assertFalse(self.console.recall_scene(5))
        self.assertEqual(self.messages, ["SCENE RECALL REJECTED — SCENE 5 IS EMPTY"])

    def test_commands_the_boundary_rejects_are_reported_not_hidden(self):
        self.capture_then_change()
        real = self.service.command_boundary.execute_command

        def flaky(param_id, *args, **kwargs):
            if param_id == "ch3.fader":
                raise Flow8CommandError("driver down")
            return real(param_id, *args, **kwargs)

        with mock.patch.object(self.service.command_boundary, "execute_command", side_effect=flaky):
            self.assertTrue(self.console.recall_scene(1))
        self.assertEqual(self.messages[-1], "SCENE RECALLED — SCENE 1 · 22 SENT · 1 NOT SENT")
        self.assertEqual(self.console.strips[3].fader_val.get(), 5)  # still the old value
        self.assertEqual(self.console.strips[4].fader_val.get(), 54)

    def test_total_failure_says_nothing_was_sent(self):
        self.capture_then_change()
        with mock.patch.object(
            self.service.command_boundary, "execute_command",
            side_effect=Flow8CommandError("driver down"),
        ):
            self.assertFalse(self.console.recall_scene(1))
        self.assertTrue(self.messages[-1].startswith("SCENE RECALL FAILED — NOT SENT"))


class PhantomSafetyTests(_Case):
    def test_scenes_never_touch_or_display_phantom(self):
        self.seed()
        self.service.set_phantom(1, True)
        strip1 = self.console.strips[1]
        strip1.sync_phantom(True)
        entries_before = len(self.phantom_entries())

        with mock.patch.object(self.service, "set_phantom", wraps=self.service.set_phantom) as spy:
            self.bar.capture_button.invoke()
            self.service.set_phantom(1, False)  # operator changes it after the capture
            spy.reset_mock()
            self.service.set_phantom(1, False)
            spy.reset_mock()
            self.bar.recall_button.invoke()
        spy.assert_not_called()

        self.assertEqual(len(self.phantom_entries()), entries_before + 2)  # only the two explicit ones
        self.assertIs(self.commanded("ch1.phantom"), False)  # recall did not restore +48V
        for values in self.service.scenes.get("SCENE 1").parameters.values():
            self.assertNotIn("phantom", " ".join(map(str, values)).lower())
        self.assertFalse([t for t in widget_texts(self.bar) if "48" in t or "PHANTOM" in t.upper()])

    def test_recall_leaves_the_strip_phantom_button_alone(self):
        self.seed()
        self.bar.capture_button.invoke()
        strip1 = self.console.strips[1]
        strip1.sync_phantom(True)
        self.service.set_phantom(1, True)
        self.bar.recall_button.invoke()
        self.assertTrue(strip1.is_phantom.get())
        self.assertIs(self.commanded("ch1.phantom"), True)


class LayoutTests(unittest.TestCase):
    """Measured in the real app window, where the navigation rail narrows the console."""

    def setUp(self):
        self.service = Flow8Service(auto_connect=False)
        self.app = Flow8App(service=self.service, show_placeholder=False)
        self.addCleanup(self.app.close)
        self.app.root.geometry("1366x768+0+0")
        self.app.root.update()
        self.console = self.app.mixer_console
        self.bar = self.console.scene_bar

    def test_everything_fits_at_1366x768(self):
        right_edge = self.console.winfo_rootx() + self.console.winfo_width()
        for index, strip in self.console.strips.items():
            end = strip.winfo_rootx() + strip.winfo_width()
            self.assertLessEqual(end, right_edge, f"strip {index} runs off the right edge")
            self.assertGreaterEqual(strip.winfo_width(), strip.winfo_reqwidth(), f"strip {index} clipped")

        banner = self.bar.master
        self.assertGreaterEqual(self.bar.winfo_width(), self.bar.winfo_reqwidth(), "scene bar clipped")
        bar_left = self.bar.winfo_rootx()
        bar_right = bar_left + self.bar.winfo_width()
        self.assertLessEqual(bar_right, right_edge)
        for sibling in banner.winfo_children():
            if sibling is self.bar:
                continue
            left = sibling.winfo_rootx()
            right = left + sibling.winfo_width()
            self.assertTrue(right <= bar_left or left >= bar_right, "scene bar overlaps the banner")

    def test_header_controls_fit_beside_the_identity_and_the_pill(self):
        header = self.app.header
        for name, button in header.connection_buttons.items():
            self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth(), f"{name} clipped")
        pill_left = header.pill.winfo_rootx()
        for button in header.connection_buttons.values():
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), pill_left)
        self.assertLessEqual(
            header.pill.winfo_rootx() + header.pill.winfo_width(),
            header.winfo_rootx() + header.winfo_width(),
        )

    def test_the_bar_costs_no_vertical_space(self):
        self.assertGreaterEqual(self.console.strips[1].fader_scale.winfo_height(), 200)
        self.assertGreaterEqual(self.console.command_log_panel.winfo_height(), 50)
        bar = self.app.status_bar
        self.assertLessEqual(bar.winfo_rooty() + bar.winfo_height(), self.app.root.winfo_rooty() + 768)


class AppIntegrationTests(unittest.TestCase):
    def test_feedback_reaches_the_status_bar(self):
        service = Flow8Service(auto_connect=False)
        app = Flow8App(service=service, show_placeholder=False)
        self.addCleanup(app.close)
        app.mixer_console.scene_bar.capture_button.invoke()
        self.assertEqual(
            app.status_bar.last_feedback_full, "SCENE CAPTURE REJECTED — NO KNOWN PARAMETERS"
        )
        service.set_fader(1, 70)
        app.mixer_console.scene_bar.capture_button.invoke()
        app.mixer_console.scene_bar.recall_button.invoke()
        self.assertEqual(app.status_bar.last_feedback_full, "SCENE RECALLED — SCENE 1")


    def test_a_long_message_is_cut_to_fit_and_never_overlaps_the_port_fields(self):
        app = Flow8App(service=Flow8Service(auto_connect=False), show_placeholder=False)
        self.addCleanup(app.close)
        app.root.geometry("1366x768+0+0")
        app.root.update()
        bar = app.status_bar
        reason = "CONNECT FAILED — " + "No FLOW 8 MIDI output port found; check the USB cable. " * 3
        bar.show_feedback(reason)
        app.root.update()

        shown = bar.feedback_var.get()
        self.assertEqual(bar.last_feedback_full, reason)  # nothing is lost
        self.assertTrue(shown.endswith("…") and len(shown) < len(reason))
        label = bar._feedback_label
        self.assertGreaterEqual(label.winfo_width(), label.winfo_reqwidth(), "feedback clipped")
        fields_right = bar._fields.winfo_rootx() + bar._fields.winfo_reqwidth()
        self.assertGreaterEqual(label.winfo_rootx(), fields_right - 1, "overlaps the port fields")

        bar.show_feedback("UNDO COMMANDED — CH 1 FADER MIDI 40")  # short text stays whole
        app.root.update()
        self.assertEqual(bar.feedback_var.get(), "UNDO COMMANDED — CH 1 FADER MIDI 40")


    def test_feedback_stays_clear_when_the_error_field_grows_in_the_same_tick(self):
        app = Flow8App(service=Flow8Service(auto_connect=False), show_placeholder=False)
        self.addCleanup(app.close)
        app.root.geometry("1366x768+0+0")
        app.root.update()
        bar = app.status_bar
        # Same order as a failed CONNECT: port status first, feedback right after, no
        # event-loop turn in between.
        bar.set_midi_port_status(False, False, "No FLOW 8 MIDI output port found")
        bar.show_feedback("CONNECT FAILED — No FLOW 8 MIDI output port found")
        app.root.update()
        label = bar._feedback_label
        self.assertGreaterEqual(label.winfo_width(), label.winfo_reqwidth(), "feedback clipped")
        fields_right = bar._fields.winfo_rootx() + bar._fields.winfo_reqwidth()
        self.assertGreaterEqual(label.winfo_rootx(), fields_right - 1)


if __name__ == "__main__":
    unittest.main()
