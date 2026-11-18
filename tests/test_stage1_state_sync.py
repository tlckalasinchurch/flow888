"""Stage 1 state-synchronisation tests: D-01 inbound MIDI, D-02 inspector refresh, D-05 reconnect.

All offline: the service never opens a MIDI port and inbound events are fed to the real
`_on_midi_in_event` handler (no fabricated telemetry in production code).
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
import unittest
from unittest import mock

from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance
from flow8.ui import theme
from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget
from flow8.ui.components.mixer_console import MixerConsole, ValueProvenance


def cc(channel: int, number: int, value: int) -> dict:
    return {"status": 0xB0, "channel": channel, "data1": number, "data2": value}


class Stage1Base(unittest.TestCase):
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

    def state(self, pid):
        return self.service.state_store.get_parameter(pid)


class InboundMidiTests(Stage1Base):
    def test_fader_mute_pan_update_the_matching_strip_only(self):
        self.service._on_midi_in_event(cc(2, 7, 90))
        self.service._on_midi_in_event(cc(2, 5, 1))   # mute
        self.service._on_midi_in_event(cc(2, 10, 30))  # pan
        self.console._drain_ui_queue()
        strip = self.console.strips[2]
        self.assertEqual(strip.fader_val.get(), 90)
        self.assertTrue(strip.is_muted.get())
        self.assertEqual(strip.pan_val.get(), 30)
        self.assertEqual(strip.fader_provenance, ValueProvenance.OBSERVED)
        self.assertEqual(self.console.strips[1].fader_provenance, ValueProvenance.UNSYNCED_DEFAULT)
        self.assertEqual(self.console.strips[3].fader_val.get(), 0)

    def test_main_fader_updates_master_strip(self):
        self.service._on_midi_in_event(cc(8, 7, 55))
        self.console._drain_ui_queue()
        self.assertEqual(self.console.strips[8].fader_val.get(), 55)

    def test_inbound_midi_sends_nothing_to_hardware(self):
        with mock.patch.object(self.service.midi_out, "send_cc") as send:
            before = len(self.service.command_boundary.command_log)
            self.service._on_midi_in_event(cc(1, 7, 100))
            self.service._on_midi_in_event(cc(1, 5, 1))
            self.service._on_midi_in_event(cc(1, 10, 20))
            self.console._drain_ui_queue()
            self.root.update()
        send.assert_not_called()
        self.assertEqual(len(self.service.command_boundary.command_log), before)
        self.assertFalse(self.service.ledger.can_undo)  # an observation is not a command

    def test_missing_telemetry_stays_unsynced_and_zero_is_distinct(self):
        self.console._drain_ui_queue()
        self.assertEqual(self.state("ch1.fader").provenance, ParameterProvenance.UNSYNCED)
        self.assertIsNone(self.state("ch1.fader").observed_raw_midi)
        self.assertEqual(self.console.strips[1].fader_provenance, ValueProvenance.UNSYNCED_DEFAULT)
        # A real reported 0 is OBSERVED, not "missing".
        self.service._on_midi_in_event(cc(1, 7, 0))
        self.console._drain_ui_queue()
        self.assertEqual(self.state("ch1.fader").observed_raw_midi, 0)
        self.assertEqual(self.console.strips[1].fader_provenance, ValueProvenance.OBSERVED)

    def test_worker_thread_events_are_applied_on_tk_thread_only(self):
        main = threading.get_ident()
        seen: list[int] = []
        orig = self.console.strips[4].sync_fader

        def spy(raw):
            seen.append(threading.get_ident())
            orig(raw)

        self.console.strips[4].sync_fader = spy
        worker = threading.Thread(
            target=lambda: self.service._on_midi_in_event(cc(4, 7, 77)))
        worker.start()
        worker.join()
        self.assertEqual(seen, [])  # the worker thread touched no widget
        deadline = time.time() + 2
        while not seen and time.time() < deadline:
            self.root.update()  # runs the console's own poll timer
            time.sleep(0.01)
        self.assertEqual(seen, [main])
        self.assertEqual(self.console.strips[4].fader_val.get(), 77)


class InspectorRefreshTests(Stage1Base):
    def open_eq(self):
        self.console.select_target(SelectionTarget.input(1))
        self.console.inspector.show_tab(ChannelDetailPanel.TAB_EQ)

    def test_preset_apply_refreshes_open_inspector(self):
        self.open_eq()
        self.service.apply_channel_preset(1, "vocal-worship-ballad")
        self.console._drain_ui_queue()
        raw = self.state("ch1.eq_low").commanded_raw_midi
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), raw)
        self.assertEqual(self.console.inspector.eq_badge.label.cget("text"), "▲ CMD")

    def test_undo_and_redo_refresh_open_inspector(self):
        self.service.set_eq_band(1, "low", 80, unit="raw")
        self.service.set_eq_band(1, "low", 60, unit="raw")
        self.open_eq()
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 60)
        self.console.undo()
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 80)
        self.console.redo()
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 60)

    def test_service_level_undo_refreshes_inspector(self):
        self.service.set_eq_band(1, "low", 80, unit="raw")
        self.service.set_eq_band(1, "low", 60, unit="raw")
        self.open_eq()
        self.service.undo()  # not via the toolbar button
        self.console._drain_ui_queue()
        self.assertEqual(self.console.inspector.eq_vars["low"].get(), 80)

    def test_refresh_does_not_rebuild_panel(self):
        self.open_eq()
        var_ids = {k: id(v) for k, v in self.console.inspector.eq_vars.items()}
        children = self.console.inspector.winfo_children()
        self.service.set_eq_band(1, "low", 70, unit="raw")
        self.console.undo()
        self.assertEqual(children, self.console.inspector.winfo_children())
        self.assertEqual(var_ids, {k: id(v) for k, v in self.console.inspector.eq_vars.items()})

    def test_preset_dialog_callback_refreshes_inspector(self):
        self.open_eq()
        with mock.patch("flow8.ui.components.preset_picker.PresetPickerDialog") as dlg:
            self.console.inspector._on_open_presets()
        on_applied = dlg.call_args.kwargs["on_applied"]
        with mock.patch.object(self.console.inspector, "_refresh_if_attached") as refresh:
            on_applied("vocal-worship-ballad")
        refresh.assert_called_once()


class DisconnectIntegrityTests(Stage1Base):
    def test_disconnect_clears_observed_commanded_and_history(self):
        self.service.set_fader(1, 70)
        self.service.set_fader(1, 80)
        self.service._on_midi_in_event(cc(2, 7, 90))
        self.assertTrue(self.service.ledger.can_undo)
        self.service.disconnect()
        for pid in ("ch1.fader", "ch2.fader"):
            p = self.state(pid)
            self.assertEqual(p.provenance, ParameterProvenance.UNSYNCED)
            self.assertIsNone(p.observed_raw_midi)
            self.assertIsNone(p.commanded_raw_midi)
            self.assertIsNone(p.commanded_value)
        self.assertFalse(self.service.ledger.can_undo)
        self.assertFalse(self.service.ledger.can_redo)

    def test_ui_shows_unsynced_after_disconnect(self):
        self.service._on_midi_in_event(cc(1, 7, 90))
        self.service.set_mute(1, True)
        self.console.select_target(SelectionTarget.input(1))
        self.console.inspector._on_eq_drag("low", "80")
        self.console.inspector._flush_eq("low")
        self.console._drain_ui_queue()
        self.assertEqual(self.console.strips[1].fader_val.get(), 90)
        self.service.disconnect()
        self.console._drain_ui_queue()
        strip = self.console.strips[1]
        self.assertEqual(strip.fader_val.get(), 0)
        self.assertFalse(strip.is_muted.get())
        self.assertEqual(strip.fader_provenance, ValueProvenance.UNSYNCED_DEFAULT)
        self.assertEqual(self.console.inspector.eq_badge.label.cget("text"), "○ UNSYNC")
        self.assertEqual(str(self.console.undo_btn.cget("state")), "disabled")

    def test_reconnect_does_not_reuse_stale_undo(self):
        self.service.set_fader(1, 70)
        self.service.set_fader(1, 80)
        self.service.disconnect()
        self.service.reconcile_connection()  # what connect() runs after reopening ports
        self.assertEqual(self.service.undo(), ())
        self.assertIsNone(self.state("ch1.fader").commanded_raw_midi)

    def test_events_queued_before_disconnect_do_not_resurrect_stale_values(self):
        self.service._on_midi_in_event(cc(1, 7, 99))  # queued, not yet drained
        self.service.disconnect()
        self.console._drain_ui_queue()
        self.assertEqual(self.console.strips[1].fader_val.get(), 0)
        self.assertEqual(self.console.strips[1].fader_provenance, ValueProvenance.UNSYNCED_DEFAULT)

    def test_destroy_removes_listener(self):
        self.console.destroy()
        self.assertNotIn(self.console._on_state_event, self.service._listeners)


if __name__ == "__main__":
    unittest.main()
