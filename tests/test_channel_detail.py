"""Tests for the FLOW 8 Channel Detail Inspector (UI2-T4-01).

Offline only. These tests never open a MIDI port and never need hardware.
Dispatch paths run through a real ``Flow8Service(auto_connect=False)``, so every
accepted command is validated by the real command boundary and ends as
``ACCEPTED_OFFLINE``. Nothing here mocks a hardware response.
"""

from __future__ import annotations

import ast
import pathlib
import tkinter as tk
import unittest
from unittest import mock

from flow8.command_boundary import Flow8CommandBoundary, Flow8CommandError
from flow8.service import Flow8Service
from flow8.state_model import EventSource
from flow8.ui import theme
from flow8.ui.components import widget_texts
from flow8.ui.components.channel_detail import (
    MAIN_TARGET,
    ChannelDetailPanel,
    SelectionTarget,
)
from flow8.ui.components.mixer_console import MixerConsole
from flow8.ui.safety_dialogs import AnalogGainSafetyGate

UI_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent / "flow8" / "ui"
FORBIDDEN_IMPORTS = {"ctypes", "flow8.midi_out", "flow8.midi_in"}
FORBIDDEN_NAMES = {"winmm", "send_cc", "midioutshortmsg", "midiinshortmsg"}


class _TkCase(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._cleanup)
        self.fonts = theme.build_fonts(self.root)
        self.service = Flow8Service(auto_connect=False)
        self.console = MixerConsole(self.root, self.fonts, service=self.service)
        self.console.pack(fill="both", expand=True)

    def _cleanup(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _show(self):
        """Map the root: Tk drops synthetic mouse/key events for unmapped windows."""
        self.root.deiconify()
        self.root.update()
    @property
    def panel(self) -> ChannelDetailPanel:
        return self.console.inspector

    def log(self):
        return self.service.command_boundary.command_log


class SelectionTargetTests(unittest.TestCase):
    def test_input_targets_are_strips_one_to_seven(self):
        for index in range(1, 8):
            self.assertEqual(SelectionTarget.input(index).kind, "input")
        for bad in (0, 8, 9, -1):
            with self.assertRaises(ValueError):
                SelectionTarget.input(bad)

    def test_main_is_its_own_identity_not_input_eight(self):
        self.assertEqual(MAIN_TARGET.kind, "main")
        self.assertIsNone(MAIN_TARGET.index)
        with self.assertRaises(ValueError):
            SelectionTarget("input", 8)
        with self.assertRaises(ValueError):
            SelectionTarget("main", 8)
        with self.assertRaises(ValueError):
            SelectionTarget("bus", 1)


class SelectionTests(_TkCase):
    def test_select_input_channel_one(self):
        self.console.select_target(SelectionTarget.input(1))
        self.assertEqual(self.console.selected_target, SelectionTarget.input(1))
        self.assertTrue(self.console.strips[1].is_selected)
        self.assertTrue(self.console.inspector_visible)
        self.assertIn("CHANNEL 01", self.panel.title_var.get())

    def test_select_input_channel_two(self):
        self.console.select_target(SelectionTarget.input(2))
        self.assertEqual(self.console.selected_target, SelectionTarget.input(2))
        self.assertIn("CHANNEL 02", self.panel.title_var.get())

    def test_selection_is_exclusive(self):
        self.console.select_target(SelectionTarget.input(1))
        self.console.select_target(SelectionTarget.input(2))
        selected = [i for i, s in self.console.strips.items() if s.is_selected]
        self.assertEqual(selected, [2])
        self.assertEqual(self.console.selected_target, SelectionTarget.input(2))

    def test_selected_strip_gets_cyan_highlight_and_others_keep_border(self):
        colors = theme.COLORS
        self.console.select_target(SelectionTarget.input(3))
        self.assertEqual(
            str(self.console.strips[3].cget("highlightbackground")), colors["cyan"]
        )
        self.assertEqual(
            str(self.console.strips[1].cget("highlightbackground")), colors["border"]
        )
        self.console.clear_selection()
        self.assertEqual(
            str(self.console.strips[3].cget("highlightbackground")), colors["border"]
        )

    def test_channel_six_is_the_seven_eight_pair(self):
        self.console.select_target(SelectionTarget.input(6))
        self.assertIn("7/8", self.panel.title_var.get() + self.panel.subtitle_var.get())
        self.assertIn("MIDI CH 6", self.panel.subtitle_var.get().upper())

    def test_master_target_identity(self):
        self.console.select_target(MAIN_TARGET)
        self.assertEqual(self.console.selected_target, MAIN_TARGET)
        self.assertEqual(self.console.selected_target.kind, "main")
        self.assertTrue(self.console.strips[8].is_selected)
        self.assertIn("MAIN L/R", self.panel.title_var.get().upper())
        self.assertNotIn("CHANNEL 08", self.panel.title_var.get().upper())

    def test_close_panel_clears_selection(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.close_button.invoke()
        self.assertIsNone(self.console.selected_target)
        self.assertFalse(self.console.inspector_visible)
        self.assertFalse(any(s.is_selected for s in self.console.strips.values()))

    def test_header_click_selects(self):
        self._show()
        self.console.strips[2].header_frame.event_generate("<Button-1>", x=3, y=3)
        self.assertEqual(self.console.selected_target, SelectionTarget.input(2))

    def test_master_header_click_selects_main(self):
        self._show()
        self.console.strips[8].header_frame.event_generate("<Button-1>", x=3, y=3)
        self.assertEqual(self.console.selected_target, MAIN_TARGET)

    def test_fader_pan_mute_do_not_change_selection(self):
        self._show()
        # Positive control: synthetic clicks are delivered, and a header click selects.
        self.console.strips[2].header_frame.event_generate("<Button-1>", x=3, y=3)
        self.assertEqual(self.console.selected_target, SelectionTarget.input(2))

        strip = self.console.strips[1]
        strip.fader_scale._commit(80)
        strip.pan_scale._commit(70)
        strip.mute_btn.invoke()
        strip.fader_scale.event_generate("<Button-1>", x=10, y=40)
        strip.fader_scale.event_generate("<B1-Motion>", x=10, y=60)
        strip.mute_btn.event_generate("<Button-1>", x=3, y=3)
        strip.pan_scale.event_generate("<Button-1>", x=10, y=10)
        self.assertEqual(self.console.selected_target, SelectionTarget.input(2))
        self.assertFalse(strip.is_selected)
        self.assertTrue(self.console.strips[2].is_selected)

    def test_selection_does_not_dispatch(self):
        self.console.select_target(SelectionTarget.input(1))
        self.console.select_target(MAIN_TARGET)
        self.console.clear_selection()
        self.assertEqual(self.log(), [])


class PhantomAvailabilityTests(_TkCase):
    def test_enabled_for_mic_one_and_two(self):
        for channel in (1, 2):
            self.console.select_target(SelectionTarget.input(channel))
            self.assertTrue(self.panel.phantom_available)
            self.assertEqual(str(self.panel.phantom_button.cget("state")), "normal")

    def test_unavailable_for_other_input_strips(self):
        for channel in range(3, 8):
            self.console.select_target(SelectionTarget.input(channel))
            self.assertFalse(self.panel.phantom_available)
            self.assertEqual(str(self.panel.phantom_button.cget("state")), "disabled")
            self.assertIn("N/A — NO HARDWARE RELAY", self.panel.phantom_note_var.get())

    def test_main_cannot_invoke_phantom(self):
        self.console.select_target(MAIN_TARGET)
        self.assertFalse(self.panel.phantom_available)
        self.assertEqual(str(self.panel.phantom_button.cget("state")), "disabled")
        with mock.patch.object(self.service, "set_phantom") as set_phantom:
            self.panel.phantom_button.invoke()
            self.assertFalse(self.panel.request_phantom(8, True))
        set_phantom.assert_not_called()
        self.assertIsNone(self.panel._phantom_dialog)

    def test_invalid_targets_rejected_without_dialog_or_dispatch(self):
        with mock.patch.object(self.service, "set_phantom") as set_phantom:
            for channel in (0, 3, 4, 5, 6, 7, 8, 9):
                self.assertFalse(self.panel.request_phantom(channel, True))
                self.assertIsNone(self.panel._phantom_dialog)
        set_phantom.assert_not_called()
        self.assertEqual(self.log(), [])

    def test_allowlist_has_exactly_two_phantom_entries_on_cc12(self):
        phantom = {
            key: spec
            for key, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items()
            if key.endswith(".phantom")
        }
        self.assertEqual(set(phantom), {"ch1.phantom", "ch2.phantom"})
        for channel, key in ((1, "ch1.phantom"), (2, "ch2.phantom")):
            self.assertEqual(phantom[key]["channel"], channel)
            self.assertEqual(phantom[key]["cc"], 12)
            self.assertTrue(phantom[key]["boolean"])


class PhantomDialogTests(_TkCase):
    def _open_on(self, channel=1):
        self.console.select_target(SelectionTarget.input(channel))
        with mock.patch.object(
            self.service, "set_phantom", wraps=self.service.set_phantom
        ) as spy:
            self.spy = spy
            self.assertTrue(self.panel.request_phantom(channel, True))
        # Re-wrap for the confirm step.
        self.assertIsNotNone(self.panel._phantom_dialog)
        return self.panel._phantom_dialog

    def test_on_request_opens_dialog_without_dispatch(self):
        dialog = self._open_on(1)
        self.assertTrue(dialog.winfo_exists())
        self.spy.assert_not_called()
        self.assertEqual(self.log(), [])
        self.assertEqual(self.panel.phantom_cmd_var.get(), "OFF")

    def test_dialog_names_exact_target_microphone(self):
        dialog = self._open_on(2)
        texts = []

        def walk(widget):
            try:
                texts.append(str(widget.cget("text")))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                walk(child)

        walk(dialog)
        joined = " ".join(texts)
        self.assertIn("CHANNEL 02", joined)
        self.assertIn("MIC 2", joined)
        self.assertIn("+48V", joined)

    def test_cancel_causes_zero_service_calls(self):
        dialog = self._open_on(1)
        dialog._cancel()
        self.spy.assert_not_called()
        self.assertEqual(self.log(), [])
        self.assertIsNone(self.panel._phantom_dialog)
        self.assertEqual(self.panel.phantom_cmd_var.get(), "OFF")

    def test_escape_causes_zero_service_calls(self):
        self._show()
        dialog = self._open_on(1)
        dialog.update()
        dialog.focus_force()
        dialog.update()
        dialog.event_generate("<Escape>", when="now")
        self.root.update()
        self.assertFalse(dialog.winfo_exists())
        self.spy.assert_not_called()
        self.assertEqual(self.log(), [])

    def test_window_close_causes_zero_service_calls(self):
        dialog = self._open_on(1)
        dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))
        self.root.update()
        self.assertFalse(dialog.winfo_exists())
        self.spy.assert_not_called()
        self.assertEqual(self.log(), [])

    def test_confirm_invokes_only_the_approved_service_method(self):
        dialog = self._open_on(1)
        with mock.patch.object(
            self.service, "set_phantom", wraps=self.service.set_phantom
        ) as set_phantom, mock.patch.object(
            self.service, "set_fader"
        ) as fader, mock.patch.object(
            self.service, "set_mute"
        ) as mute, mock.patch.object(
            self.service, "set_pan"
        ) as pan:
            dialog._confirm()
        set_phantom.assert_called_once_with(1, True)
        fader.assert_not_called()
        mute.assert_not_called()
        pan.assert_not_called()

    def test_confirm_goes_through_command_boundary_offline(self):
        dialog = self._open_on(1)
        dialog._confirm()
        entries = self.log()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.param_id, "ch1.phantom")
        self.assertEqual(entry.midi_channel, 1)
        self.assertEqual(entry.midi_cc, 12)
        self.assertEqual(entry.raw_midi_prepared, 127)
        self.assertIsNone(entry.raw_midi_sent)
        self.assertEqual(entry.dispatch_status, "ACCEPTED_OFFLINE")
        self.assertFalse(entry.driver_dispatched)
        self.assertIsNone(entry.hardware_applied)
        self.assertFalse(self.service.midi_out_open)
        self.assertFalse(self.service.midi_in_open)

    def test_repeated_confirm_does_not_duplicate_dispatch(self):
        dialog = self._open_on(1)
        dialog._confirm()
        dialog._confirm()
        dialog._confirm()
        self.assertEqual(len(self.log()), 1)

    def test_second_request_while_dialog_open_is_ignored(self):
        first = self._open_on(1)
        self.assertFalse(self.panel.request_phantom(1, True))
        self.assertFalse(self.panel.request_phantom(2, True))
        self.assertIs(self.panel._phantom_dialog, first)
        first._confirm()
        self.assertEqual(len(self.log()), 1)

    def test_pending_confirmation_stays_bound_to_original_channel(self):
        dialog = self._open_on(1)
        self.console.select_target(SelectionTarget.input(2))
        dialog._confirm()
        params = [entry.param_id for entry in self.log()]
        self.assertEqual(params, ["ch1.phantom"])
        self.assertEqual(
            self.service.state_store.get_parameter("ch2.phantom").commanded_value,
            False,
        )

    def test_selection_change_does_not_cancel_or_redirect(self):
        dialog = self._open_on(2)
        self.console.select_target(MAIN_TARGET)
        self.assertTrue(dialog.winfo_exists())
        dialog._confirm()
        self.assertEqual([e.param_id for e in self.log()], ["ch2.phantom"])

    def test_confirm_updates_commanded_not_observed(self):
        dialog = self._open_on(1)
        dialog._confirm()
        self.assertEqual(self.panel.phantom_cmd_var.get(), "ON")
        self.assertEqual(self.panel.phantom_obs_var.get(), "UNKNOWN")
        self.assertEqual(self.panel.phantom_sync_var.get(), "UNSYNCED")
        state = self.service.state_store.get_parameter("ch1.phantom")
        self.assertTrue(state.commanded_value)
        self.assertIsNone(state.observed_value)
        self.assertTrue(self.console.strips[1].is_phantom.get())

    def test_matching_observation_never_renders_the_word_synced(self):
        dialog = self._open_on(1)
        dialog._confirm()
        self.service.state_store.set_observed_value("ch1.phantom", True, EventSource.PHYSICAL_HARDWARE)
        self.panel._refresh_phantom()
        self.assertEqual(self.panel.phantom_sync_var.get(), "OBS = CMD")
        self.assertNotRegex(" ".join(widget_texts(self.root)).upper(), r"\bSYNCED\b")

    def test_restore_of_phantom_goes_through_strip_sync(self):
        self._open_on(1)._confirm()
        strip = self.console.strips[1]
        strip.is_phantom.set(False)
        strip._restore_commanded_value("phantom")
        self.assertTrue(strip.is_phantom.get())
        self.console.strips[3].sync_phantom(True)  # no +48V button: must not raise

    def test_failed_dispatch_restores_prior_state_and_shows_error(self):
        dialog = self._open_on(1)
        with mock.patch.object(
            self.service, "set_phantom", side_effect=Flow8CommandError("boom")
        ):
            dialog._confirm()
        self.assertEqual(self.panel.phantom_cmd_var.get(), "OFF")
        self.assertFalse(self.console.strips[1].is_phantom.get())
        self.assertIn("NOT SENT", self.panel.error_var.get())
        self.assertIn("boom", self.panel.error_var.get())
        self.assertNotIn("CONFIRMED", self.panel.error_var.get().upper())

    def test_failed_off_after_on_keeps_last_commanded_on(self):
        self._open_on(1)._confirm()
        self.assertEqual(self.panel.phantom_cmd_var.get(), "ON")
        with mock.patch.object(
            self.service, "set_phantom", side_effect=Flow8CommandError("nope")
        ):
            self.assertFalse(self.panel.request_phantom(1, False))
        self.assertEqual(self.panel.phantom_cmd_var.get(), "ON")
        self.assertTrue(self.console.strips[1].is_phantom.get())
        self.assertIn("nope", self.panel.error_var.get())

    def test_off_dispatches_value_zero_without_dialog(self):
        self._open_on(1)._confirm()
        self.assertTrue(self.panel.request_phantom(1, False))
        self.assertIsNone(self.panel._phantom_dialog)
        entries = self.log()
        self.assertEqual([e.param_id for e in entries], ["ch1.phantom", "ch1.phantom"])
        self.assertEqual(entries[-1].raw_midi_prepared, 0)
        self.assertEqual(entries[-1].dispatch_status, "ACCEPTED_OFFLINE")
        self.assertEqual(self.panel.phantom_cmd_var.get(), "OFF")

    def test_inbound_observation_is_separate_from_command(self):
        self.console.select_target(SelectionTarget.input(1))
        self.service._on_midi_in_event(
            {"status": 0xB0, "channel": 1, "data1": 12, "data2": 127}
        )
        self.root.update()
        self.assertEqual(self.panel.phantom_obs_var.get(), "ON")
        self.assertEqual(self.panel.phantom_cmd_var.get(), "OFF")
        self.assertEqual(self.log(), [])

    def test_strip_phantom_button_requires_confirmation(self):
        strip = self.console.strips[1]
        with mock.patch.object(
            self.service, "set_phantom", wraps=self.service.set_phantom
        ) as set_phantom:
            strip.phantom_btn.invoke()
            set_phantom.assert_not_called()
            self.assertIsNotNone(self.panel._phantom_dialog)
            self.assertFalse(strip.is_phantom.get())
            self.panel._phantom_dialog._cancel()
        set_phantom.assert_not_called()
        self.assertEqual(self.log(), [])

    def test_offline_shell_without_service_cannot_dispatch(self):
        panel = ChannelDetailPanel(self.root, self.fonts, service=None)
        panel.show_target(SelectionTarget.input(1))
        self.assertEqual(str(panel.phantom_button.cget("state")), "disabled")
        self.assertFalse(panel.request_phantom(1, True))
        self.assertIsNone(panel._phantom_dialog)
        self.assertIn("NO COMMAND SERVICE", panel.error_var.get().upper())


class AnalogGainPreviewTests(_TkCase):
    def test_slider_preview_updates_and_is_labelled_unverified(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.gain_slider._commit(80)
        self.assertEqual(self.panel.gain_preview_var.get(), 80)
        text = self.panel.gain_preview_text_var.get()
        self.assertIn("UNVERIFIED", text)
        self.assertIn("80", text)

    def test_preview_makes_zero_service_calls(self):
        self.console.select_target(SelectionTarget.input(3))
        with mock.patch.object(
            self.service.command_boundary, "execute_command"
        ) as execute:
            for value in (10, 64, 127, 0):
                self.panel.gain_slider._commit(value)
        execute.assert_not_called()
        self.assertEqual(self.log(), [])

    def test_cancel_restores_original_staged_value(self):
        self.console.select_target(SelectionTarget.input(1))
        baseline = self.panel.gain_preview_var.get()
        self.panel.gain_slider._commit(99)
        self.assertTrue(self.panel.gain_gate.is_staged)
        self.panel.cancel_gain_preview()
        self.assertEqual(self.panel.gain_preview_var.get(), baseline)
        self.assertFalse(self.panel.gain_gate.is_staged)
        self.assertEqual(self.log(), [])

    def test_apply_button_stays_disabled_and_inert(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.gain_slider._commit(50)
        self.assertEqual(str(self.panel.gain_apply_btn.cget("state")), "disabled")
        self.panel.gain_apply_btn.invoke()
        self.assertEqual(self.log(), [])

    def test_mapping_remains_gated(self):
        self.assertFalse(AnalogGainSafetyGate.is_verified_mapping_available())
        self.console.select_target(SelectionTarget.input(1))
        with self.assertRaises(RuntimeError):
            self.panel.gain_gate.commit_gain(self.service)

    def test_gain_available_only_on_inputs_one_to_four(self):
        for channel in (1, 2, 3, 4):
            self.console.select_target(SelectionTarget.input(channel))
            self.assertTrue(self.panel.gain_available)
        for channel in (5, 6, 7):
            self.console.select_target(SelectionTarget.input(channel))
            self.assertFalse(self.panel.gain_available)
            self.assertIsNone(self.panel.gain_gate)
        self.console.select_target(MAIN_TARGET)
        self.assertFalse(self.panel.gain_available)

    def test_switching_channels_resets_preview(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.gain_slider._commit(77)
        self.console.select_target(SelectionTarget.input(2))
        self.assertFalse(self.panel.gain_gate.is_staged)
        self.assertEqual(self.panel.gain_gate.channel_index, 2)

    def test_gain_commanded_value_is_not_invented(self):
        self.console.select_target(SelectionTarget.input(1))
        self.assertIn("NOT COMMANDED", self.panel.gain_cmd_var.get())


class BoundaryTests(unittest.TestCase):
    PATHS = (
        UI_DIRECTORY / "components" / "channel_detail.py",
        UI_DIRECTORY / "components" / "mixer_console.py",
        UI_DIRECTORY / "safety_dialogs.py",
    )

    def test_no_transport_imports(self):
        for path in self.PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name, FORBIDDEN_IMPORTS, path.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertNotIn(module, FORBIDDEN_IMPORTS, path.name)
                    self.assertFalse(module.startswith("flow8.midi"), path.name)

    def test_no_driver_call_sites(self):
        for path in self.PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id.lower(), FORBIDDEN_NAMES, path.name)
                elif isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr.lower(), FORBIDDEN_NAMES, path.name)

    def test_inspector_only_reaches_the_phantom_setter_through_the_safety_gate(self):
        def setters(path):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            return {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and (node.attr.startswith("set_") or node.attr.startswith("execute"))
            }

        self.assertEqual(
            setters(UI_DIRECTORY / "components" / "channel_detail.py"), set()
        )
        self.assertEqual(setters(UI_DIRECTORY / "safety_dialogs.py"), {"set_phantom"})

    def test_inspector_does_not_touch_the_boundary_or_engine_directly(self):
        path = UI_DIRECTORY / "components" / "channel_detail.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("command_boundary", "parameter_engine", "execute_command"):
            self.assertNotIn(forbidden, source)


class LifecycleTests(_TkCase):
    def test_open_and_close_repeatedly_without_tcl_error(self):
        for _ in range(3):
            self.console.select_target(SelectionTarget.input(1))
            self.root.update()
            self.console.select_target(MAIN_TARGET)
            self.root.update()
            self.console.clear_selection()
            self.root.update()
        self.assertIsNone(self.console.selected_target)

    def test_no_stale_selection_after_close(self):
        self.console.select_target(SelectionTarget.input(1))
        self.console.clear_selection()
        self.assertIsNone(self.panel.target)
        self.assertFalse(any(s.is_selected for s in self.console.strips.values()))
        self.console.select_target(SelectionTarget.input(2))
        self.assertEqual(self.panel.target, SelectionTarget.input(2))

    def test_listener_registered_once_and_removed_on_close(self):
        listener = self.panel._on_state_event
        self.assertNotIn(listener, self.service._listeners)
        self.console.select_target(SelectionTarget.input(1))
        self.console.select_target(SelectionTarget.input(2))
        self.console.select_target(MAIN_TARGET)
        self.assertEqual(self.service._listeners.count(listener), 1)
        self.console.clear_selection()
        self.assertNotIn(listener, self.service._listeners)

    def test_console_destroy_removes_all_listeners(self):
        listener = self.panel._on_state_event
        command_log_listener = self.console._on_command_log_update
        self.console.select_target(SelectionTarget.input(1))
        self.console.destroy()
        self.assertNotIn(listener, self.service._listeners)
        self.assertNotIn(
            command_log_listener, self.service._command_log_listeners
        )

    def test_destroy_with_open_dialog_is_clean(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.request_phantom(1, True)
        dialog = self.panel._phantom_dialog
        self.console.destroy()
        self.root.update()
        self.assertFalse(dialog.winfo_exists())
        self.assertEqual(self.log(), [])

    def test_close_while_dialog_open_cancels_it(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.request_phantom(1, True)
        dialog = self.panel._phantom_dialog
        self.panel.close_button.invoke()
        self.root.update()
        self.assertFalse(dialog.winfo_exists())
        self.assertEqual(self.log(), [])

    def test_late_state_event_after_close_is_ignored(self):
        self.console.select_target(SelectionTarget.input(1))
        self.console.clear_selection()
        self.panel._on_state_event("ch1.phantom", True)
        self.root.update()


class LayoutTests(unittest.TestCase):
    def _measure(self, width, height):
        from flow8.ui.app import Flow8App

        service = Flow8Service(auto_connect=False)
        app = Flow8App(
            service=service, connect_hardware=False, show_placeholder=False
        )
        self.addCleanup(lambda: app.close())
        app.root.geometry(f"{width}x{height}+0+0")
        app.root.deiconify()
        app.root.update()
        console = app.mixer_console
        console.select_target(SelectionTarget.input(1))
        app.root.update()
        app.root.update_idletasks()
        return app, console

    def _assert_fits(self, width, height):
        app, console = self._measure(width, height)
        inspector = console.inspector
        self.assertTrue(inspector.winfo_ismapped())
        self.assertLessEqual(inspector.winfo_width(), 320)
        self.assertGreaterEqual(inspector.winfo_width(), 240)
        # No vertical clipping: every inspector row must sit inside the panel.
        inspector_bottom = inspector.winfo_rooty() + inspector.winfo_height()
        for widget in (
            inspector.close_button,
            inspector.phantom_button,
            inspector.gain_slider,
            inspector.gain_cancel_btn,
            inspector.gain_apply_btn,
            inspector.error_label,
        ):
            self.assertLessEqual(
                widget.winfo_rooty() + widget.winfo_height(),
                inspector_bottom,
                f"{widget} is clipped at {width}x{height}",
            )
        self.assertLessEqual(inspector.body.winfo_reqheight(), inspector.winfo_height())
        console_right = console.winfo_rootx() + console.winfo_width()
        self.assertLessEqual(
            inspector.winfo_rootx() + inspector.winfo_width(), console_right
        )
        for strip in console.strips.values():
            self.assertGreaterEqual(strip.fader_scale.winfo_width(), 60)
            self.assertLessEqual(
                strip.winfo_rootx() + strip.winfo_width(), inspector.winfo_rootx()
            )

    def test_fits_at_default_window(self):
        self._assert_fits(1600, 900)

    def test_fits_at_minimum_window(self):
        self._assert_fits(1366, 768)

    def test_default_window_never_exceeds_the_display(self):
        from flow8.ui.app import Flow8App

        app = Flow8App(connect_hardware=False, show_placeholder=False)
        self.addCleanup(app.close)
        app.root.update()
        screen_w = app.root.winfo_screenwidth()
        screen_h = app.root.winfo_screenheight()
        min_w, min_h = theme.WINDOW_MIN_SIZE
        self.assertLessEqual(app.root.winfo_width(), max(screen_w, min_w))
        self.assertLessEqual(
            app.root.winfo_height(),
            max(screen_h - theme.TASKBAR_ALLOWANCE, min_h),
        )
        self.assertGreaterEqual(app.root.winfo_width(), min_w)
        self.assertGreaterEqual(app.root.winfo_height(), min_h)


if __name__ == "__main__":
    unittest.main()
