"""Tests for Flow8-Remote-Pro adaptations (Features 1-5) under flow888 safety rules."""

from __future__ import annotations

import json
import struct
import tempfile
import tkinter as tk
import unittest
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.library_io import (
    BEHRINGER_SYSEX_HEADER,
    FLOW_MAGIC,
    export_library_json,
    import_library_json,
    pack_8bit_to_7bit,
    parse_dsp_snapshot,
    parse_sysex_message,
    unpack_7bit_to_8bit,
)
from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance
from flow8.ui import theme
from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget
from flow8.ui.components.mixer_console import MixerConsole


class UnplugWatchdogTests(unittest.TestCase):
    def test_unplug_detection_disconnects_and_reconciles_to_unsynced(self):
        service = Flow8Service(auto_connect=False)
        service._connected = True
        service.set_fader(1, 50)
        service.set_fader(1, 90)
        self.assertTrue(service.ledger.can_undo)
        self.assertEqual(
            service.state_store.get_parameter("ch1.fader").provenance,
            ParameterProvenance.COMMANDED,
        )

        with mock.patch.object(service.midi_out, "find_device_id", return_value=None), \
             mock.patch.object(service.midi_in, "find_device_id", return_value=None):
            healthy = service.check_connection_health()

        self.assertFalse(healthy)
        self.assertFalse(service._connected)
        self.assertFalse(service.ledger.can_undo)
        self.assertEqual(
            service.state_store.get_parameter("ch1.fader").provenance,
            ParameterProvenance.UNSYNCED,
        )


class BusMasterTests(unittest.TestCase):
    def test_set_bus_fader_dispatches_and_supports_undo(self):
        service = Flow8Service(auto_connect=False)
        service.set_bus_fader("mon1", 60)
        service.set_bus_fader("mon1", 100)
        self.assertEqual(service.state_store.get_parameter("mon1.fader").commanded_raw_midi, 100)
        self.assertTrue(service.ledger.can_undo)

        service.undo()
        self.assertEqual(service.state_store.get_parameter("mon1.fader").commanded_raw_midi, 60)
        service.redo()
        self.assertEqual(service.state_store.get_parameter("mon1.fader").commanded_raw_midi, 100)

    def test_inbound_bus_cc_updates_observed_state(self):
        service = Flow8Service(auto_connect=False)
        service._on_midi_in_event({"status": 0xB0, "channel": 9, "data1": 7, "data2": 88})
        st = service.state_store.get_parameter("mon1.fader")
        self.assertEqual(st.observed_raw_midi, 88)
        self.assertEqual(st.provenance, ParameterProvenance.OBSERVED)

    def test_bus_masters_ui_toggle(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        fonts = theme.build_fonts(root)
        service = Flow8Service(auto_connect=False)
        console = MixerConsole(root, fonts, service=service)
        console.pack(fill="both", expand=True)

        self.assertEqual(set(console.bus_strips), {"mon1", "mon2", "fx1", "fx2"})
        console.toggle_bus_masters()
        self.assertTrue(console._bus_view_active)
        console.bus_strips["fx1"]._on_fader_drag("75")
        console.bus_strips["fx1"]._flush_fader()
        self.assertEqual(service.state_store.get_parameter("fx1.fader").commanded_raw_midi, 75)
        console.toggle_bus_masters()
        self.assertFalse(console._bus_view_active)


class LanHubTests(unittest.TestCase):
    def setUp(self):
        # The hub rejects commands while MIDI is closed. Report "connected" here
        # so the action tests reach the service. Disconnected cases are in
        # tests/test_lan_hub_audit_fixes.py.
        patcher = mock.patch.object(
            Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            try:
                return err.code, json.loads(err.read().decode("utf-8"))
            finally:
                err.close()

    def test_status_session_and_safe_actions(self):
        status = self._get("/api/status")
        self.assertEqual(status["status"], "ok")

        code, res = self._post({"action": "setFader", "channel": 1, "value": 92})
        self.assertEqual(code, 200)
        self.assertTrue(res["ok"])
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi, 92)

        code, res = self._post({"action": "setBusFader", "bus": "mon2", "value": 70})
        self.assertEqual(code, 200)
        self.assertEqual(self.service.state_store.get_parameter("mon2.fader").commanded_raw_midi, 70)

        session = self._get("/api/session")
        ch1 = next(c for c in session["channels"] if c["index"] == 1)
        self.assertEqual(ch1["fader"], 92)
        self.assertEqual(ch1["faderProvenance"], "COMMANDED")

        presets_res = self._get("/api/presets")
        self.assertGreater(len(presets_res["presets"]), 0)

        code, _ = self._post({"action": "applyPreset", "channel": 1, "presetId": "speech-mc-handheld"})
        self.assertEqual(code, 200)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_value, -3.0)

        code, _ = self._post({"action": "resetEqFlat", "channel": 1})
        self.assertEqual(code, 200)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 64)

        code, _ = self._post({"action": "setScribble", "channel": 1, "label": "Lead Vox", "color": "#10b981"})
        self.assertEqual(code, 200)
        session2 = self._get("/api/session")
        ch1_after = next(c for c in session2["channels"] if c["index"] == 1)
        self.assertEqual(ch1_after["label"], "Lead Vox")

        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/styles.css", timeout=3) as r:
            self.assertEqual(r.status, 200)

    def test_gain_and_phantom_are_blocked_over_lan(self):
        code_gain, _ = self._post({"action": "setGain", "channel": 1, "value": 50})
        self.assertEqual(code_gain, 403)
        code_48v, _ = self._post({"action": "set48V", "channel": 1, "value": True})
        self.assertEqual(code_48v, 403)
        self.assertIsNone(self.service.state_store.get_parameter("ch1.gain").commanded_raw_midi)
        self.assertIsNone(self.service.state_store.get_parameter("ch1.phantom").commanded_raw_midi)


class EqCurveCanvasTests(unittest.TestCase):
    def test_eq_curve_draws_and_reflects_provenance(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        fonts = theme.build_fonts(root)
        service = Flow8Service(auto_connect=False)
        console = MixerConsole(root, fonts, service=service)
        console.pack(fill="both", expand=True)

        console.select_target(SelectionTarget.input(1))
        console.inspector.show_tab(ChannelDetailPanel.TAB_EQ)
        root.update()

        canvas = console.inspector.eq_curve
        texts = [canvas.itemcget(i, "text") for i in canvas.find_all() if canvas.type(i) == "text"]
        self.assertIn("COMMANDED — not measured", texts)
        lines = [i for i in canvas.find_all() if canvas.type(i) == "line"]
        # Unsynced -> muted color
        self.assertEqual(canvas.itemcget(lines[-1], "fill"), theme.COLORS["text_muted"])

        # Command EQ -> cyan curve
        console.inspector._on_eq_drag("low", "90")
        console.inspector._flush_eq("low")
        root.update()
        lines2 = [i for i in canvas.find_all() if canvas.type(i) == "line"]
        self.assertEqual(canvas.itemcget(lines2[-1], "fill"), theme.COLORS["cyan"])


class LibraryAndSysexTests(unittest.TestCase):
    def test_library_export_import_roundtrip_and_safety(self):
        src = Flow8Service(auto_connect=False)
        src.set_eq_band(1, "low", 3.0, unit="dB")
        src.set_low_cut(1, 100.0, unit="Hz")
        src.set_compressor(1, 40.0, unit="%")
        src.set_bus_fader("mon1", 80)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "New_8.json"
            exported = export_library_json(src, path)
            self.assertTrue(path.exists())
            self.assertEqual(exported["buses"]["mon1"]["fader"], 80)

            dst = Flow8Service(auto_connect=False)
            dst.set_eq_band(1, "low", 0.0, unit="dB")
            dst.ledger.clear()

            report = import_library_json(dst, path)
            self.assertGreater(report["applied"], 0)
            self.assertAlmostEqual(dst.state_store.get_parameter("ch1.eq_low").commanded_value, 3.0, delta=0.4)
            self.assertEqual(dst.state_store.get_parameter("mon1.fader").commanded_raw_midi, 80)
            self.assertIsNone(dst.state_store.get_parameter("ch1.gain").commanded_raw_midi)
            self.assertIsNone(dst.state_store.get_parameter("ch1.phantom").commanded_raw_midi)

            # Single atomic undo restores ch1.eq_low
            dst.undo()
            self.assertEqual(dst.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 64)

    def test_sysex_7bit_roundtrip_and_crc(self):
        dsp = bytes([i % 256 for i in range(2600)])
        crc = zlib.crc32(dsp) & 0xFFFFFFFF
        raw = bytearray(0x4E0 + 2600)
        raw[0x4D0:0x4D4] = FLOW_MAGIC
        struct.pack_into("<I", raw, 0x4D4, 1)
        struct.pack_into("<I", raw, 0x4D8, crc)
        raw[0x4E0:0x4E0 + 2600] = dsp

        encoded_7bit = pack_8bit_to_7bit(bytes(raw))
        self.assertTrue(all(b < 0x80 for b in encoded_7bit))
        decoded = unpack_7bit_to_8bit(encoded_7bit)
        self.assertEqual(decoded[:len(raw)], bytes(raw))

        parsed = parse_dsp_snapshot(decoded)
        self.assertTrue(parsed["crc_valid"])
        self.assertEqual(parsed["dsp_bytes"], 2600)

        sysex = BEHRINGER_SYSEX_HEADER + encoded_7bit + b"\xF7"
        parsed_frame = parse_sysex_message(sysex)
        self.assertTrue(parsed_frame["crc_valid"])


class SendsOnFaderAndCrossSurfaceSyncTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._cleanup)
        self.fonts = theme.build_fonts(self.root)
        self.service = Flow8Service(auto_connect=False)
        self.console = MixerConsole(self.root, self.fonts, service=self.service)
        self.console.pack(fill="both", expand=True)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def _cleanup(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _post(self, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _get_session(self) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/session", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_bus_color_coding_and_sends_on_fader_dispatch(self):
        # Default MAIN layer: Ch 1..6 White/Silver (#E6E8EB), Ch 7 USB/BT Blue (#4FA8FF), Master (#E6E8EB)
        self.assertEqual(self.console.active_bus, "main")
        self.assertEqual(str(self.console.strips[1].header_accent_bar.cget("bg")), "#E6E8EB")
        self.assertEqual(self.console.strips[1].fader_scale.accent, "#E6E8EB")
        self.assertEqual(str(self.console.strips[7].header_accent_bar.cget("bg")), "#4FA8FF")
        self.assertEqual(self.console.strips[7].fader_scale.accent, "#4FA8FF")
        self.assertEqual(str(self.console.strips[8].title_label.cget("text")), "Main L/R")

        # Select MON 1 -> Emerald Green (#34D399)
        self.console.select_bus("mon1")
        self.assertEqual(self.console.active_bus, "mon1")
        self.assertEqual(self.service.active_bus, "mon1")
        for ch in range(1, 9):
            self.assertEqual(str(self.console.strips[ch].header_accent_bar.cget("bg")), "#34D399")
            self.assertEqual(self.console.strips[ch].fader_scale.accent, "#34D399")
        self.assertEqual(str(self.console.strips[8].title_label.cget("text")), "Monitor 1")
        self.assertEqual(str(self.console.strips[8].num_badge_label.cget("text")), "MON 1")

        # Moving strip 1 fader in MON 1 mode dispatches ch1.send_mon1
        self.console.strips[1]._on_fader_drag("77")
        self.console.strips[1]._flush_fader()
        self.assertEqual(self.service.state_store.get_parameter("ch1.send_mon1").commanded_raw_midi, 77)

        # Moving Master strip (8) fader in MON 1 mode dispatches mon1.fader
        self.console.strips[8]._on_fader_drag("92")
        self.console.strips[8]._flush_fader()
        self.assertEqual(self.service.state_store.get_parameter("mon1.fader").commanded_raw_midi, 92)

        # Select FX 2 -> Violet Purple (#A78BFA)
        self.console.select_bus("fx2")
        self.assertEqual(self.console.active_bus, "fx2")
        self.assertEqual(str(self.console.strips[1].header_accent_bar.cget("bg")), "#A78BFA")
        self.assertEqual(self.console.strips[8].fader_scale.accent, "#A78BFA")
        self.assertEqual(str(self.console.strips[8].title_label.cget("text")), "FX 2 Return")
        self.console.strips[2]._on_fader_drag("65")
        self.console.strips[2]._flush_fader()
        self.assertEqual(self.service.state_store.get_parameter("ch2.send_fx2").commanded_raw_midi, 65)

    def test_cross_surface_sync_between_lan_hub_and_tkinter_console(self):
        # 1. iPad Web UI switches active bus to FX 1 and adjusts send + bus master
        code, _ = self._post({"action": "setActiveBus", "bus": "fx1"})
        self.assertEqual(code, 200)
        self.console._drain_ui_queue()
        self.assertEqual(self.console.active_bus, "fx1")
        self.assertEqual(self.console.strips[1].fader_scale.accent, "#A78BFA")

        code, _ = self._post({"action": "setSend", "channel": 1, "target": "fx1", "value": 88})
        self.assertEqual(code, 200)
        code, _ = self._post({"action": "setBusFader", "bus": "fx1", "value": 105})
        self.assertEqual(code, 200)
        self.console._drain_ui_queue()
        self.assertEqual(self.console.strips[1].fader_val.get(), 88)
        self.assertEqual(self.console.strips[8].fader_val.get(), 105)

        # 2. Desktop switches back to MAIN and moves ch1 fader -> session reflects both
        self.console.select_bus("main")
        self.console.strips[1]._on_fader_drag("99")
        self.console.strips[1]._flush_fader()
        snap = self._get_session()
        self.assertEqual(snap["activeBus"], "main")
        ch1 = next(c for c in snap["channels"] if c["index"] == 1)
        self.assertEqual(ch1["fader"], 99)

    def test_stage_view_toggle_rotary_dials_live_meter_arcs_and_tap_tempo(self):
        # 1. Switch to STAGE view via LAN Hub and verify desktop sync
        code, _ = self._post({"action": "setActiveView", "view": "stage"})
        self.assertEqual(code, 200)
        self.console._drain_ui_queue()
        self.assertEqual(self.console.active_view, "stage")
        self.assertEqual(len(self.console.stage_cards), 7)
        expected_tags = {
            1: "MIC 1", 2: "MIC 2", 3: "COMBO 3", 4: "COMBO 4",
            5: "LINE 5/6", 6: "LINE 7/8", 7: "BT/USB",
        }
        for idx, tag in expected_tags.items():
            self.assertEqual(self.console.stage_cards[idx].tag, tag)

        # 2. Meter arcs are strictly gated: absent before live meter feed
        self.root.deiconify()
        self.root.update()
        dial1 = self.console.stage_cards[1].dial
        self.assertEqual(len(dial1.find_withtag("meter-arc")), 0)

        # Publish real-time USB meter frame via hub -> desktop StageView dial renders meter-arc
        self.hub.publish_meters({"ch1": {"rms": -12.0, "peak": -6.0}, "ch6": {"rms": -3.0, "peak": -0.2}})
        self.console._drain_ui_queue()
        self.root.update()
        self.assertGreater(len(dial1.find_withtag("meter-arc")), 0)
        self.assertGreater(len(self.console.stage_cards[6].dial.find_withtag("meter-arc")), 0)
        # Ch 7 (BT/USB) is not in the USB capture stream -> never shows a fake meter arc
        self.assertEqual(len(self.console.stage_cards[7].dial.find_withtag("meter-arc")), 0)

        # Clearing meters hides the meter arc immediately
        self.console.ingest_meter_levels({}, live=False)
        self.root.update()
        self.assertEqual(len(dial1.find_withtag("meter-arc")), 0)

        # 3. Stage rotary dial dispatches active bus level (MAIN vs MON/FX sends)
        self.console.select_bus("mon2")
        self.assertEqual(self.console.stage_cards[3].dial.accent, "#34D399")
        self.console.stage_cards[3]._on_dial_drag("84")
        self.console.stage_cards[3]._flush_level()
        self.assertEqual(self.service.state_store.get_parameter("ch3.send_mon2").commanded_raw_midi, 84)

        # 4. Tap tempo pad computes rolling BPM locally while keeping MIDI Ch 16 locked
        self.console.tap_tempo(now=10.0)
        bpm = self.console.tap_tempo(now=10.5)  # 0.5s interval -> 120 BPM
        self.assertEqual(bpm, 120)
        self.assertIn("120 BPM", self.console.tap_bpm_var.get())

    def test_full_inspector_bus_geq_fx_grids_and_configure_inputs_view(self):
        from flow8.ui.app import Flow8App

        # 1. Inspector Pan/Balance dispatch on input channel & Main L/R
        self.console.select_target(SelectionTarget.input(1))
        panel = self.console.inspector
        panel._on_pan_drag("90")
        panel._flush_pan()
        self.assertEqual(self.service.state_store.get_parameter("ch1.pan").commanded_raw_midi, 90)

        # 2. Inspect Bus Masters (MON 1 9-Band GEQ & FX 1 / FX 2 4x4 v1.14 Preset Grids)
        self.console.select_target(SelectionTarget.bus("mon1"))
        self.assertIn("MONITOR 1", panel.title_var.get())
        panel.show_tab(ChannelDetailPanel.TAB_BUS_FX)
        self.assertEqual(len(panel.geq_band_labels), 9)
        self.assertIn("63", panel.geq_band_labels)
        self.assertIn("16k", panel.geq_band_labels)

        self.console.select_target(SelectionTarget.bus("fx1"))
        self.assertEqual(len(panel.fx_tile_buttons), 16)
        self.assertIn("AMBIENCE", str(panel.fx_tile_buttons[0].cget("text")))
        self.assertIn("CATHEDRAL", str(panel.fx_tile_buttons[9].cget("text")))

        self.console.select_target(SelectionTarget.bus("fx2"))
        self.assertIn("DELAY 1/1", str(panel.fx_tile_buttons[0].cget("text")))
        self.assertIn("PING PONG", str(panel.fx_tile_buttons[9].cget("text")))

        # 3. Configure Inputs (RoutingView) 8 physical jacks, per-jack meters in5..in8, Stereo/Mono link, -10 dBV pads
        app = Flow8App(service=self.service, show_placeholder=False)
        self.addCleanup(app.close)
        app.show_page("routing")
        rv = app.routing_view
        self.assertEqual(sorted(rv.jack_meters.keys()), list(range(1, 9)))
        self.assertEqual(sorted(rv.jack_phantom_buttons.keys()), [1, 2])
        self.assertIn("5/6", rv.stereo_link_labels)
        self.assertIn("7/8", rv.stereo_link_labels)
        self.assertIn("main", rv.output_pad_labels)

        # Gated per-jack meters: empty before live feed, populated when live feed arrives
        self.assertEqual(len(rv.jack_meters[6].find_withtag("meter-bar")), 0)
        rv.ingest_meter_levels({"ch1": {"rms": -10.0, "peak": -4.0}, "in6": {"rms": -15.0, "peak": -8.0}}, live=True)
        self.assertGreater(len(rv.jack_meters[1].find_withtag("meter-bar")), 0)
        self.assertGreater(len(rv.jack_meters[6].find_withtag("meter-bar")), 0)
        rv.ingest_meter_levels({}, live=False)
        self.assertEqual(len(rv.jack_meters[6].find_withtag("meter-bar")), 0)

        # FxView 4x4 v1.14 grids
        app.show_page("fx")
        fv = app.fx_view
        self.assertEqual(len(fv.fx_grids["fx1"]), 16)
        self.assertEqual(len(fv.fx_grids["fx2"]), 16)


if __name__ == "__main__":
    unittest.main()
