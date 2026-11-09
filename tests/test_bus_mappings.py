"""
Byte-level regression tests for the output-bus layer (Phase C.2 section 7).

Covers Main, Monitor 1, Monitor 2, FX 1 and FX 2: MIDI channel, CC number,
status byte, data value, invalid-address rejection, and CC collision protection.

No physical hardware is touched -- winmm is mocked, and every assertion is on the
exact 24-bit short message a real driver would have received.
"""

import unittest
from unittest.mock import MagicMock
from ctypes import wintypes

from flow8.midi_out import Flow8MidiOut, Flow8ValidationError
from flow8.midi_constants import WinMmError
from flow8.state_model import Flow8StateStore
from flow8.command_boundary import Flow8CommandBoundary, Flow8CommandRejectedError
from flow8.parameter_engine import Flow8ParameterEngine


def packed(channel: int, cc: int, value: int) -> int:
    """Reference encoder, written independently of midi_out's implementation."""
    return (0xB0 | (channel - 1)) | (cc << 8) | (value << 16)


class BusTestBase(unittest.TestCase):
    def setUp(self):
        self.out = Flow8MidiOut()
        self.mock = MagicMock()
        self.out._winmm = self.mock
        self.out._is_open = True
        self.out._handle = wintypes.HANDLE(0x1234)
        self.mock.midiOutShortMsg.return_value = WinMmError.MMSYSERR_NOERROR
        self.store = Flow8StateStore()
        self.boundary = Flow8CommandBoundary(self.out, self.store)
        self.engine = Flow8ParameterEngine(self.boundary, self.store)


class TestBusFaders(BusTestBase):
    CASES = (("main", 8), ("mon1", 9), ("mon2", 10), ("fx1", 11), ("fx2", 12))

    def test_bus_fader_channel_cc_and_value(self):
        for bus_id, channel in self.CASES:
            with self.subTest(bus=bus_id):
                self.mock.midiOutShortMsg.reset_mock()
                entry = self.engine.bus(bus_id).set_fader(100)
                self.assertTrue(entry.success)
                self.assertTrue(entry.driver_dispatched)
                self.assertEqual(entry.raw_midi_sent, 100)
                self.mock.midiOutShortMsg.assert_called_once_with(
                    self.out._handle, packed(channel, 7, 100)
                )

    def test_literal_status_bytes(self):
        # Literals, not the helper: a channel off-by-one cannot hide here.
        cases = (
            ("main", 0x6407B7), ("mon1", 0x6407B8), ("mon2", 0x6407B9),
            ("fx1", 0x6407BA), ("fx2", 0x6407BB),
        )
        for bus_id, message in cases:
            with self.subTest(bus=bus_id):
                self.engine.bus(bus_id).set_fader(100)
                self.mock.midiOutShortMsg.assert_called_with(self.out._handle, message)

    def test_value_endpoints(self):
        self.engine.set_main_fader(0)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x0007B7)
        self.engine.set_main_fader(127)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x7F07B7)

    def test_main_balance_is_cc10_on_channel_8(self):
        entry = self.engine.bus("main").set_balance(64)
        self.assertTrue(entry.success)
        self.assertEqual(entry.raw_midi_sent, 64)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x400AB7)

    def test_only_main_exposes_balance(self):
        for bus_id in ("mon1", "mon2", "fx1", "fx2"):
            with self.subTest(bus=bus_id):
                with self.assertRaises(Flow8ValidationError):
                    self.engine.bus(bus_id).set_balance(64)

    def test_bus_allowlist_contains_exactly_the_bus_parameters(self):
        bus_params = sorted(
            p for p in self.boundary.allowlist if not p.startswith("ch")
        )
        self.assertEqual(bus_params, [
            "fx1.fader", "fx2.fader", "main.balance",
            "main.fader", "mon1.fader", "mon2.fader",
        ])

    def test_bus_values_out_of_range_rejected(self):
        for value in (-1, 128):
            with self.subTest(value=value):
                with self.assertRaises(Flow8ValidationError):
                    self.engine.set_main_fader(value)


class TestBusInvalidAddresses(BusTestBase):
    def test_transport_gate_rejects_unsupported_bus_addresses(self):
        bad = (
            (8, 5),    # mute is not a bus parameter
            (9, 10),   # balance is MAIN only
            (10, 10),
            (11, 10),
            (12, 10),
            (11, 14),  # no sends on FX master channels
            (9, 20),   # beyond the 9-band GEQ range
            (13, 7),   # reserved channel
            (14, 1),   # FX engine parameters are not implemented
            (15, 1),
            (16, 7),
        )
        for channel, cc in bad:
            with self.subTest(channel=channel, cc=cc):
                with self.assertRaises(Flow8ValidationError):
                    self.out.send_cc(channel, cc, 64)

    def test_no_message_is_transmitted_for_a_rejected_address(self):
        with self.assertRaises(Flow8ValidationError):
            self.out.send_cc(13, 7, 64)
        self.mock.midiOutShortMsg.assert_not_called()

    def test_boundary_rejects_unimplemented_bus_parameters(self):
        for param_id in ("main.limiter", "main.geq_500", "mon1.geq_1k", "fx1.mute"):
            with self.subTest(param=param_id):
                with self.assertRaises(Flow8CommandRejectedError):
                    self.boundary.execute_command(param_id, 64)


class TestBusCcCollisionProtection(BusTestBase):
    """CC 14-17 are sends on ch 1-7 but GEQ bands on ch 8-10."""

    def test_same_cc_on_different_channels_encodes_differently(self):
        self.out.send_cc(1, 14, 45)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, packed(1, 14, 45))
        self.out.send_cc(8, 14, 45)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, packed(8, 14, 45))
        self.assertNotEqual(packed(1, 14, 45), packed(8, 14, 45))

    def test_literal_mon_send_vs_geq_500(self):
        # ch1 CC14 = Mon 1 send (0xB0), ch8 CC14 = GEQ 500 Hz (0xB7).
        self.out.send_cc(1, 14, 45)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x2D0EB0)
        self.out.send_cc(8, 14, 45)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x2D0EB7)

    def test_collision_is_resolved_by_the_boundary_too(self):
        # Bus GEQ is unreachable through the sanctioned path...
        with self.assertRaises(Flow8CommandRejectedError):
            self.boundary.execute_command("main.geq_500", 45)
        # ...while the per-channel send at the same CC is reachable.
        entry = self.engine.channel(1).set_send("mon1", 45)
        self.assertTrue(entry.driver_dispatched)
        self.assertEqual(entry.raw_midi_sent, 45)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x2D0EB0)

    def test_cc8_gain_versus_bus_limiter(self):
        # ch1 CC8 = preamp gain (allowed), ch8 CC8 = bus limiter (gate allows,
        # boundary does not expose).
        entry = self.engine.channel(1).set_gain(-20.0, unit="dB")
        self.assertEqual(entry.raw_midi_sent, 0)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x0008B0)
        self.out.send_cc(8, 8, 64)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x4008B7)
        with self.assertRaises(Flow8CommandRejectedError):
            self.boundary.execute_command("main.limiter", 64)

    def test_cc11_compressor_versus_main_geq(self):
        entry = self.engine.channel(1).set_compressor(50, unit="%")
        self.assertEqual(entry.raw_midi_sent, 50)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x320BB0)
        self.out.send_cc(8, 11, 50)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x320BB7)


if __name__ == '__main__':
    unittest.main()
