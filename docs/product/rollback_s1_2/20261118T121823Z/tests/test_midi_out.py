"""
Unit tests for Flow8MidiOut.
Mocks WinMM functions to test parameter validation, byte packing, lifecycle,
disconnection handling, and error handling without requiring hardware.
"""

import unittest
from unittest.mock import MagicMock, patch
import ctypes
from ctypes import wintypes

from flow8.midi_out import (
    Flow8MidiOut,
    Flow8ValidationError,
    Flow8NotConnectedError,
    Flow8DeviceBusyError,
    Flow8MidiError,
    MIDIOUTCAPSW,
)
from flow8.midi_constants import WinMmError

class TestFlow8MidiOut(unittest.TestCase):

    def setUp(self):
        self.mock_winmm = MagicMock()
        self.engine = Flow8MidiOut()
        self.engine._winmm = self.mock_winmm

    def test_send_when_disconnected_raises_error(self):
        with self.assertRaises(Flow8NotConnectedError):
            self.engine.send_cc(8, 7, 100)

    def test_invalid_channel_validation(self):
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(0, 7, 64)
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(17, 7, 64)

    def test_invalid_cc_number_validation(self):
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(8, -1, 64)
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(8, 128, 64)

    def test_invalid_value_validation(self):
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(8, 7, -1)
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(8, 7, 128)

    def test_unverified_parameter_rejected(self):
        # Channel 13 is reserved/unsupported on FLOW 8
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(13, 7, 64)
        # Channel 5 CC 8 (Preamp Gain) is physically unsupported on Line 5/6
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(5, 8, 64)
        # Channel 7 CC 11 (Compressor) is physically unsupported on USB/BT Return
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(7, 11, 64)
        # Channel 3 CC 12 (Phantom Power) is physically unsupported on Ch 3/4
        with self.assertRaises(Flow8ValidationError):
            self.engine.send_cc(3, 12, 64)

    def test_byte_encoding_and_dispatch(self):
        # Simulate open device
        self.engine._is_open = True
        dummy_handle = wintypes.HANDLE(0x1234)
        self.engine._handle = dummy_handle
        self.mock_winmm.midiOutShortMsg.return_value = WinMmError.MMSYSERR_NOERROR

        # Test Main Fader: Ch 8 (status 0xB7), CC 7, Val 100
        # Expected DWORD: 0xB7 | (7 << 8) | (100 << 16) = 0xB7 | 0x0700 | 0x640000 = 0x6407B7
        self.engine.set_main_fader(100)
        self.mock_winmm.midiOutShortMsg.assert_called_with(dummy_handle, 0x6407B7)

        # Test Ch 1 Fader: Ch 1 (status 0xB0), CC 7, Val 50
        # Expected DWORD: 0xB0 | (7 << 8) | (50 << 16) = 0xB0 | 0x0700 | 0x320000 = 0x3207B0
        self.engine.set_channel1_fader(50)
        self.mock_winmm.midiOutShortMsg.assert_called_with(dummy_handle, 0x3207B0)

        # Test Ch 1 Mute ON: Ch 1 (status 0xB0), CC 5, Val 127
        # Expected DWORD: 0xB0 | (5 << 8) | (127 << 16) = 0x7F05B0
        self.engine.set_channel1_mute(True)
        self.mock_winmm.midiOutShortMsg.assert_called_with(dummy_handle, 0x7F05B0)

        # Test Ch 1 Mute OFF: Ch 1 (status 0xB0), CC 5, Val 0
        # Expected DWORD: 0xB0 | (5 << 8) | (0 << 16) = 0x0005B0
        self.engine.set_channel1_mute(False)
        self.mock_winmm.midiOutShortMsg.assert_called_with(dummy_handle, 0x0005B0)

        # Test Ch 1 Pan Center: Ch 1 (status 0xB0), CC 10, Val 64
        # Expected DWORD: 0xB0 | (10 << 8) | (64 << 16) = 0x400AB0
        self.engine.set_channel1_pan(64)
        self.mock_winmm.midiOutShortMsg.assert_called_with(dummy_handle, 0x400AB0)

    def test_open_endpoint_allocation_error(self):
        self.mock_winmm.midiOutGetNumDevs.return_value = 1
        # Set dev caps to return FLOW 8
        def mock_get_caps(dev_id, p_caps, size):
            caps = ctypes.cast(p_caps, ctypes.POINTER(MIDIOUTCAPSW)).contents
            caps.szPname = "FLOW 8 MIDI OUT"
            return WinMmError.MMSYSERR_NOERROR
        self.mock_winmm.midiOutGetDevCapsW.side_effect = mock_get_caps
        self.mock_winmm.midiOutOpen.return_value = WinMmError.MMSYSERR_ALLOCATED

        with self.assertRaises(Flow8DeviceBusyError):
            self.engine.open()

    def test_open_endpoint_not_found(self):
        self.mock_winmm.midiOutGetNumDevs.return_value = 0
        with self.assertRaises(Flow8NotConnectedError):
            self.engine.open()

    def test_disconnection_during_dispatch(self):
        self.engine._is_open = True
        self.engine._handle = wintypes.HANDLE(0x1234)
        self.mock_winmm.midiOutShortMsg.return_value = WinMmError.MMSYSERR_INVALHANDLE

        with self.assertRaises(Flow8NotConnectedError):
            self.engine.set_main_fader(50)

        # Verify state reset
        self.assertFalse(self.engine.is_connected)

    def test_lifecycle_and_duplicate_handles(self):
        self.mock_winmm.midiOutGetNumDevs.return_value = 1
        def mock_get_caps(dev_id, p_caps, size):
            caps = ctypes.cast(p_caps, ctypes.POINTER(MIDIOUTCAPSW)).contents
            caps.szPname = "FLOW 8 MIDI OUT"
            return WinMmError.MMSYSERR_NOERROR
        self.mock_winmm.midiOutGetDevCapsW.side_effect = mock_get_caps
        self.mock_winmm.midiOutOpen.return_value = WinMmError.MMSYSERR_NOERROR

        # First open
        self.engine.open()
        self.assertTrue(self.engine.is_connected)

        # Second open without manual close should close previous handle first
        self.engine.open()
        self.assertTrue(self.engine.is_connected)
        self.assertEqual(self.mock_winmm.midiOutClose.call_count, 1)

        # Explicit close
        self.engine.close()
        self.assertFalse(self.engine.is_connected)
        self.assertEqual(self.mock_winmm.midiOutClose.call_count, 2)

if __name__ == '__main__':
    unittest.main()
