"""Unit tests for FLOW 8 Mixer Console and Service (UI.2-T2)."""

import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest import mock

from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.app import Flow8App
from flow8.ui.components.mixer_console import (
    ChannelStripWidget,
    MixerConsole,
    ValueProvenance,
    format_db,
    format_pan,
)
from flow8.ui.components.controls import VerticalFader


class MixerFormattingTests(unittest.TestCase):
    def test_format_db(self):
        self.assertEqual(format_db(0), "-inf dB")
        self.assertIn("0.0 dB", format_db(101))
        self.assertIn("+10.0 dB", format_db(127))

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
        self.assertEqual(ch1.fader_provenance, ValueProvenance.OBSERVED)

    def test_initial_fader_is_marked_as_default(self):
        console = MixerConsole(self.root, self.fonts)
        self.assertIn("DEFAULT", console.strips[1].db_label_var.get())
        self.assertEqual(
            console.strips[1].fader_provenance,
            ValueProvenance.UNSYNCED_DEFAULT,
        )

    def test_failed_fader_dispatch_is_visible_and_rolls_back(self):
        service = mock.Mock()
        service.set_fader.side_effect = RuntimeError("driver unavailable")
        messages = []
        console = MixerConsole(
            self.root, self.fonts, service=service, on_feedback=messages.append
        )
        strip = console.strips[1]
        strip._on_fader_drag("80")
        strip._flush_fader()
        self.assertEqual(strip.fader_val.get(), 0)
        self.assertEqual(strip.fader_provenance, ValueProvenance.DISPATCH_FAILED)
        self.assertIn("FAILED", messages[-1])

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
        strip._on_fader_release(None)
        service.set_fader.assert_called_with(1, strip.fader_val.get())

    def test_fader_coalesces_to_latest_value_until_release(self):
        service = mock.Mock()
        console = MixerConsole(self.root, self.fonts, service=service)
        strip = console.strips[1]
        strip._on_fader_drag("20")
        strip._on_fader_drag("40")
        strip._on_fader_drag("90")
        service.set_fader.assert_not_called()
        strip._on_fader_release(None)
        service.set_fader.assert_called_once_with(1, 90)

    def test_fader_contains_explicit_db_scale_labels(self):
        console = MixerConsole(self.root, self.fonts)
        console.pack(fill="both", expand=True)
        fader = console.strips[1].fader_scale
        self.root.deiconify()
        self.root.geometry("1400x800")
        self.root.update_idletasks()
        labels = {fader.itemcget(item, "text") for item in fader.find_withtag("db-scale")}
        self.assertTrue({"+10", "0", "-10", "-20", "-40", "-∞"}.issubset(labels))

    def test_shift_pointer_delta_is_finer_than_normal_delta(self):
        variable = tk.IntVar(self.root, value=64)
        control = VerticalFader(self.root, variable=variable)
        control.pack()
        self.root.deiconify()
        self.root.geometry("400x400")
        self.root.update_idletasks()
        control._on_pointer(SimpleNamespace(type=tk.EventType.ButtonPress, y=130, state=0))
        normal_start = variable.get()
        control._on_pointer(SimpleNamespace(type=tk.EventType.Motion, y=100, state=0))
        normal_delta = abs(variable.get() - normal_start)
        variable.set(64)
        control._on_pointer(SimpleNamespace(type=tk.EventType.ButtonPress, y=130, state=0))
        fine_start = variable.get()
        control._on_pointer(SimpleNamespace(type=tk.EventType.Motion, y=100, state=1))
        fine_delta = abs(variable.get() - fine_start)
        self.assertLess(fine_delta, normal_delta)

    def test_keyboard_control_dispatches_bounded_values(self):
        service = mock.Mock()
        console = MixerConsole(self.root, self.fonts, service=service)
        strip = console.strips[1]
        strip.fader_scale._on_key(SimpleNamespace(keysym="Up", state=0))
        strip._flush_fader()
        self.assertEqual(strip.fader_val.get(), 4)
        strip.fader_scale._on_key(SimpleNamespace(keysym="Up", state=1))
        strip._flush_fader()
        self.assertEqual(strip.fader_val.get(), 5)
        strip.fader_scale._on_key(SimpleNamespace(keysym="End", state=0))
        strip._flush_fader()
        self.assertEqual(strip.fader_val.get(), 0)
        self.assertEqual(strip.fader_provenance, ValueProvenance.COMMANDED)
        service.set_fader.assert_called_with(1, 0)

    def test_double_click_resets_fader_to_unity(self):
        console = MixerConsole(self.root, self.fonts)
        self.root.deiconify()
        self.root.update()
        strip = console.strips[2]
        strip.fader_scale._on_reset(None)
        self.assertEqual(strip.fader_val.get(), 101)

    def test_inbound_service_update(self):
        service = Flow8Service(auto_connect=False)
        console = MixerConsole(self.root, self.fonts, service=service)
        ch2 = console.strips[2]

        console._apply_update("ch2.fader", 80)
        self.assertEqual(ch2.fader_val.get(), 80)

        console._apply_update("ch2.mute", 1)
        self.assertTrue(ch2.is_muted.get())

        console._apply_update("main.fader", 115)
        self.assertEqual(console.strips[8].fader_val.get(), 115)


class Flow8ServiceTests(unittest.TestCase):
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
