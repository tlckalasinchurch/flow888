"""Tests for CueAir Gen Z/Alpha Figma UI implementation (Phases 4-6)."""

from __future__ import annotations

import tkinter as tk
import unittest

from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.app import Flow8App
from flow8.ui.components import widget_texts


class CueAirFigmaUiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.service = Flow8Service(auto_connect=False)
        self.app = Flow8App(root=self.root, service=self.service, show_placeholder=False)
        self.addCleanup(self.app.close)

    def test_figma_palette_tokens(self):
        self.assertEqual(theme.COLORS["background"], "#070B14")
        self.assertEqual(theme.COLORS["cyan"], "#2EF2E2")
        self.assertEqual(theme.COLORS["purple"], "#BC71FF")
        self.assertEqual(theme.COLORS["lime"], "#C5FF4A")

    def test_workstation_navigation_across_all_views(self):
        for key in ("mixer", "routing", "fx", "scenes", "device"):
            self.assertTrue(self.app.navigation.is_enabled(key), key)
            self.assertTrue(self.app.show_page(key), key)
            self.assertEqual(self.app._active_page, key)
        self.assertFalse(self.app.navigation.is_enabled("recording"))
        self.assertFalse(self.app.show_page("recording"))
        self.app.show_page("mixer")

    def test_mute_all_mutes_all_seven_channels_as_one_undo_step(self):
        for ch in range(1, 8):
            self.service.set_mute(ch, False)
        self.service.ledger.clear()

        self.assertTrue(self.app.mixer_console.mute_all())
        for ch in range(1, 8):
            self.assertIs(self.service.state_store.get_parameter(f"ch{ch}.mute").commanded_value, True)

        self.app.mixer_console.undo()
        for ch in range(1, 8):
            self.assertIs(self.service.state_store.get_parameter(f"ch{ch}.mute").commanded_value, False)

    def test_scenes_view_capture_and_recall(self):
        self.service.set_fader(1, 84)
        self.app.show_page("scenes")
        self.app.scenes_view._capture_slot(1)
        self.assertIn("SCENE 1", self.service.scenes.names())
        self.service.set_fader(1, 20)
        self.app.scenes_view._recall_slot(1)
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi, 84)

    def test_routing_view_sends_and_master_and_phones_honesty(self):
        self.app.show_page("routing")
        rv = self.app.routing_view
        rv.select_bus("mon2")
        rv._on_send_drag(1, "77")
        rv._on_master_drag("95")
        self.assertEqual(self.service.state_store.get_parameter("ch1.send_mon2").commanded_raw_midi, 77)
        self.assertEqual(self.service.state_store.get_parameter("mon2.fader").commanded_raw_midi, 95)
        texts = " ".join(widget_texts(rv))
        self.assertIn("PHONES OUTPUT · HARDWARE ONLY", texts)

    def test_fx_view_return_faders_and_honest_unsupported_labels(self):
        self.app.show_page("fx")
        fv = self.app.fx_view
        fv._on_fx_drag("fx1", "82")
        self.assertEqual(self.service.state_store.get_parameter("fx1.fader").commanded_raw_midi, 82)
        texts = " ".join(widget_texts(fv))
        self.assertIn("UNSUPPORTED", texts)
        self.assertIn("READ-ONLY", texts)

    def test_device_view_honest_port_status_and_bluetooth_unsupported(self):
        self.app.show_page("device")
        dv = self.app.device_view
        dv.refresh()
        self.assertEqual(dv.port_status_var.get(), "MIDI PORTS CLOSED")
        texts = " ".join(widget_texts(dv))
        self.assertIn("Bluetooth BLE Control", texts)
        self.assertIn("UNSUPPORTED", texts)


if __name__ == "__main__":
    unittest.main()
