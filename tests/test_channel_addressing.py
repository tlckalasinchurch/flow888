"""
Regression tests for logical-strip -> MIDI-channel addressing (Phase C.2 sec. 4).

The defect under test: strip index N is NOT input number N. `ch6` addresses the
Channel 7/8 stereo pair, and `ch7` addresses the USB/BT return, which has no
connector at all. These tests pin the mapping so no member of the chain (domain
model -> allowlist -> boundary -> status byte) can drift.
"""

import unittest
from unittest.mock import MagicMock
from ctypes import wintypes

from flow8.domain_model import (
    LOGICAL_CHANNELS,
    LOGICAL_CHANNEL_BY_MIDI_CHANNEL,
    logical_channel_for_connector,
    ChannelKind,
)
from flow8.midi_out import Flow8MidiOut, Flow8ValidationError
from flow8.midi_constants import WinMmError
from flow8.state_model import Flow8StateStore
from flow8.command_boundary import Flow8CommandBoundary
from flow8.parameter_engine import Flow8ParameterEngine


def packed(channel: int, cc: int, value: int) -> int:
    return (0xB0 | (channel - 1)) | (cc << 8) | (value << 16)


class TestStripIdentity(unittest.TestCase):
    """The domain model is the single source of truth for strip -> MIDI channel."""

    def test_every_strip_declares_its_own_midi_channel(self):
        for idx in range(1, 8):
            self.assertEqual(LOGICAL_CHANNELS[idx].midi_channel, idx)

    def test_reverse_index_is_consistent(self):
        for idx in range(1, 8):
            self.assertEqual(LOGICAL_CHANNEL_BY_MIDI_CHANNEL[idx], idx)

    def test_strip_6_is_the_7_8_pair_not_input_6(self):
        strip6 = LOGICAL_CHANNELS[6]
        self.assertEqual(strip6.name, "Channel 7/8")
        self.assertEqual(strip6.midi_channel, 6)
        self.assertEqual(strip6.physical_connectors, ("IN_7L", "IN_8R"))
        # Input 6 belongs to strip 5, never to strip 6.
        self.assertNotIn("IN_6R", strip6.physical_connectors)

    def test_strip_5_is_the_5_6_pair(self):
        strip5 = LOGICAL_CHANNELS[5]
        self.assertEqual(strip5.midi_channel, 5)
        self.assertEqual(strip5.kind, ChannelKind.STEREO_INPUT)
        self.assertEqual(strip5.physical_connectors, ("IN_5L", "IN_6R"))

    def test_strip_7_is_the_usb_bt_return(self):
        strip7 = LOGICAL_CHANNELS[7]
        self.assertEqual(strip7.midi_channel, 7)
        self.assertEqual(strip7.kind, ChannelKind.STEREO_RETURN)
        self.assertEqual(strip7.physical_connectors, ("USB_PORT",))

    def test_connector_resolution_table(self):
        cases = {
            "IN_1": 1, "IN_2": 2, "IN_3": 3, "IN_4": 4,
            "IN_5L": 5, "IN_6R": 5,
            "IN_7L": 6, "IN_8R": 6,
            "USB_PORT": 7,
        }
        for connector, idx in cases.items():
            with self.subTest(connector=connector):
                self.assertEqual(logical_channel_for_connector(connector), idx)

        self.assertIsNone(logical_channel_for_connector("NO_SUCH_INPUT"))


class TestAllowlistIdentity(unittest.TestCase):
    """Every allowlist entry's MIDI channel must match its parameter identity."""

    def test_channel_params_carry_the_domain_midi_channel(self):
        al = Flow8CommandBoundary.ACTIVE_ALLOWLIST
        for idx in range(1, 8):
            with self.subTest(strip=idx):
                self.assertEqual(
                    al[f"ch{idx}.fader"]["channel"],
                    LOGICAL_CHANNELS[idx].midi_channel,
                )

    def test_bus_params_carry_their_bus_channel(self):
        al = Flow8CommandBoundary.ACTIVE_ALLOWLIST
        expected = {"main": 8, "mon1": 9, "mon2": 10, "fx1": 11, "fx2": 12}
        for bus_id, channel in expected.items():
            with self.subTest(bus=bus_id):
                self.assertEqual(al[f"{bus_id}.fader"]["channel"], channel)

    def test_ch6_never_addresses_channel_5_or_7(self):
        al = Flow8CommandBoundary.ACTIVE_ALLOWLIST
        for param_id, spec in al.items():
            if param_id.startswith("ch6."):
                self.assertEqual(spec["channel"], 6, param_id)


class TestChannelStatusBytes(unittest.TestCase):
    """Byte-level: each strip must produce its own status byte."""

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

    def test_status_byte_per_input_strip(self):
        for idx in range(1, 8):
            with self.subTest(strip=idx):
                self.mock.midiOutShortMsg.reset_mock()
                self.out.send_cc(idx, 7, 64)
                self.mock.midiOutShortMsg.assert_called_once_with(
                    self.out._handle, packed(idx, 7, 64)
                )

    def test_literal_channel_status_bytes(self):
        expected = {
            1: 0x4007B0, 2: 0x4007B1, 3: 0x4007B2, 4: 0x4007B3,
            5: 0x4007B4, 6: 0x4007B5, 7: 0x4007B6,
        }
        for channel, message in expected.items():
            with self.subTest(channel=channel):
                self.out.send_cc(channel, 7, 64)
                self.mock.midiOutShortMsg.assert_called_with(self.out._handle, message)

    def test_ch6_fader_reaches_midi_channel_6(self):
        entry = self.engine.channel(6).set_fader(64)
        self.assertTrue(entry.driver_dispatched)
        self.assertEqual(entry.raw_midi_sent, 64)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x4007B5)

    def test_ch5_and_ch6_are_distinct_channels(self):
        self.engine.channel(5).set_fader(64)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x4007B4)
        self.engine.channel(6).set_fader(64)
        self.mock.midiOutShortMsg.assert_called_with(self.out._handle, 0x4007B5)

    def test_all_seven_strips_are_distinct(self):
        seen = {}
        for idx in range(1, 8):
            seen[self.engine.channel(idx).kind] = seen.get(self.engine.channel(idx).kind, 0) + 1
        # 4 mono + 2 stereo pairs + 1 stereo return
        self.assertEqual(seen[ChannelKind.MONO_INPUT], 4)
        self.assertEqual(seen[ChannelKind.STEREO_INPUT], 2)
        self.assertEqual(seen[ChannelKind.STEREO_RETURN], 1)


class TestPhysicalInputResolution(unittest.TestCase):
    """UI-facing resolution: inputs -> strips, without index arithmetic."""

    def setUp(self):
        store = Flow8StateStore()
        self.engine = Flow8ParameterEngine(
            Flow8CommandBoundary(Flow8MidiOut(), store), store
        )

    def test_resolves_inputs_to_the_correct_strip(self):
        cases = {
            "IN_1": 1, "IN_2": 2, "IN_3": 3, "IN_4": 4,
            "IN_5L": 5, "IN_6R": 5,
            "IN_7L": 6, "IN_8R": 6,
            "USB_PORT": 7,
        }
        for connector, idx in cases.items():
            with self.subTest(connector=connector):
                strip = self.engine.channel_for_physical_input(connector)
                self.assertEqual(strip.channel_index, idx)

    def test_unknown_connector_rejected(self):
        with self.assertRaises(Flow8ValidationError):
            self.engine.channel_for_physical_input("IN_99")

    def test_known_but_unmapped_connector_rejected(self):
        # Footswitch is a real connector with no mixer channel strip.
        with self.assertRaises(Flow8ValidationError):
            self.engine.channel_for_physical_input("FOOTSWITCH")


class TestStereoBalanceVersusPan(unittest.TestCase):
    """Balance must not be silently applied as a mono pan law."""

    def setUp(self):
        store = Flow8StateStore()
        self.engine = Flow8ParameterEngine(
            Flow8CommandBoundary(Flow8MidiOut(), store), store
        )

    def test_stereo_strips_accept_balance(self):
        for idx in (5, 6, 7):
            with self.subTest(strip=idx):
                entry = self.engine.channel(idx).set_balance(64)
                self.assertTrue(entry.success)
                self.assertEqual(entry.raw_midi_sent, None)  # offline
                self.assertEqual(entry.raw_midi_prepared, 64)

    def test_mono_strips_reject_balance(self):
        for idx in (1, 2, 3, 4):
            with self.subTest(strip=idx):
                with self.assertRaises(Flow8ValidationError):
                    self.engine.channel(idx).set_balance(64)

    def test_stereo_state_label_is_balance(self):
        store = Flow8StateStore()
        for idx in (5, 6, 7):
            with self.subTest(strip=idx):
                self.assertEqual(
                    store.get_parameter(f"ch{idx}.pan").parameter_name, "balance"
                )
        for idx in (1, 2, 3, 4):
            with self.subTest(strip=idx):
                self.assertEqual(
                    store.get_parameter(f"ch{idx}.pan").parameter_name, "pan"
                )


if __name__ == '__main__':
    unittest.main()
