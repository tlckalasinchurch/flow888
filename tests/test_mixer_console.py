"""Unit tests for FLOW 8 Mixer Console and Service (UI.2-T2)."""

import tkinter as tk
import unittest
from unittest import mock

from flow8.service import Flow8Service
from flow8.domain_model import LOGICAL_CHANNELS
from flow8.state_model import EventSource
from flow8.ui import theme
from flow8.ui.app import Flow8App
from flow8.ui.components.mixer_console import (
    ChannelStripWidget,
    MixerConsole,
    format_db,
    format_pan,
)


class MixerFormattingTests(unittest.TestCase):
    def test_format_db(self):
        self.assertEqual(format_db(0), "Approx. -inf dB · MIDI 0/127")
        self.assertIn("Approx. +0.0 dB", format_db(101))
        self.assertIn("MIDI 101/127", format_db(101))
        self.assertIn("Approx. +10.0 dB", format_db(127))
        self.assertIn("MIDI 127/127", format_db(127))

    def test_format_pan(self):
        self.assertEqual(format_pan(64), "C")
        self.assertEqual(format_pan(0), "L100")
        self.assertEqual(format_pan(127), "R100")


class MixerConsoleTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._cleanup)
        self.fonts = theme.build_fonts(self.root)

    def _cleanup(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_console_creates_all_eight_strips(self):
        console = MixerConsole(self.root, self.fonts)
        # Strips 1..7 plus 8 (Master)
        self.assertEqual(len(console.strips), 8)
        for ch in range(1, 9):
            self.assertIn(ch, console.strips)

    def test_input_strip_features(self):
        console = MixerConsole(self.root, self.fonts)
        ch1 = console.strips[1]
        self.assertTrue(ch1.has_phantom)
        self.assertTrue(hasattr(ch1, "phantom_btn"))
        self.assertTrue(hasattr(ch1, "mute_btn"))

        ch3 = console.strips[3]
        self.assertFalse(ch3.has_phantom)
        self.assertFalse(hasattr(ch3, "phantom_btn"))

        master = console.strips[8]
        self.assertTrue(master.is_master)
        self.assertFalse(hasattr(master, "mute_btn"))

    def test_strip_sync_methods(self):
        console = MixerConsole(self.root, self.fonts)
        ch1 = console.strips[1]

        ch1.sync_fader(101)
        self.assertEqual(ch1.fader_val.get(), 101)
        self.assertIn("0.0 dB", ch1.db_label_var.get())

        ch1.sync_pan(0)
        self.assertEqual(ch1.pan_val.get(), 0)
        self.assertEqual(ch1.pan_label_var.get(), "L100")

        ch1.sync_mute(True)
        self.assertTrue(ch1.is_muted.get())

    def test_fader_responds_to_user_drag_and_dispatches(self):
        service = mock.Mock()
        service.is_connected = True
        console = MixerConsole(self.root, self.fonts, service=service)
        console.pack(fill="both", expand=True)
        self.root.deiconify()
        self.root.geometry("1400x800")
        self.root.update()
        strip = console.strips[1]
        fader = strip.fader_scale
        h = fader.winfo_height()
        fader.event_generate("<Button-1>", x=30, y=h // 2)
        self.root.update()
        self.assertGreater(strip.fader_val.get(), 0)
        service.set_fader.assert_called_with(1, strip.fader_val.get())

    def test_double_click_resets_fader_to_unity(self):
        console = MixerConsole(self.root, self.fonts)
        self.root.deiconify()
        self.root.update()
        strip = console.strips[2]
        strip.fader_scale._on_reset(None)
        self.assertEqual(strip.fader_val.get(), 101)

    def test_inbound_observations_do_not_overwrite_command_value_controls(self):
        service = Flow8Service(auto_connect=False)
        console = MixerConsole(self.root, self.fonts, service=service)
        ch2 = console.strips[2]

        service._on_midi_in_event({
            "status": 0xB1, "channel": 2, "data1": 7, "data2": 80,
        })
        self.assertEqual(service.state_store.get_parameter("ch2.fader").observed_value, 80)
        self.assertEqual(ch2.fader_val.get(), 0)

        service._on_midi_in_event({
            "status": 0xB7, "channel": 8, "data1": 7, "data2": 115,
        })
        self.assertEqual(service.state_store.get_parameter("main.fader").observed_value, 115)
        self.assertEqual(console.strips[8].fader_val.get(), 101)

    def test_command_log_panel_shows_dispatch_and_verification_separately(self):
        service = Flow8Service(auto_connect=False)
        console = MixerConsole(self.root, self.fonts, service=service)

        service.set_fader(1, 95)
        service.set_mute(1, True)
        self.root.update()

        rows = console.command_log_panel.tree.get_children()
        self.assertEqual(len(rows), 2)
        newest = console.command_log_panel.tree.item(rows[0], "values")
        older = console.command_log_panel.tree.item(rows[1], "values")
        self.assertEqual(newest[1], "ch1.mute")
        self.assertIn("Ch 1 / CC 5 · prepared 127", newest[4])
        self.assertEqual(newest[5], "ACCEPTED_OFFLINE")
        self.assertEqual(newest[6], "UNKNOWN")
        self.assertEqual(older[1], "ch1.fader")
        self.assertEqual(older[2], "95")
        self.assertEqual(older[3], "UNKNOWN")
        self.assertIn("Ch 1 / CC 7 · prepared 95", older[4])
        self.assertEqual(older[5], "ACCEPTED_OFFLINE")
        self.assertEqual(older[6], "UNKNOWN")


class Flow8ServiceTests(unittest.TestCase):
    def test_inbound_midi_maps_channel_six_to_logical_stereo_pair(self):
        service = Flow8Service(auto_connect=False)
        service.state_store.set_commanded_value(
            "ch6.fader", 35, source=EventSource.LOCAL_HOST, raw_midi_value=35,
        )

        service._on_midi_in_event({
            "status": 0xB5, "channel": 6, "data1": 7, "data2": 80,
        })

        state = service.state_store.get_parameter("ch6.fader")
        self.assertEqual(state.commanded_value, 35)
        self.assertEqual(state.commanded_raw_midi, 35)
        self.assertEqual(state.observed_value, 80)
        self.assertEqual(state.observed_raw_midi, 80)
        self.assertIn("IN_7L", LOGICAL_CHANNELS[6].physical_connectors)
        self.assertIn("IN_8R", LOGICAL_CHANNELS[6].physical_connectors)

    def test_service_initialization_offline(self):
        service = Flow8Service(auto_connect=False)
        self.assertFalse(service.is_connected)

    def test_service_dispatch_fader(self):
        service = Flow8Service(auto_connect=False)
        # Offline dispatch updates state store without hardware error
        service.set_fader(1, 95)
        state = service.state_store.get_parameter("ch1.fader")
        self.assertEqual(state.commanded_raw_midi, 95)

    def test_service_dispatch_mute(self):
        service = Flow8Service(auto_connect=False)
        service.set_mute(1, True)
        state = service.state_store.get_parameter("ch1.mute")
        self.assertEqual(state.commanded_raw_midi, 127)

    def test_service_dispatch_pan(self):
        service = Flow8Service(auto_connect=False)
        service.set_pan(5, 30)
        state = service.state_store.get_parameter("ch5.pan")
        self.assertEqual(state.commanded_raw_midi, 30)


if __name__ == "__main__":
    unittest.main()
