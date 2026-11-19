"""USB diagnosis: which MIDI Out names Windows lists, and why FLOW 8 is not usable.

Read-only. A stubbed WinMM stands in for the driver; nothing is sent to a mixer.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from flow8.midi_constants import WinMmError
from flow8.midi_out import Flow8MidiOut, diagnose_usb
from flow8.service import Flow8Service


def _winmm_with(names):
    """A stub WinMM whose MIDI Out devices have the given names."""
    winmm = MagicMock()
    winmm.midiOutGetNumDevs.return_value = len(names)

    def caps(index, ref, size):
        ref._obj.szPname = names[index]
        return WinMmError.MMSYSERR_NOERROR

    winmm.midiOutGetDevCapsW.side_effect = caps
    return winmm


class ListDeviceNamesTests(unittest.TestCase):
    def test_list_device_names_returns_every_name(self):
        engine = Flow8MidiOut()
        engine._winmm = _winmm_with(["Microsoft GS Wavetable Synth", "FLOW 8 MIDI OUT [0]"])
        self.assertEqual(engine.list_device_names(),
                         ["Microsoft GS Wavetable Synth", "FLOW 8 MIDI OUT [0]"])

    def test_list_device_names_empty_when_no_devices(self):
        engine = Flow8MidiOut()
        engine._winmm = _winmm_with([])
        self.assertEqual(engine.list_device_names(), [])

    def test_list_device_names_never_raises_without_winmm(self):
        engine = Flow8MidiOut()
        engine._winmm = None
        self.assertEqual(engine.list_device_names(), [])

    def test_list_device_names_never_raises_when_driver_throws(self):
        engine = Flow8MidiOut()
        engine._winmm = MagicMock()
        engine._winmm.midiOutGetNumDevs.side_effect = OSError("driver gone")
        self.assertEqual(engine.list_device_names(), [])


class DiagnoseUsbTests(unittest.TestCase):
    def test_connected(self):
        self.assertEqual(diagnose_usb(True, ["FLOW 8 MIDI OUT [0]"], "FLOW 8 MIDI OUT", None), "connected")

    def test_no_midi_devices(self):
        self.assertEqual(diagnose_usb(False, [], "FLOW 8 MIDI OUT", "x"), "no_midi_devices")

    def test_flow8_not_listed(self):
        self.assertEqual(
            diagnose_usb(False, ["Microsoft GS Wavetable Synth"], "FLOW 8 MIDI OUT", "x"),
            "flow8_not_listed")

    def test_listed_but_not_open_is_open_failed(self):
        self.assertEqual(
            diagnose_usb(False, ["FLOW 8 MIDI OUT [0]"], "FLOW 8 MIDI OUT", "busy"),
            "open_failed")


class ServiceSnapshotTests(unittest.TestCase):
    def test_snapshot_names_what_was_seen_when_flow8_missing(self):
        svc = Flow8Service(auto_connect=False)
        svc.midi_out.list_device_names = lambda: ["Microsoft GS Wavetable Synth"]
        usb = svc.transport_status()["usb"]
        self.assertEqual(usb["diagnosis"], "flow8_not_listed")
        self.assertEqual(usb["devicesSeen"], ["Microsoft GS Wavetable Synth"])


if __name__ == "__main__":
    unittest.main()
