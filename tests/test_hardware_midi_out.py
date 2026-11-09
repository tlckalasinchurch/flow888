"""
Physical hardware integration tests for the Behringer FLOW 8.

SAFETY MODEL (Phase C.2)
------------------------
These tests talk to real hardware, so they are OFF by default. Running
`python -m unittest discover -s tests -v` transmits NOTHING and reports every
class here as SKIPPED.

Two independent opt-in tiers, because "open the endpoint" and "change the mix"
are very different risks:

  FLOW8_HW_TESTS=1
      Tier 1: NON-MUTATING. Enumerates, opens, starts, stops and closes MIDI
      endpoints. Transmits no MIDI messages at all, so mixer state cannot change.

  FLOW8_HW_TESTS=1 FLOW8_HW_TESTS_MUTATE=1
      Tier 2: MUTATING. Sends Control Change messages that change mixer
      parameters. Read the notes on that class before enabling it.

No automatic restore is attempted anywhere in this file: the current mixer values
are never assumed to be known, and guessing a "restore" value would be worse than
leaving the state visible on the hardware.
"""

import os
import time
import unittest

from flow8.midi_out import Flow8MidiOut
from flow8.midi_in import Flow8MidiIn
from flow8.state_model import Flow8StateStore
from flow8.command_boundary import Flow8CommandBoundary
from flow8.parameter_engine import Flow8ParameterEngine

HW_OPT_IN_ENV = "FLOW8_HW_TESTS"
HW_MUTATE_ENV = "FLOW8_HW_TESTS_MUTATE"

HW_SKIP_REASON = (
    f"Physical hardware tests are disabled by default (nothing was transmitted). "
    f"Set {HW_OPT_IN_ENV}=1 for non-mutating endpoint tests. "
    f"Set {HW_OPT_IN_ENV}=1 and {HW_MUTATE_ENV}=1 to also enable MUTATING "
    f"parameter tests, which change mixer state and perform no restore."
)

MUTATE_SKIP_REASON = (
    f"MUTATING hardware tests are disabled (no MIDI parameter messages were sent). "
    f"Requires {HW_OPT_IN_ENV}=1 and {HW_MUTATE_ENV}=1. These tests change mixer "
    f"parameters and deliberately do NOT restore previous values."
)


def hardware_tests_enabled() -> bool:
    """True only when the operator explicitly opted in to touching hardware."""
    return os.environ.get(HW_OPT_IN_ENV, "").strip() == "1"


def mutating_tests_enabled() -> bool:
    """True only when the operator opted in to changing mixer parameters."""
    return hardware_tests_enabled() and os.environ.get(HW_MUTATE_ENV, "").strip() == "1"


@unittest.skipUnless(hardware_tests_enabled(), HW_SKIP_REASON)
class TestHardwareEndpointsNonMutating(unittest.TestCase):
    """
    REAL HARDWARE / NON-MUTATING.

    Enumerates and opens/closes the physical endpoints only. No CC, PC, note or
    SysEx message is transmitted, so no FLOW 8 parameter can change.
    """

    def setUp(self):
        self.out = Flow8MidiOut()
        if self.out.find_device_id() is None:
            self.skipTest("Physical FLOW 8 MIDI Out endpoint not detected.")

    def tearDown(self):
        if self.out.is_connected:
            self.out.close()

    def test_hardware_out_lifecycle(self):
        """Open, verify identity, close -- no messages transmitted."""
        self.out.open()
        self.assertTrue(self.out.is_connected)
        dev_id, dev_name = self.out.device_info
        self.assertIsNotNone(dev_id)
        self.assertIn("FLOW 8", dev_name)
        self.out.close()
        self.assertFalse(self.out.is_connected)

    def test_hardware_out_reconnect(self):
        """Open -> close -> open -> close cycles release handles cleanly."""
        self.out.open()
        self.assertTrue(self.out.is_connected)
        self.out.close()
        self.assertFalse(self.out.is_connected)
        self.out.open()
        self.assertTrue(self.out.is_connected)
        self.out.close()

    def test_hardware_out_context_manager(self):
        with Flow8MidiOut() as out:
            self.assertTrue(out.is_connected)
        self.assertFalse(out.is_connected)

    def test_hardware_in_lifecycle(self):
        """Open/start/stop/close the listener. Asserts no received events claimed."""
        listener = Flow8MidiIn()
        if listener.find_device_id() is None:
            self.skipTest("Physical FLOW 8 MIDI In endpoint not detected.")

        listener.open()
        self.assertTrue(listener.is_connected)
        listener.start()
        self.assertTrue(listener.is_listening)
        time.sleep(0.2)
        listener.stop()
        self.assertFalse(listener.is_listening)
        listener.close()
        self.assertFalse(listener.is_connected)


@unittest.skipUnless(mutating_tests_enabled(), MUTATE_SKIP_REASON)
class TestHardwareParameterDispatchMutating(unittest.TestCase):
    """
    REAL HARDWARE / MUTATING. Read this before enabling.

    What it deliberately does NOT do:
    - It never touches a fader (Main, Monitor or channel). A mistaken fader write
      can silence a live PA, and there is no way to restore a value we do not know.
    - It never enables +48V phantom power.
    - It never assumes or restores prior values.

    Every operation below is chosen to land on a NEUTRAL position, so the mixer
    ends in a sane state regardless of where it started:
      - ch1 pan     -> 64 (centre)
      - ch1 EQ low  -> 0.0 dB (flat, raw 64)
      - ch1 mute    -> ON then OFF (ends unmuted)

    What a pass actually proves: the Windows MIDI driver accepted the messages
    (midiOutShortMsg returned MMSYSERR_NOERROR). It does NOT prove USB
    transmission, that the mixer applied anything, or that the audio changed.
    `hardware_applied` is therefore asserted to stay None -- it stays unknown
    until an observation channel exists.
    """

    def setUp(self):
        self.out = Flow8MidiOut()
        if self.out.find_device_id() is None:
            self.skipTest("Physical FLOW 8 MIDI Out endpoint not detected.")

    def tearDown(self):
        if self.out.is_connected:
            self.out.close()

    def test_dispatch_is_api_acknowledgement_only(self):
        with Flow8MidiOut() as midi_out:
            store = Flow8StateStore()
            boundary = Flow8CommandBoundary(midi_out, store)
            engine = Flow8ParameterEngine(boundary, store)

            # Neutral pan: centre.
            entry_pan = engine.channel(1).set_pan(0.0, unit="%")
            self.assertTrue(entry_pan.success)
            self.assertEqual(entry_pan.raw_midi_sent, 64)
            self.assertTrue(entry_pan.driver_dispatched)
            # Not proof the mixer applied it:
            self.assertIsNone(entry_pan.hardware_applied)
            time.sleep(0.05)

            # Neutral EQ: flat.
            entry_eq = engine.channel(1).set_eq_band("low", 0.0, unit="dB")
            self.assertTrue(entry_eq.success)
            self.assertEqual(entry_eq.raw_midi_sent, 64)
            self.assertIsNone(entry_eq.hardware_applied)
            time.sleep(0.05)

            # Mute round-trip ends unmuted.
            entry_mute_on = engine.channel(1).set_mute(True)
            self.assertTrue(entry_mute_on.driver_dispatched)
            time.sleep(0.05)
            entry_mute_off = engine.channel(1).set_mute(False)
            self.assertTrue(entry_mute_off.driver_dispatched)
            time.sleep(0.05)

            log = boundary.command_log
            self.assertEqual(len(log), 4)
            self.assertTrue(all(e.driver_dispatched for e in log))
            self.assertTrue(all(e.hardware_applied is None for e in log))


if __name__ == '__main__':
    unittest.main()
