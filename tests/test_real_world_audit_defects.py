"""Real-World UX/UI & Functionality Audit — Defect Reproduction & Regression Tests.

These tests document and reproduce the architectural, state-sync, and layout defects
discovered during the Independent Real-World Audit of Stage 2 (`456fd5a`) without
modifying production business logic or weakening existing tests.

Defects covered:
- D-01 [P1]: Inbound hardware MIDI events (`_on_midi_in_event`) update `Flow8StateStore`
             but never update `ChannelStripWidget` fader/pan/mute in `MixerConsole`.
- D-02 [P1]: Applying a channel preset or invoking Undo/Redo updates `Flow8StateStore`
             but leaves the open `ChannelDetailPanel` sliders and readouts stale.
- D-03 [P1]: Clicking `RESET FLAT (0 dB)` in `ChannelDetailPanel` pushes 4 separate
             undo steps instead of 1 atomic batch transaction.
- D-04 [P1]: `capture_scene` / `SceneManager` only captures `fader`, `pan`, and `mute`,
             discarding `eq_*`, `low_cut`, `compressor`, and `send_*` settings.
- D-05 [P1]: Disconnecting hardware resets `Flow8StateStore` provenance to `UNSYNCED`,
             but leaves `ChannelDetailPanel` badges stuck on `▲ CMD` and `ledger.can_undo` True.
- D-06 [P1]: Opening `ChannelDetailPanel` at minimum supported window size (`1366x768`)
             squeezes all 8 channel strips below their requested width (`105px < 132px`).
- D-07 [P2]: `Navigation` and `StatusBar` call `grid_propagate(False)` on `.pack()`
             containers, failing to enforce `NAVIGATION_WIDTH=232` and `STATUS_BAR_HEIGHT=36`.
"""

from __future__ import annotations

import tkinter as tk
import unittest

from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance
from flow8.ui import theme
from flow8.ui.app import Flow8App
from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget
from flow8.ui.components.mixer_console import MixerConsole


class RealWorldAuditDefectTests(unittest.TestCase):
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

    def test_d01_inbound_midi_fader_updates_strip_widget(self):
        """D-01 [P1]: Inbound hardware MIDI CC 7 should move the strip's on-screen fader."""
        self.service._on_midi_in_event(
            {"status": 0xB0, "channel": 1, "data1": 7, "data2": 101}
        )
        self.console._drain_ui_queue()
        self.assertEqual(
            self.service.state_store.get_parameter("ch1.fader").observed_raw_midi, 101
        )
        self.assertEqual(self.console.strips[1].fader_val.get(), 101)

    def test_d02a_preset_apply_refreshes_open_inspector_sliders(self):
        """D-02a [P1]: Applying a preset should update the open ChannelDetailPanel sliders."""
        self.console.select_target(SelectionTarget.input(1))
        self.console.inspector.show_tab(ChannelDetailPanel.TAB_EQ)
        self.service.apply_channel_preset(1, "vocal-worship-ballad", preserve_levels=True)
        self.root.update()
        expected_raw = self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi
        self.assertEqual(expected_raw, 60)
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 60)

    def test_d02b_undo_refreshes_open_inspector_sliders(self):
        """D-02b [P1]: Clicking UNDO should refresh the open ChannelDetailPanel sliders."""
        self.service.set_eq_band(1, "low", 80, unit="raw")
        self.service.set_eq_band(1, "low", 60, unit="raw")
        self.console.select_target(SelectionTarget.input(1))
        self.console.inspector.show_tab(ChannelDetailPanel.TAB_EQ)
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 60)

        self.console.undo()
        self.root.update()
        self.assertEqual(
            self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 80
        )
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 80)

    @unittest.expectedFailure
    def test_d03_reset_eq_flat_records_single_atomic_undo_step(self):
        """D-03 [P1]: Clicking 'RESET FLAT (0 dB)' should push 1 batch transaction, not 4 steps."""
        for band in ("low", "low_mid", "hi_mid", "hi"):
            self.service.set_eq_band(1, band, 80, unit="raw")
        self.service.ledger.clear()

        self.console.select_target(SelectionTarget.input(1))
        self.console.inspector.reset_eq_flat()

        # Undo once should revert all 4 bands together
        self.service.undo()
        for band in ("low", "low_mid", "hi_mid", "hi"):
            self.assertEqual(
                self.service.state_store.get_parameter(f"ch1.eq_{band}").commanded_raw_midi,
                80,
            )

    @unittest.expectedFailure
    def test_d04_scene_capture_includes_eq_dynamics_and_sends(self):
        """D-04 [P1]: Scene capture should preserve commanded EQ, HPF, Comp, and Aux Sends."""
        self.service.set_fader(1, 90)
        self.service.set_eq_band(1, "low", 75, unit="raw")
        self.service.set_send(1, "mon1", 85, unit="raw")
        snapshot = self.service.capture_scene("SCENE 1")
        self.assertIn("eq_low", snapshot.parameters[1])
        self.assertIn("send_mon1", snapshot.parameters[1])

    def test_d05_disconnect_invalidates_open_inspector_provenance_badges(self):
        """D-05 [P1]: Disconnecting hardware should reset open Inspector badges to UNSYNCED."""
        self.console.select_target(SelectionTarget.input(1))
        self.console.inspector._on_eq_drag("low", "80")
        self.console.inspector._flush_eq("low")
        self.assertEqual(self.console.inspector.eq_badge.label.cget("text"), "▲ CMD")

        self.service.disconnect()
        self.root.update()
        self.assertEqual(
            self.service.state_store.get_parameter("ch1.eq_low").provenance,
            ParameterProvenance.UNSYNCED,
        )
        self.assertEqual(self.console.inspector.eq_badge.label.cget("text"), "○ UNSYNC")

    @unittest.expectedFailure
    def test_d06_strips_not_clipped_at_1366x768_when_inspector_open(self):
        """D-06 [P1]: All 8 strips should fit without clipping at 1366x768 when Inspector is open."""
        app = Flow8App(root=self.root, service=self.service, show_placeholder=False)
        self.root.deiconify()
        self.root.geometry("1366x768")
        self.root.update()
        app.mixer_console.select_target(SelectionTarget.input(1))
        self.root.update()
        self.root.update_idletasks()
        for index, strip in app.mixer_console.strips.items():
            self.assertGreaterEqual(
                strip.winfo_width(),
                strip.winfo_reqwidth(),
                f"strip {index} clipped when inspector open at 1366x768",
            )


if __name__ == "__main__":
    unittest.main()
