"""Unit tests for flow8/ble_transport.py codec, echo suppression, and service integration."""

import asyncio
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

    def test_connected_but_unauthenticated_is_not_ready(self):
        tr = BleTransport()
        tr._connected = True
        # GATT link up but no 0x36 ACK yet: not ready for control writes.
        self.assertFalse(tr.is_connected)
        self.assertFalse(tr.status_snapshot()["authenticated"])
        tr._handle_notification(build_ble_packet(PKT_AUTH_ACK))
        self.assertTrue(tr.is_connected)
        self.assertTrue(tr.status_snapshot()["authenticated"])

    def test_malformed_packets_are_dropped(self):
        observed = []
        tr = BleTransport(on_parameter=lambda pid, val: observed.append((pid, val)))
        good = encode_fader_command(1, 64)
        # Corrupt the checksum
        bad = bytearray(good)
        bad[-1] ^= 0xFF
        tr._handle_notification(bytes(bad))
        # Truncated packet
        tr._handle_notification(good[:3])
        # Empty
        tr._handle_notification(b"")
        self.assertEqual(observed, [])
        self.assertEqual(tr.status_snapshot()["packetsRx"], 3)
        # Sanity: the intact packet still decodes
        tr._handle_notification(good)
        self.assertEqual(len(observed), 1)

    def test_state_dump_chunks_counted_never_decoded(self):
        observed = []
        tr = BleTransport(on_parameter=lambda pid, val: observed.append((pid, val)))
        chunk = build_ble_packet(0x38, b"\x00" * 20)
        tr._handle_notification(chunk)
        tr._handle_notification(chunk)
        snap = tr.status_snapshot()
        self.assertEqual(snap["dumpChunks"], 2)
        self.assertEqual(snap["dumpBytes"], 2 * len(chunk))
        self.assertIsNotNone(snap["lastDumpAt"])
        self.assertEqual(observed, [])  # dump is observed, never applied as params

    def test_gatt_validation_requires_flow8_service_and_characteristic(self):
        from flow8.ble_transport import (
            FLOW8_DATA_CHAR_UUID,
            FLOW8_SERVICE_UUID,
            BleTransport,
        )

        class FakeChar:
            pass

        class FakeServices:
            def __init__(self, uuids, has_char):
                self._svcs = [mock.Mock(uuid=u) for u in uuids]
                self._has_char = has_char

            def __iter__(self):
                return iter(self._svcs)

            def get_characteristic(self, uuid):
                if self._has_char and uuid == FLOW8_DATA_CHAR_UUID:
                    return FakeChar()
                return None

        client = mock.Mock()
        client.services = FakeServices([FLOW8_SERVICE_UUID], has_char=True)
        BleTransport._require_flow8_gatt(client)  # must not raise

        client.services = FakeServices(["0000180f-0000-1000-8000-00805f9b34fb"], has_char=True)
        with self.assertRaises(RuntimeError):
            BleTransport._require_flow8_gatt(client)

        client.services = FakeServices([FLOW8_SERVICE_UUID], has_char=False)
        with self.assertRaises(RuntimeError):
            BleTransport._require_flow8_gatt(client)

    def test_write_packet_serializes_concurrent_writes(self):
        tr = BleTransport()
        order = []

        class FakeClient:
            is_connected = True

            async def write_gatt_char(self, uuid, payload, response=False):
                order.append(("start", payload[0]))
                await asyncio.sleep(0.01)
                order.append(("end", payload[0]))

        tr._client = FakeClient()

        async def run():
            await asyncio.gather(
                tr._write_packet(bytes([0x11, 0x01, 0x12])),
                tr._write_packet(bytes([0x22, 0x01, 0x23])),
                tr._write_packet(bytes([0x33, 0x01, 0x34])),
            )

        asyncio.run(run())
        # No interleaving: every "start" is followed by its "end" before the next start.
        starts = [i for i, (tag, _) in enumerate(order) if tag == "start"]
        ends = [i for i, (tag, _) in enumerate(order) if tag == "end"]
        self.assertEqual(len(starts), 3)
        for s, e in zip(starts, ends):
            self.assertEqual(e, s + 1)
        self.assertEqual(tr.status_snapshot()["packetsTx"], 3)

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
