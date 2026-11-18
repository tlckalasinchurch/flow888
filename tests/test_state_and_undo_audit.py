"""
Stage 1 Regression & Correctness Tests: State Model Provenance & Undo/Redo Engine.

Covers all mandatory requirements:
- Explicit Parameter Provenance (UNSYNCED, COMMANDED, OBSERVED, DISPATCH_FAILED, UNSUPPORTED)
- Exact-value Undo / Redo (never neutral baseline assumptions)
- Unknown previous state treated as non-undoable
- Transaction ordering: undo in reverse order, redo in original order
- Partial dispatch failure and compensating rollback
- Invalidation / reconciliation upon disconnect and reconnect
"""

import unittest
from unittest import mock
from flow8.command_boundary import Flow8CommandBoundary, Flow8CommandError
from flow8.domain_model import LOGICAL_CHANNELS
from flow8.ledger import CommandLedger, CommandRecord
from flow8.midi_in import Flow8MidiIn
from flow8.midi_out import Flow8MidiOut
from flow8.parameter_engine import Flow8ParameterEngine
from flow8.service import Flow8Service
from flow8.state_model import (
    EventSource,
    Flow8StateStore,
    ParameterProvenance,
    SyncStatus,
    VerificationLevel,
)


class TestParameterProvenanceAndState(unittest.TestCase):
    def setUp(self):
        self.store = Flow8StateStore()

    def test_startup_provenance_is_unsynced(self):
        # All standard channel parameters must start as UNSYNCED
        ch1_fader = self.store.get_parameter("ch1.fader")
        self.assertEqual(ch1_fader.provenance, ParameterProvenance.UNSYNCED)
        self.assertEqual(ch1_fader.sync_status, SyncStatus.UNKNOWN)
        self.assertIsNone(ch1_fader.observed_value)

        ch1_eq = self.store.get_parameter("ch1.eq_low")
        self.assertEqual(ch1_eq.provenance, ParameterProvenance.UNSYNCED)

    def test_unsupported_parameters_marked_unsupported(self):
        # Stereo pair compressors on Ch 5 and 6 have no control address
        ch5_comp = self.store.get_parameter("ch5.compressor")
        self.assertEqual(ch5_comp.provenance, ParameterProvenance.UNSUPPORTED)

    def test_commanded_value_sets_provenance_commanded(self):
        param = self.store.set_commanded_value(
            "ch1.fader", 80, EventSource.LOCAL_HOST, raw_midi_value=80
        )
        self.assertEqual(param.provenance, ParameterProvenance.COMMANDED)
        self.assertEqual(param.commanded_raw_midi, 80)
        self.assertIsNone(param.observed_raw_midi)

    def test_observed_value_sets_provenance_observed(self):
        param = self.store.set_observed_value(
            "ch1.fader", 80, EventSource.PHYSICAL_HARDWARE, raw_midi_value=80
        )
        self.assertEqual(param.provenance, ParameterProvenance.OBSERVED)
        self.assertEqual(param.observed_raw_midi, 80)

    def test_dispatch_failed_sets_provenance_failed(self):
        param = self.store.set_dispatch_failed("ch1.fader")
        self.assertEqual(param.provenance, ParameterProvenance.DISPATCH_FAILED)

    def test_reconcile_reconnect_resets_provenance_to_unsynced(self):
        self.store.set_commanded_value("ch1.fader", 85, EventSource.LOCAL_HOST, 85)
        self.store.set_observed_value("ch1.pan", 64, EventSource.PHYSICAL_HARDWARE, 64)

        self.store.reconcile_reconnect()

        self.assertEqual(self.store.get_parameter("ch1.fader").provenance, ParameterProvenance.UNSYNCED)
        self.assertIsNone(self.store.get_parameter("ch1.fader").observed_raw_midi)
        self.assertEqual(self.store.get_parameter("ch1.pan").provenance, ParameterProvenance.UNSYNCED)


class TestExactValueUndoRedoAndOrdering(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def test_exact_value_undo_preserves_user_baseline_not_neutral(self):
        """
        Verify:
        Initial EQ = -3 dB (raw 51)
        Apply preset setting Low EQ to +1 dB (raw 68)
        Undo = -3 dB (raw 51)  [NOT 0 dB / raw 64!]
        Redo = +1 dB (raw 68)
        """
        # 1. Establish user-defined baseline on Channel 1
        self.service.set_eq_band(1, "low", -3.0, unit="dB")
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 51)

        # 2. Apply a preset that sets Low EQ to -1.0 dB
        # vocal-worship-ballad sets eq_low_db to -1.0 dB
        self.service.apply_channel_preset(1, "vocal-worship-ballad", preserve_levels=True)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_value, -1.0)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 60)

        # 3. Undo: MUST restore -3.0 dB (raw 51), NOT flat 0.0 dB (raw 64)
        undone = self.service.undo()
        self.assertGreater(len(undone), 0)
        restored_raw = self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi
        self.assertEqual(restored_raw, 51, "Undo must restore exact prior value (-3 dB / 51), never neutral 0 dB (64)")

        # 4. Redo: MUST re-apply preset value -1.0 dB (raw 60)
        redone = self.service.redo()
        self.assertGreater(len(redone), 0)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 60)

    def test_unknown_previous_state_is_non_undoable(self):
        """
        If a parameter has never been commanded or observed, its previous state
        is unknown. Applying a command must NOT create an undo record with a fake guess.
        """
        # Ensure fresh service with no commands
        fresh_service = Flow8Service(auto_connect=False)
        self.assertEqual(fresh_service.state_store.get_parameter("ch2.low_cut").provenance, ParameterProvenance.UNSYNCED)

        # Set low cut on previously untouched channel
        fresh_service.set_low_cut(2, 80.0, unit="Hz")

        # History should be empty because previous state was unknown
        self.assertFalse(fresh_service.ledger.can_undo)

        # But subsequent change DOES have a known previous state and IS undoable
        fresh_service.set_low_cut(2, 120.0, unit="Hz")
        self.assertTrue(fresh_service.ledger.can_undo)
        fresh_service.undo()
        # Restores 80.0 Hz (raw 13)
        self.assertEqual(fresh_service.state_store.get_parameter("ch2.low_cut").commanded_raw_midi, 13)

    def test_transaction_ordering_reverse_on_undo_forward_on_redo(self):
        """
        Commands A, B, C batched in transaction:
        Undo must execute C -> B -> A.
        Redo must execute A -> B -> C.
        """
        dispatched_order = []

        def executor(ptype, ch, val):
            dispatched_order.append((ptype, ch, val))

        ledger = CommandLedger(executor=executor)
        ledger.begin_batch()
        ledger.push(CommandRecord("fader", 1, previous_value=10, new_value=20, timestamp=None))
        ledger.push(CommandRecord("pan", 1, previous_value=64, new_value=80, timestamp=None))
        ledger.push(CommandRecord("mute", 1, previous_value=False, new_value=True, timestamp=None))
        committed = ledger.end_batch()
        self.assertEqual(committed, 3)

        # Execute Undo
        dispatched_order.clear()
        ledger.undo()
        expected_undo_order = [
            ("mute", 1, False),
            ("pan", 1, 64),
            ("fader", 1, 10),
        ]
        self.assertEqual(dispatched_order, expected_undo_order, "Undo must execute in reverse causal order")

        # Execute Redo
        dispatched_order.clear()
        ledger.redo()
        expected_redo_order = [
            ("fader", 1, 20),
            ("pan", 1, 80),
            ("mute", 1, True),
        ]
        self.assertEqual(dispatched_order, expected_redo_order, "Redo must execute in forward causal order")

    def test_partial_dispatch_failure_rolls_back_and_preserves_ledger(self):
        """
        If command 3 of 3 fails during undo, commands 1 and 2 must be
        compensated (rolled back) to their new_values so mixer does not stay half-undone.
        """
        dispatched = []

        def flaky_executor(ptype, ch, val):
            if ptype == "fader" and val == 10:  # Fail on the 3rd undo command
                raise Flow8CommandError("driver timeout on fader")
            dispatched.append((ptype, ch, val))

        ledger = CommandLedger(executor=flaky_executor)
        ledger.begin_batch()
        ledger.push(CommandRecord("fader", 1, previous_value=10, new_value=20, timestamp=None))
        ledger.push(CommandRecord("pan", 1, previous_value=64, new_value=80, timestamp=None))
        ledger.push(CommandRecord("mute", 1, previous_value=False, new_value=True, timestamp=None))
        ledger.end_batch()

        # Attempt undo
        with self.assertRaises(Flow8CommandError) as ctx:
            ledger.undo()

        self.assertIn("driver timeout on fader", str(ctx.exception))

        # Check compensation trace:
        # 1. Undone mute to False
        # 2. Undone pan to 64
        # 3. Fader failed
        # 4. Compensation: pan rolled back to 80 (new_value)
        # 5. Compensation: mute rolled back to True (new_value)
        expected_trace = [
            ("mute", 1, False),
            ("pan", 1, 64),
            ("pan", 1, 80),   # Compensating rollback
            ("mute", 1, True),  # Compensating rollback
        ]
        self.assertEqual(dispatched, expected_trace)

        # The failed transaction is STILL at the top of the undo stack, ready for retry!
        self.assertTrue(ledger.can_undo)

    def test_disconnect_reconnect_reconciliation(self):
        self.service.set_fader(1, 70)
        self.service.set_fader(1, 80)
        self.assertTrue(self.service.ledger.can_undo)

        # Call reconnect reconciliation
        self.service.reconcile_connection()

        # State provenance reset to UNSYNCED
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").provenance, ParameterProvenance.UNSYNCED)
        # Redo stack cleared
        self.assertFalse(self.service.ledger.can_redo)


if __name__ == "__main__":
    unittest.main()
