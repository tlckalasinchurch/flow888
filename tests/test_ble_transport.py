"""Unit tests for flow8/ble_transport.py codec, echo suppression, and service integration."""

import json
import threading
import time
import unittest
import urllib.request
from unittest import mock

from flow8.ble_transport import (
    AUTH_PACKET,
    CONFIG_REQUEST_PACKET,
    DUMP_TRIGGER_PACKET,
    PARAM_FADER,
    PKT_AUTH_ACK,
    PKT_PARAM_CMD,
    SESSION_START_PACKET,
    BleTransport,
    ble_byte_to_raw_midi,
    ble_checksum,
    build_ble_packet,
    decode_ble_notification,
    encode_fader_command,
    parse_snapshot_names,
    raw_midi_to_ble_byte,
    verify_ble_packet,
)
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance
from tests._no_hardware import NoHardwareMixin


class BleCodecTests(unittest.TestCase):
    def test_known_handshake_packets_pass_checksum(self):
        for pkt in (AUTH_PACKET, SESSION_START_PACKET, CONFIG_REQUEST_PACKET, DUMP_TRIGGER_PACKET):
            self.assertTrue(verify_ble_packet(pkt), pkt.hex())
        self.assertEqual(ble_checksum(bytes.fromhex("3701")), 0x38)
        self.assertEqual(build_ble_packet(0x4B), DUMP_TRIGGER_PACKET)

    def test_fader_encode_and_decode_roundtrip(self):
        pkt = encode_fader_command(1, 101)
        self.assertEqual(pkt[0], PKT_PARAM_CMD)
        self.assertEqual(pkt[2], 1)
        self.assertEqual(pkt[3], PARAM_FADER)
        self.assertTrue(verify_ble_packet(pkt))

        ev = decode_ble_notification(pkt)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.channel, 1)
        self.assertEqual(ev.param_id, PARAM_FADER)
        self.assertEqual(ev.raw_midi, 101)

        self.assertEqual(raw_midi_to_ble_byte(-5), 0)
        self.assertEqual(raw_midi_to_ble_byte(200), 255)
        self.assertEqual(ble_byte_to_raw_midi(255), 127)

        with self.assertRaises(ValueError):
            encode_fader_command(8, 64)

    def test_parse_snapshot_names(self):
        payload = bytes([4]) + b"Live" + bytes([0]) + bytes([7]) + b"Worship"
        pkt = build_ble_packet(0x27, payload)
        names = parse_snapshot_names(pkt)
        self.assertEqual(names, ["Live", None, "Worship"])


class BleEchoAndServiceTests(NoHardwareMixin, unittest.TestCase):
    def test_echo_suppression_and_observed_telemetry(self):
        observed = []
        tr = BleTransport(on_parameter=lambda pid, val: observed.append((pid, val)))
        # Simulate recent outbound write echo for ch1 fader = 200
        pkt = encode_fader_command(1, 100)
        tr._recent_echoes[(1, PARAM_FADER, pkt[4])] = time.monotonic()

        # Matching echo within window is suppressed
        tr._handle_notification(pkt)
        self.assertEqual(observed, [])

        # Subsequent genuine physical fader move on ch2 updates observed callback
        pkt2 = encode_fader_command(2, 80)
        tr._handle_notification(pkt2)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], "ch2.fader")
        self.assertEqual(observed[0][1], 80)

        # Auth ack marks authenticated
        tr._handle_notification(build_ble_packet(PKT_AUTH_ACK))
        self.assertTrue(tr.is_connected or tr.status_snapshot()["authenticated"])

    def test_service_and_hub_transport_mode_switching(self):
        svc = Flow8Service(auto_connect=False)
        self.assertEqual(svc.transport_mode, "usb_midi")

        with mock.patch("flow8.ble_transport.BleTransport.start", return_value=True) as mock_start, \
             mock.patch("flow8.ble_transport.BleTransport.stop") as mock_stop:
            self.assertEqual(svc.set_transport_mode("hybrid"), "hybrid")
            self.assertEqual(svc.transport_mode, "hybrid")
            mock_start.assert_called_once()

            # Incoming BLE observation records OBSERVED provenance in state_store
            svc._on_ble_parameter("ch1.fader", 92)
            st = svc.state_store.get_parameter("ch1.fader")
            self.assertEqual(st.provenance, ParameterProvenance.OBSERVED)
            self.assertEqual(st.observed_raw_midi, 92)

            self.assertEqual(svc.set_transport_mode("usb_midi"), "usb_midi")
            mock_stop.assert_called_once()

        with self.assertRaises(ValueError):
            svc.set_transport_mode("invalid_mode")

    def test_lan_hub_set_transport_mode_action(self):
        svc = Flow8Service(auto_connect=False)
        hub = Flow8LanHub(svc, port=0)
        hub.start()
        self.addCleanup(hub.stop)
        with mock.patch("flow8.ble_transport.BleTransport.start", return_value=True):
            req = urllib.request.Request(
                f"http://127.0.0.1:{hub.port}/api/action",
                data=json.dumps({"action": "setTransportMode", "mode": "ble"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read().decode())
            self.assertTrue(body["ok"])
            self.assertEqual(body["transportMode"], "ble")

            with urllib.request.urlopen(f"http://127.0.0.1:{hub.port}/api/status", timeout=3) as resp:
                status = json.loads(resp.read().decode())
            self.assertEqual(status["transportMode"], "ble")
            self.assertIn("ble", status)
        svc.disconnect()


if __name__ == "__main__":
    unittest.main()
