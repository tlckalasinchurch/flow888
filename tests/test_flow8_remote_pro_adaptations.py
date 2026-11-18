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


if __name__ == "__main__":
    unittest.main()
