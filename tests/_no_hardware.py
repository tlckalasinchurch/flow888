"""Guard for safety tests: a physical MIDI port must never be opened.

Mix `NoHardwareMixin` into a TestCase. Opening either endpoint raises AssertionError.
Byte-level checks use `fake_open_port` in `_safety_helpers`, which has no real handle.
"""
from unittest import mock

from flow8.midi_in import Flow8MidiIn
from flow8.midi_out import Flow8MidiOut


class NoHardwareMixin:
    def setUp(self):
        super().setUp()
        for cls in (Flow8MidiOut, Flow8MidiIn):
            patcher = mock.patch.object(
                cls, "open", side_effect=AssertionError("physical port open attempted"))
            patcher.start()
            self.addCleanup(patcher.stop)
