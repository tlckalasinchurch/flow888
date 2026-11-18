"""Tests for FLOW 8 Stage 2 UI Controls & Features.

Validates the full Stage 2 Mixer Workstation capabilities:
* 4-Band Parametric EQ (sliders, readouts, reset flat, CC 1-4);
* Low Cut Filter / HPF (frequency slider, bypass, CC 9, Ch 1-4);
* 1-Knob Dynamics Compressor (intensity slider, bypass, CC 11, Ch 1-4);
* Aux Sends (Mon 1, Mon 2, FX 1, FX 2, CC 14-17, Ch 1-7);
* Parameter Provenance visual badges;
* Tabbed inspector navigation (Preamp, EQ, Dynamics, Sends);
* Visual Undo / Redo buttons in the console banner row.
"""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest import mock

from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance
from flow8.ui import theme
from flow8.ui.components.channel_detail import (
    MAIN_TARGET,
    ChannelDetailPanel,
    SelectionTarget,
)
from flow8.ui.components.controls import ProvenanceBadge
from flow8.ui.components.mixer_console import MixerConsole


class _Stage2TkCase(unittest.TestCase):
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

    @property
    def panel(self) -> ChannelDetailPanel:
        return self.console.inspector

    def log(self):
        return self.service.command_boundary.command_log


class Stage2ChannelDetailTabTests(_Stage2TkCase):
    def test_tab_switching(self):
        self.console.select_target(SelectionTarget.input(1))
        self.assertEqual(self.panel.current_tab, ChannelDetailPanel.TAB_PREAMP)
        self.assertEqual(self.panel.preamp_tab.winfo_manager(), "pack")

        # Switch to EQ tab
        self.panel.show_tab(ChannelDetailPanel.TAB_EQ)
        self.assertEqual(self.panel.current_tab, ChannelDetailPanel.TAB_EQ)
        self.assertEqual(self.panel.eq_tab.winfo_manager(), "pack")
        self.assertEqual(self.panel.preamp_tab.winfo_manager(), "")

        # Switch to Dynamics tab
        self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)
        self.assertEqual(self.panel.current_tab, ChannelDetailPanel.TAB_DYNAMICS)
        self.assertEqual(self.panel.dyn_tab.winfo_manager(), "pack")
        self.assertEqual(self.panel.eq_tab.winfo_manager(), "")

        # Switch to Sends tab
        self.panel.show_tab(ChannelDetailPanel.TAB_SENDS)
        self.assertEqual(self.panel.current_tab, ChannelDetailPanel.TAB_SENDS)
        self.assertEqual(self.panel.sends_tab.winfo_manager(), "pack")
        self.assertEqual(self.panel.dyn_tab.winfo_manager(), "")


class Stage2EQControlTests(_Stage2TkCase):
    def test_eq_bands_initialized_to_flat_for_input_channel(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.show_tab(ChannelDetailPanel.TAB_EQ)
        for band in ("low", "low_mid", "hi_mid", "hi"):
            self.assertEqual(self.panel.eq_vars[band].get(), 64)
            self.assertIn("0.0 dB", self.panel.eq_readouts[band].get())

    def test_eq_drag_dispatches_correct_cc_and_value(self):
        self.console.select_target(SelectionTarget.input(2))
        self.panel.show_tab(ChannelDetailPanel.TAB_EQ)

        with mock.patch.object(self.service, "set_eq_band", wraps=self.service.set_eq_band) as spy:
            self.panel._on_eq_drag("low", "80")
            self.panel._flush_eq("low")
            spy.assert_called_once_with(2, "low", 80, unit="raw")

        entries = [e for e in self.log() if e.param_id == "ch2.eq_low"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].raw_midi_prepared, 80)
        self.assertEqual(entries[0].midi_cc, 1)

    def test_eq_reset_flat_sets_all_bands_to_64(self):
        self.console.select_target(SelectionTarget.input(3))
        self.panel.show_tab(ChannelDetailPanel.TAB_EQ)

        # Set some initial non-flat values
        self.panel._on_eq_drag("low", "90")
        self.panel._flush_eq("low")
        self.panel._on_eq_drag("hi", "40")
        self.panel._flush_eq("hi")

        self.panel.reset_eq_flat()
        for band in ("low", "low_mid", "hi_mid", "hi"):
            self.assertEqual(self.panel.eq_vars[band].get(), 64)
            self.assertIn("0.0 dB", self.panel.eq_readouts[band].get())

    def test_eq_unsupported_on_main_target(self):
        self.console.select_target(MAIN_TARGET)
        self.panel.show_tab(ChannelDetailPanel.TAB_EQ)
        self.assertIn("NOT SUPPORTED", self.panel.eq_note_var.get())
        self.assertEqual(self.panel.eq_badge.label.cget("text"), "— N/A")


class Stage2LowCutControlTests(_Stage2TkCase):
    def test_low_cut_supported_on_channel_one_to_four(self):
        for ch in range(1, 5):
            self.console.select_target(SelectionTarget.input(ch))
            self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)
            self.assertEqual(self.panel.low_cut_note_var.get(), "")

    def test_low_cut_unsupported_on_channel_five_to_seven(self):
        for ch in range(5, 8):
            self.console.select_target(SelectionTarget.input(ch))
            self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)
            self.assertIn("AVAILABLE ON CH 1–4 ONLY", self.panel.low_cut_note_var.get())
            self.assertEqual(self.panel.low_cut_badge.label.cget("text"), "— N/A")

    def test_low_cut_drag_and_bypass(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)

        with mock.patch.object(self.service, "set_low_cut", wraps=self.service.set_low_cut) as spy:
            self.panel._on_low_cut_drag("40")
            self.panel._flush_low_cut()
            spy.assert_called_with(1, 40, unit="raw")

        entries = [e for e in self.log() if e.param_id == "ch1.low_cut"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].raw_midi_prepared, 40)
        self.assertEqual(entries[0].midi_cc, 9)

        # Bypass resets to 0 (20 Hz)
        self.panel.bypass_low_cut()
        self.assertEqual(self.panel.low_cut_var.get(), 0)
        self.assertIn("BYPASS", self.panel.low_cut_readout.get())


class Stage2CompressorControlTests(_Stage2TkCase):
    def test_compressor_supported_on_channel_one_to_four(self):
        for ch in range(1, 5):
            self.console.select_target(SelectionTarget.input(ch))
            self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)
            self.assertEqual(self.panel.comp_note_var.get(), "")

    def test_compressor_unsupported_on_channel_five_to_seven(self):
        for ch in range(5, 8):
            self.console.select_target(SelectionTarget.input(ch))
            self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)
            self.assertIn("AVAILABLE ON CH 1–4 ONLY", self.panel.comp_note_var.get())
            self.assertEqual(self.panel.comp_badge.label.cget("text"), "— N/A")

    def test_compressor_drag_and_bypass(self):
        self.console.select_target(SelectionTarget.input(3))
        self.panel.show_tab(ChannelDetailPanel.TAB_DYNAMICS)

        with mock.patch.object(self.service, "set_compressor", wraps=self.service.set_compressor) as spy:
            self.panel._on_comp_drag("55")
            self.panel._flush_comp()
            spy.assert_called_with(3, 55, unit="raw")

        entries = [e for e in self.log() if e.param_id == "ch3.compressor"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].raw_midi_prepared, 55)
        self.assertEqual(entries[0].midi_cc, 11)

        # Bypass resets to 0 (0%)
        self.panel.bypass_comp()
        self.assertEqual(self.panel.comp_var.get(), 0)
        self.assertIn("BYPASS", self.panel.comp_readout.get())


class Stage2AuxSendsControlTests(_Stage2TkCase):
    def test_aux_sends_supported_on_input_strips(self):
        self.console.select_target(SelectionTarget.input(1))
        self.panel.show_tab(ChannelDetailPanel.TAB_SENDS)
        self.assertEqual(self.panel.send_note_var.get(), "")
        for target in ("mon1", "mon2", "fx1", "fx2"):
            self.assertIn(target, self.panel.send_sliders)

    def test_aux_sends_drag_dispatches_correct_cc(self):
        self.console.select_target(SelectionTarget.input(4))
        self.panel.show_tab(ChannelDetailPanel.TAB_SENDS)

        # Test mon1 (CC 14)
        with mock.patch.object(self.service, "set_send", wraps=self.service.set_send) as spy:
            self.panel._on_send_drag("mon1", "101")
            self.panel._flush_send("mon1")
            spy.assert_called_with(4, "mon1", 101, unit="raw")

        entries = [e for e in self.log() if e.param_id == "ch4.send_mon1"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].raw_midi_prepared, 101)
        self.assertEqual(entries[0].midi_cc, 14)

        # Test fx1 (CC 16)
        with mock.patch.object(self.service, "set_send", wraps=self.service.set_send) as spy:
            self.panel._on_send_drag("fx1", "85")
            self.panel._flush_send("fx1")
            spy.assert_called_with(4, "fx1", 85, unit="raw")

        entries_fx = [e for e in self.log() if e.param_id == "ch4.send_fx1"]
        self.assertEqual(len(entries_fx), 1)
        self.assertEqual(entries_fx[0].raw_midi_prepared, 85)
        self.assertEqual(entries_fx[0].midi_cc, 16)

    def test_aux_sends_unsupported_on_main(self):
        self.console.select_target(MAIN_TARGET)
        self.panel.show_tab(ChannelDetailPanel.TAB_SENDS)
        self.assertIn("NOT SUPPORTED ON MAIN", self.panel.send_note_var.get())
        self.assertEqual(self.panel.send_badge.label.cget("text"), "— N/A")


class Stage2ConsoleHistoryButtonsTests(_Stage2TkCase):
    def test_undo_and_redo_buttons_exist_and_initially_disabled(self):
        self.assertTrue(hasattr(self.console, "undo_btn"))
        self.assertTrue(hasattr(self.console, "redo_btn"))
        self.assertEqual(str(self.console.undo_btn.cget("state")), "disabled")
        self.assertEqual(str(self.console.redo_btn.cget("state")), "disabled")

    def test_fader_action_enables_undo_button(self):
        # First command on uncommanded channel establishes known commanded state (previous=None -> non-undoable)
        self.service.set_fader(1, 90)
        self.console._refresh_history_buttons()
        self.assertEqual(str(self.console.undo_btn.cget("state")), "disabled")

        # Second command on channel has known prior value (90 -> undoable)
        self.service.set_fader(1, 100)
        self.console._refresh_history_buttons()
        self.assertEqual(str(self.console.undo_btn.cget("state")), "normal")
        self.assertEqual(str(self.console.redo_btn.cget("state")), "disabled")

        # Invoke undo via button (restores 90)
        self.console.undo_btn.invoke()
        self.assertEqual(str(self.console.undo_btn.cget("state")), "disabled")
        self.assertEqual(str(self.console.redo_btn.cget("state")), "normal")
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi, 90)

        # Invoke redo via button (restores 100)
        self.console.redo_btn.invoke()
        self.assertEqual(str(self.console.undo_btn.cget("state")), "normal")
        self.assertEqual(str(self.console.redo_btn.cget("state")), "disabled")
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi, 100)


if __name__ == "__main__":
    unittest.main()
