"""
Unit and integration tests for Behringer FLOW 8 Parameter Engine.
Verifies channel strip topology constraints, bus control, strict command boundary dispatch,
offline vs online hardware dispatch flags, and parameter conversion.
"""

import unittest
from unittest.mock import MagicMock
from ctypes import wintypes

from flow8.midi_out import Flow8MidiOut, Flow8ValidationError
from flow8.midi_constants import WinMmError
from flow8.state_model import Flow8StateStore, SyncStatus, EventSource, VerificationLevel
from flow8.command_boundary import (
    Flow8CommandBoundary,
    Flow8CommandRejectedError,
    CommandLogEntry,
    DispatchStatus,
)
from flow8.parameter_engine import (
    Flow8ParameterEngine,
    Flow8ChannelStrip,
    Flow8BusStrip,
)
from flow8.domain_model import ChannelKind

class TestParameterEngine(unittest.TestCase):

    def setUp(self):
        self.mock_midi_out = Flow8MidiOut()
        self.state_store = Flow8StateStore()
        self.boundary = Flow8CommandBoundary(self.mock_midi_out, self.state_store)
        self.engine = Flow8ParameterEngine(self.boundary, self.state_store)

    # -----------------------------------------------------------------------
    # 1. Structure & Topology Validation
    # -----------------------------------------------------------------------

    def test_channel_strip_instantiation(self):
        for ch in range(1, 8):
            strip = self.engine.channel(ch)
            self.assertIsInstance(strip, Flow8ChannelStrip)
            self.assertEqual(strip.channel_index, ch)

        with self.assertRaises(Flow8ValidationError):
            self.engine.channel(0)

        with self.assertRaises(Flow8ValidationError):
            self.engine.channel(8)

    def test_bus_strip_instantiation(self):
        for bid in ("main", "mon1", "mon2", "fx1", "fx2"):
            bus = self.engine.bus(bid)
            self.assertIsInstance(bus, Flow8BusStrip)
            self.assertEqual(bus.bus_id, bid)

        with self.assertRaises(Flow8ValidationError):
            self.engine.bus("unknown_bus")

    # -----------------------------------------------------------------------
    # 2. Hardware Capability Enforcement
    # -----------------------------------------------------------------------

    def test_preamp_gain_channel_restrictions(self):
        # Ch 1-4 have analog preamp gain
        for ch in (1, 2, 3, 4):
            entry = self.engine.channel(ch).set_gain(20, unit="raw")
            self.assertTrue(entry.success)
            self.assertEqual(entry.raw_midi_prepared, 20)

        # Ch 5, 6, 7 do NOT have analog preamp gain
        for ch in (5, 6, 7):
            with self.assertRaises(Flow8ValidationError):
                self.engine.channel(ch).set_gain(20, unit="raw")

    def test_low_cut_channel_restrictions(self):
        # Ch 1-4 have low cut
        for ch in (1, 2, 3, 4):
            entry = self.engine.channel(ch).set_low_cut(80, unit="Hz")
            self.assertTrue(entry.success)

        # Ch 5, 6, 7 do NOT have low cut
        for ch in (5, 6, 7):
            with self.assertRaises(Flow8ValidationError):
                self.engine.channel(ch).set_low_cut(80, unit="Hz")

    def test_compressor_channel_restrictions(self):
        # Ch 1-4 have 1-knob compressor
        for ch in (1, 2, 3, 4):
            entry = self.engine.channel(ch).set_compressor(50, unit="%")
            self.assertTrue(entry.success)
            self.assertEqual(entry.raw_midi_prepared, 50)

        # Ch 5, 6, 7 do NOT have compressor
        for ch in (5, 6, 7):
            with self.assertRaises(Flow8ValidationError):
                self.engine.channel(ch).set_compressor(50, unit="%")

    def test_phantom_power_channel_restrictions(self):
        # Ch 1-2 have +48V phantom power
        entry1 = self.engine.channel(1).set_phantom(True)
        self.assertTrue(entry1.success)
        self.assertEqual(entry1.raw_midi_prepared, 127)

        entry2 = self.engine.channel(2).set_phantom(False)
        self.assertTrue(entry2.success)
        self.assertEqual(entry2.raw_midi_prepared, 0)

        # Ch 3-7 do NOT have phantom power
        for ch in (3, 4, 5, 6, 7):
            with self.assertRaises(Flow8ValidationError):
                self.engine.channel(ch).set_phantom(True)

    def test_bus_balance_restrictions(self):
        # Main bus has balance
        entry = self.engine.bus("main").set_balance(64)
        self.assertTrue(entry.success)
        self.assertEqual(entry.raw_midi_prepared, 64)

        # MON1, MON2, FX1, FX2 do not have balance
        for bid in ("mon1", "mon2", "fx1", "fx2"):
            with self.assertRaises(Flow8ValidationError):
                self.engine.bus(bid).set_balance(64)

    # -----------------------------------------------------------------------
    # 3. 4-Band EQ & Send Targets
    # -----------------------------------------------------------------------

    def test_4band_eq_all_input_channels(self):
        # All 7 input channels support 4-band EQ
        for ch in range(1, 8):
            strip = self.engine.channel(ch)
            for band in ("low", "low_mid", "hi_mid", "hi"):
                entry = strip.set_eq_band(band, 0.0, unit="dB")
                self.assertTrue(entry.success)
                self.assertEqual(entry.raw_midi_prepared, 64)

        # Invalid band name raises Flow8ValidationError
        with self.assertRaises(Flow8ValidationError):
            self.engine.channel(1).set_eq_band("sub_bass", 0.0)

    def test_auxiliary_sends_all_input_channels(self):
        # All 7 input channels support 4 sends (Mon 1, Mon 2, FX 1, FX 2)
        for ch in range(1, 8):
            strip = self.engine.channel(ch)
            for target in ("mon1", "mon2", "fx1", "fx2"):
                entry = strip.set_send(target, 45, unit="raw")
                self.assertTrue(entry.success)
                self.assertEqual(entry.raw_midi_prepared, 45)

        # Invalid send target raises Flow8ValidationError
        with self.assertRaises(Flow8ValidationError):
            self.engine.channel(1).set_send("aux5", 50)

    # -----------------------------------------------------------------------
    # 4. Strict Dispatch Path & Offline Flag
    # -----------------------------------------------------------------------

    def test_offline_dispatch_flag(self):
        # When mock_midi_out is disconnected (default in unit tests)
        entry = self.engine.channel(1).set_fader(75)
        # Accepted and processed, but nothing left the process.
        self.assertTrue(entry.success)
        self.assertTrue(entry.command_accepted)
        self.assertFalse(entry.dispatched_to_hardware)
        self.assertFalse(entry.driver_dispatched)
        # No observation channel exists, so application is unknown, not True.
        self.assertIsNone(entry.hardware_applied)
        # Phase C.2: raw_midi_sent means "bytes submitted to the driver".
        self.assertIsNone(entry.raw_midi_sent)
        self.assertEqual(entry.raw_midi_prepared, 75)
        self.assertEqual(entry.dispatch_status, DispatchStatus.ACCEPTED_OFFLINE)

        # State store is updated (commanded only; observation still absent)
        state = self.engine.get_state("ch1.fader")
        self.assertEqual(state.commanded_value, 75)
        self.assertEqual(state.raw_midi_value, 75)
        self.assertEqual(state.commanded_raw_midi, 75)
        self.assertIsNone(state.observed_value)
        self.assertEqual(state.sync_status, SyncStatus.PENDING_DISPATCH)

    def test_mocked_hardware_dispatch(self):
        # Mock winmm and simulate open device
        mock_winmm = MagicMock()
        mock_winmm.midiOutShortMsg.return_value = WinMmError.MMSYSERR_NOERROR
        self.mock_midi_out._winmm = mock_winmm
        self.mock_midi_out._is_open = True
        self.mock_midi_out._handle = wintypes.HANDLE(0x8888)

        # Dispatch Ch 1 EQ Low: status 0xB0, CC 1, Val 64 (0.0 dB)
        entry = self.engine.channel(1).set_eq_band("low", 0.0, unit="dB")
        self.assertTrue(entry.success)
        self.assertTrue(entry.dispatched_to_hardware)

        # Expected DWORD: 0xB0 | (1 << 8) | (64 << 16) = 0x4001B0
        mock_winmm.midiOutShortMsg.assert_called_with(self.mock_midi_out._handle, 0x4001B0)

        # Dispatch Main Fader: status 0xB7 (Ch 8), CC 7, Val 100
        entry_main = self.engine.set_main_fader(100)
        self.assertTrue(entry_main.success)
        self.assertTrue(entry_main.dispatched_to_hardware)
        # Expected DWORD: 0xB7 | (7 << 8) | (100 << 16) = 0x6407B7
        mock_winmm.midiOutShortMsg.assert_called_with(self.mock_midi_out._handle, 0x6407B7)

        # Phase C.2: driver dispatch is NOT hardware confirmation.
        self.assertTrue(entry_main.driver_dispatched)
        self.assertEqual(entry_main.dispatch_status, DispatchStatus.DRIVER_DISPATCHED)
        self.assertEqual(entry_main.raw_midi_sent, 100)
        self.assertIsNone(entry_main.hardware_applied)

    # -----------------------------------------------------------------------
    # 5. Engineering Unit Conversions
    # -----------------------------------------------------------------------

    def test_unit_conversions(self):
        strip = self.engine.channel(1)

        # Gain in dB (-20 dB -> 0, +60 dB -> 127)
        e1 = strip.set_gain(-20.0, unit="dB")
        self.assertEqual(e1.raw_midi_prepared, 0)
        e2 = strip.set_gain(60.0, unit="dB")
        self.assertEqual(e2.raw_midi_prepared, 127)

        # Low cut in Hz (20 Hz -> 0, 600 Hz -> 127)
        e3 = strip.set_low_cut(20.0, unit="Hz")
        self.assertEqual(e3.raw_midi_prepared, 0)
        e4 = strip.set_low_cut(600.0, unit="Hz")
        self.assertEqual(e4.raw_midi_prepared, 127)

        # Compressor in % (0% -> 0, 100% -> 100)
        e5 = strip.set_compressor(0.0, unit="%")
        self.assertEqual(e5.raw_midi_prepared, 0)
        e6 = strip.set_compressor(100.0, unit="%")
        self.assertEqual(e6.raw_midi_prepared, 100)

        # Pan in % (-100% -> 0, 0% -> 64, +100% -> 127)
        e7 = strip.set_pan(-100.0, unit="%")
        self.assertEqual(e7.raw_midi_prepared, 0)
        e8 = strip.set_pan(0.0, unit="%")
        self.assertEqual(e8.raw_midi_prepared, 64)
        e9 = strip.set_pan(100.0, unit="%")
        self.assertEqual(e9.raw_midi_prepared, 127)


if __name__ == '__main__':
    unittest.main()
