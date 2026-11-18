"""
Allowlist integrity, boundary enforcement, and dispatch-transaction tests
(Phase C.2 sections 3 and 6).

Covers:
- structural self-validation of the allowlist (channel/CC scope, bounds,
  parameter identity, uniqueness of the (channel, CC) pair)
- per-entry minimum/maximum enforcement, including below/above boundaries
- dispatch failure must NOT be reported or recorded as successful
- offline acceptance must be distinguishable from driver dispatch
"""

import unittest
from unittest.mock import MagicMock
from ctypes import wintypes

from flow8.midi_out import Flow8MidiOut, Flow8ValidationError, Flow8MidiError
from flow8.midi_constants import WinMmError
from flow8.state_model import Flow8StateStore, SyncStatus, VerificationLevel
from flow8.command_boundary import (
    Flow8CommandBoundary,
    Flow8CommandError,
    Flow8CommandRejectedError,
    DispatchStatus,
    _expected_channel_for_param,
)


def make_boundary(connected: bool = False):
    out = Flow8MidiOut()
    mock = MagicMock()
    out._winmm = mock
    if connected:
        out._is_open = True
        out._handle = wintypes.HANDLE(0x1234)
        mock.midiOutShortMsg.return_value = WinMmError.MMSYSERR_NOERROR
    store = Flow8StateStore()
    return Flow8CommandBoundary(out, store), store, mock, out


class TestAllowlistStructure(unittest.TestCase):
    def test_channel_and_cc_scope(self):
        for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
            with self.subTest(param=param_id):
                self.assertGreaterEqual(spec["channel"], 1)
                self.assertLessEqual(spec["channel"], 16)
                self.assertGreaterEqual(spec["cc"], 0)
                self.assertLessEqual(spec["cc"], 127)

    def test_bounds_are_ordered_and_within_midi_domain(self):
        for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
            with self.subTest(param=param_id):
                self.assertLessEqual(spec["min"], spec["max"])
                self.assertGreaterEqual(spec["min"], 0)
                self.assertLessEqual(spec["max"], 127)

    def test_parameter_identity_matches_declared_channel(self):
        for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
            with self.subTest(param=param_id):
                self.assertEqual(
                    _expected_channel_for_param(param_id), spec["channel"]
                )

    def test_no_duplicate_channel_cc_pairs(self):
        seen = {}
        for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
            pair = (spec["channel"], spec["cc"])
            with self.subTest(pair=pair):
                self.assertNotIn(pair, seen, f"{param_id} collides with {seen.get(pair)}")
            seen[pair] = param_id

    def test_every_parameter_has_a_state_record(self):
        store = Flow8StateStore()
        for param_id in Flow8CommandBoundary.ACTIVE_ALLOWLIST:
            with self.subTest(param=param_id):
                self.assertIsNotNone(store.get_parameter(param_id))


class TestAllowlistBoundsEnforcement(unittest.TestCase):
    def test_every_entry_enforces_min_and_max(self):
        for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
            with self.subTest(param=param_id):
                boundary, _, _, _ = make_boundary()

                if spec.get("boolean"):
                    # Booleans accept only a genuine 0/1 and encode to 0/127.
                    for good in (0, 1, True, False):
                        self.assertTrue(boundary.execute_command(param_id, good).success)
                    for bad in (-1, 2, 5, 128):
                        with self.assertRaises(Flow8ValidationError):
                            boundary.execute_command(param_id, bad)
                else:
                    for good in (spec["min"], spec["max"]):
                        self.assertTrue(boundary.execute_command(param_id, good).success)
                    for bad in (spec["min"] - 1, spec["max"] + 1):
                        with self.assertRaises(Flow8ValidationError):
                            boundary.execute_command(param_id, bad)

    def test_named_boundary_cases(self):
        boundary, _, _, _ = make_boundary()
        # at minimum
        self.assertEqual(boundary.execute_command("ch1.fader", 0).raw_midi_prepared, 0)
        # at maximum
        self.assertEqual(boundary.execute_command("ch1.fader", 127).raw_midi_prepared, 127)
        # below minimum
        with self.assertRaises(Flow8ValidationError):
            boundary.execute_command("ch1.fader", -1)
        # above maximum
        with self.assertRaises(Flow8ValidationError):
            boundary.execute_command("ch1.fader", 128)

    def test_boolean_parameter_rejects_non_boolean(self):
        boundary, _, _, _ = make_boundary()
        with self.assertRaises(Flow8ValidationError):
            boundary.execute_command("ch1.mute", 64)
        entry = boundary.execute_command("ch1.mute", True)
        self.assertEqual(entry.raw_midi_prepared, 127)


class TestCapabilityScope(unittest.TestCase):
    def test_gain_low_cut_compressor_scope(self):
        boundary, _, _, _ = make_boundary()
        for param in ("gain", "low_cut", "compressor"):
            for ch in (1, 2, 3, 4):
                with self.subTest(param=param, ch=ch):
                    self.assertIn(f"ch{ch}.{param}", boundary.allowlist)
            for ch in (5, 6, 7):
                with self.subTest(param=param, ch=ch):
                    self.assertNotIn(f"ch{ch}.{param}", boundary.allowlist)
                    with self.assertRaises(Flow8CommandRejectedError):
                        boundary.execute_command(f"ch{ch}.{param}", 0)

    def test_phantom_scope(self):
        boundary, _, _, _ = make_boundary()
        for ch in (1, 2):
            self.assertIn(f"ch{ch}.phantom", boundary.allowlist)
        for ch in (3, 4, 5, 6, 7):
            with self.subTest(ch=ch):
                with self.assertRaises(Flow8CommandRejectedError):
                    boundary.execute_command(f"ch{ch}.phantom", True)

    def test_comparator_unknown_not_available(self):
        boundary, _, _, _ = make_boundary()
        self.assertNotIn("ch5.compressor", boundary.allowlist)
        self.assertNotIn("ch6.compressor", boundary.allowlist)

    def test_out_of_range_channel_and_bus_rejected(self):
        boundary, _, _, _ = make_boundary()
        for param_id in ("ch0.fader", "ch8.fader", "ch9.fader", "unknown.fader"):
            with self.subTest(param=param_id):
                with self.assertRaises(Flow8CommandRejectedError):
                    boundary.execute_command(param_id, 64)


class TestDispatchTransaction(unittest.TestCase):
    def test_offline_is_accepted_but_not_dispatched(self):
        boundary, store, mock, _ = make_boundary(connected=False)
        entry = boundary.execute_command("ch1.fader", 50)
        self.assertEqual(entry.dispatch_status, DispatchStatus.ACCEPTED_OFFLINE)
        self.assertTrue(entry.command_accepted)
        self.assertFalse(entry.driver_dispatched)
        self.assertFalse(entry.dispatched_to_hardware)
        self.assertIsNone(entry.raw_midi_sent)
        self.assertEqual(entry.raw_midi_prepared, 50)
        self.assertIsNone(entry.hardware_applied)
        mock.midiOutShortMsg.assert_not_called()
        self.assertEqual(store.get_parameter("ch1.fader").commanded_value, 50)
        self.assertEqual(
            store.get_parameter("ch1.fader").sync_status, SyncStatus.PENDING_DISPATCH
        )

    def test_driver_dispatch_is_not_hardware_application(self):
        boundary, _, mock, _ = make_boundary(connected=True)
        entry = boundary.execute_command("ch1.fader", 50)
        self.assertEqual(entry.dispatch_status, DispatchStatus.DRIVER_DISPATCHED)
        self.assertTrue(entry.driver_dispatched)
        self.assertEqual(entry.raw_midi_sent, 50)
        # Unknown until an observation channel exists:
        self.assertIsNone(entry.hardware_applied)
        mock.midiOutShortMsg.assert_called_once()

    def test_failed_dispatch_does_not_commit_commanded_state(self):
        boundary, store, mock, _ = make_boundary(connected=True)
        mock.midiOutShortMsg.return_value = WinMmError.MMSYSERR_ERROR
        before = store.get_parameter("ch1.fader").commanded_value

        with self.assertRaises(Flow8CommandError) as ctx:
            boundary.execute_command("ch1.fader", 50)

        # The raised error names the failure explicitly.
        self.assertIn("hardware dispatch failed", str(ctx.exception).lower())

        after = store.get_parameter("ch1.fader")
        self.assertEqual(after.commanded_value, before)
        self.assertEqual(after.sync_status, SyncStatus.UNKNOWN)

        entry = boundary.command_log[-1]
        self.assertFalse(entry.success)
        self.assertTrue(entry.command_accepted)
        self.assertFalse(entry.driver_dispatched)
        self.assertFalse(entry.dispatched_to_hardware)
        self.assertEqual(entry.dispatch_status, DispatchStatus.DISPATCH_FAILED)
        # Nothing was sent, so no bytes may be claimed as sent...
        self.assertIsNone(entry.raw_midi_sent)
        # ...but the prepared value and the error are retained for troubleshooting.
        self.assertEqual(entry.raw_midi_prepared, 50)
        # error_message preserves the underlying transport error verbatim.
        self.assertIn("failed to send midi cc", entry.error_message.lower())

    def test_disconnection_failure_is_recorded_and_raises(self):
        boundary, store, mock, out = make_boundary(connected=True)
        mock.midiOutShortMsg.return_value = WinMmError.MMSYSERR_INVALHANDLE
        before = store.get_parameter("ch1.fader").commanded_value

        with self.assertRaises(Flow8CommandError):
            boundary.execute_command("ch1.fader", 50)

        # send_cc closed the endpoint on this error.
        self.assertFalse(out.is_connected)
        self.assertEqual(store.get_parameter("ch1.fader").commanded_value, before)
        entry = boundary.command_log[-1]
        self.assertEqual(entry.dispatch_status, DispatchStatus.DISPATCH_FAILED)
        self.assertIsNone(entry.raw_midi_sent)

    def test_rejection_is_logged_without_dispatch(self):
        boundary, _, mock, _ = make_boundary(connected=True)
        with self.assertRaises(Flow8CommandRejectedError):
            boundary.execute_command("ch5.gain", 10)
        entry = boundary.command_log[-1]
        self.assertEqual(entry.dispatch_status, DispatchStatus.REJECTED)
        self.assertFalse(entry.command_accepted)
        self.assertFalse(entry.driver_dispatched)
        self.assertIsNone(entry.raw_midi_sent)
        self.assertIsNone(entry.raw_midi_prepared)
        mock.midiOutShortMsg.assert_not_called()

    def test_validation_failure_is_logged_without_dispatch(self):
        boundary, _, mock, _ = make_boundary(connected=True)
        with self.assertRaises(Flow8ValidationError):
            boundary.execute_command("ch1.fader", 999)
        entry = boundary.command_log[-1]
        self.assertEqual(entry.dispatch_status, DispatchStatus.VALIDATION_FAILED)
        self.assertFalse(entry.command_accepted)
        self.assertIsNone(entry.raw_midi_sent)
        mock.midiOutShortMsg.assert_not_called()

    def test_log_entry_reports_state_and_verification_level(self):
        boundary, _, _, _ = make_boundary(connected=True)
        entry = boundary.execute_command("ch1.fader", 50)
        self.assertIsNone(entry.observed_value)
        self.assertEqual(entry.verification_level, VerificationLevel.UNKNOWN)

    def test_latency_is_host_side_only(self):
        boundary, _, _, _ = make_boundary(connected=True)
        entry = boundary.execute_command("ch1.fader", 50)
        self.assertGreaterEqual(entry.latency_us, 0.0)
        # A host-side measurement cannot legitimately exceed one second.
        self.assertLess(entry.latency_us, 1_000_000.0)


if __name__ == '__main__':
    unittest.main()
