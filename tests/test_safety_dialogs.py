"""Tests for FLOW 8 UI.2-T4-02 safety gates and confirmation dialogs."""

import tkinter as tk
import unittest
from unittest import mock

from flow8.ui.safety_dialogs import (
    PhantomPowerSafetyGate,
    PhantomPowerConfirmationDialog,
    AnalogGainSafetyGate,
    PhantomPowerConfirmationToken,
)


class PhantomPowerSafetyGateTests(unittest.TestCase):
    def test_only_channels_1_and_2_are_allowed(self):
        self.assertTrue(PhantomPowerSafetyGate.validate_channel(1))
        self.assertTrue(PhantomPowerSafetyGate.validate_channel(2))
        for ch in [0, 3, 4, 5, 6, 7, 8, 9]:
            with self.assertRaises(ValueError) as ctx:
                PhantomPowerSafetyGate.validate_channel(ch)
            self.assertIn("physically restricted to Channels 1 and 2", str(ctx.exception))

    def test_valid_token_dispatches_once(self):
        token = PhantomPowerSafetyGate.issue_token(1)
        mock_service = mock.Mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, token)
        self.assertTrue(result)
        mock_service.set_phantom.assert_called_once_with(1, True)

    def test_legacy_positional_true_does_not_dispatch(self):
        mock_service = mock.Mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, True)
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()

    def test_legacy_keyword_confirmed_raises_typeerror(self):
        mock_service = mock.Mock()
        with self.assertRaises(TypeError):
            PhantomPowerSafetyGate.confirm_and_dispatch(
                mock_service, 1, confirmed=True
            )
        mock_service.set_phantom.assert_not_called()

    def test_missing_token_none_dispatches_nothing(self):
        mock_service = mock.Mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, None)
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()

    def test_forged_token_dispatches_nothing(self):
        mock_service = mock.Mock()
        forged = PhantomPowerConfirmationToken()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, forged)
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()

    def test_token_from_other_dialog_rejected(self):
        t_a = PhantomPowerSafetyGate.issue_token(1)
        t_b = PhantomPowerSafetyGate.issue_token(1)
        PhantomPowerSafetyGate.revoke_token(t_a)
        mock_service = mock.Mock()
        self.assertFalse(PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, t_a))
        mock_service.set_phantom.assert_not_called()
        self.assertTrue(PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, t_b))

    def test_token_channel_mismatch_mic1_vs_mic2(self):
        token = PhantomPowerSafetyGate.issue_token(1)
        mock_service = mock.Mock()
        self.assertFalse(PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 2, token))
        mock_service.set_phantom.assert_not_called()

    def test_token_channel_mismatch_mic2_vs_mic1(self):
        token = PhantomPowerSafetyGate.issue_token(2)
        mock_service = mock.Mock()
        self.assertFalse(PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, token))
        mock_service.set_phantom.assert_not_called()

    def test_consumed_token_cannot_be_reused(self):
        token = PhantomPowerSafetyGate.issue_token(1)
        mock_service = mock.Mock()
        self.assertTrue(PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, token))
        mock_service.set_phantom.reset_mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, token)
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()

    def test_revoked_token_rejected(self):
        token = PhantomPowerSafetyGate.issue_token(1)
        PhantomPowerSafetyGate.revoke_token(token)
        mock_service = mock.Mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, token)
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()

    def test_expired_token_by_clock_rejected(self):
        clock = mock.Mock(side_effect=[0.0, 5.0])
        token = PhantomPowerSafetyGate.issue_token(1, clock=clock)
        mock_service = mock.Mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(
            mock_service, 1, token, clock=clock, ttl=1.0
        )
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()

    def test_service_failure_propagates(self):
        token = PhantomPowerSafetyGate.issue_token(1)
        mock_service = mock.Mock()
        mock_service.set_phantom.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, token)
        mock_service.set_phantom.assert_called_once_with(1, True)

    def test_invalid_channels_rejected_before_dispatch(self):
        for ch in (0, 3, 4, 5, 6, 7, 8, 9):
            with self.assertRaises(ValueError):
                PhantomPowerSafetyGate.validate_channel(ch)


class PhantomPowerDialogUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_dialog_rejects_disallowed_channel(self):
        with self.assertRaises(ValueError):
            PhantomPowerConfirmationDialog(
                parent=self.root,
                channel_index=3,
                on_confirm=lambda token: None,
            )

    def test_dialog_cancel_invokes_on_cancel(self):
        confirmed_called = False
        canceled_called = False

        def on_confirm(token):
            nonlocal confirmed_called
            confirmed_called = True

        def on_cancel():
            nonlocal canceled_called
            canceled_called = True

        dialog = PhantomPowerConfirmationDialog(
            parent=self.root,
            channel_index=1,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )
        dialog._cancel()
        self.assertFalse(confirmed_called)
        self.assertTrue(canceled_called)
        self.assertFalse(dialog.confirmed)

    def test_dialog_confirm_invokes_on_confirm_with_token(self):
        confirmed_called = False
        received = {"token": None}

        def on_confirm(token):
            nonlocal confirmed_called
            confirmed_called = True
            received["token"] = token

        dialog = PhantomPowerConfirmationDialog(
            parent=self.root,
            channel_index=2,
            on_confirm=on_confirm,
        )
        dialog._confirm()
        self.assertTrue(confirmed_called)
        self.assertTrue(dialog.confirmed)
        self.assertIsInstance(received["token"], PhantomPowerConfirmationToken)

    def test_dialog_double_confirm_dispatches_at_most_once(self):
        calls = {"n": 0}

        def on_confirm(token):
            calls["n"] += 1

        dialog = PhantomPowerConfirmationDialog(
            parent=self.root,
            channel_index=1,
            on_confirm=on_confirm,
        )
        dialog._confirm()
        dialog._confirm()
        self.assertEqual(calls["n"], 1)

    def test_dialog_cancel_revokes_token(self):
        token_holder = {}

        def on_confirm(token):
            token_holder["t"] = token

        dialog = PhantomPowerConfirmationDialog(
            parent=self.root,
            channel_index=1,
            on_confirm=on_confirm,
        )
        tok = dialog.confirmation_token
        dialog._cancel()
        mock_service = mock.Mock()
        result = PhantomPowerSafetyGate.confirm_and_dispatch(mock_service, 1, tok)
        self.assertFalse(result)
        mock_service.set_phantom.assert_not_called()


class AnalogGainSafetyGateTests(unittest.TestCase):
    def test_allowed_channels(self):
        for ch in [1, 2, 3, 4]:
            gate = AnalogGainSafetyGate(ch, initial_gain_db=10.0)
            self.assertEqual(gate.channel_index, ch)
            self.assertEqual(gate.current_gain_db, 10.0)

        for ch in [0, 5, 6, 7, 8]:
            with self.assertRaises(ValueError):
                AnalogGainSafetyGate(ch)

    def test_staged_editing_preview_and_cancel(self):
        gate = AnalogGainSafetyGate(channel_index=1, initial_gain_db=15.0)
        self.assertFalse(gate.is_staged)

        # Stage preview
        preview = gate.stage_preview(28.5)
        self.assertEqual(preview, 28.5)
        self.assertEqual(gate.preview_gain_db, 28.5)
        self.assertEqual(gate.current_gain_db, 15.0)
        self.assertTrue(gate.is_staged)

        # Cancel preview restores software state
        restored = gate.cancel_staged()
        self.assertEqual(restored, 15.0)
        self.assertEqual(gate.preview_gain_db, 15.0)
        self.assertEqual(gate.current_gain_db, 15.0)
        self.assertFalse(gate.is_staged)

    def test_gain_dispatch_is_gated_when_unverified(self):
        gate = AnalogGainSafetyGate(channel_index=2, initial_gain_db=0.0)
        gate.stage_preview(20.0)

        mock_service = mock.Mock()
        with self.assertRaises(RuntimeError) as ctx:
            gate.commit_gain(service=mock_service)
        self.assertIn("Preamp Gain dB curve is an UNVERIFIED APPROXIMATION", str(ctx.exception))
        mock_service.assert_not_called()

    def test_verified_mapping_still_needs_confirmation_and_never_fakes_success(self):
        gate = AnalogGainSafetyGate(channel_index=1, initial_gain_db=0.0)
        gate.stage_preview(20.0)
        service = mock.Mock()
        with mock.patch.object(
            AnalogGainSafetyGate, "is_verified_mapping_available", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                gate.commit_gain(service)
            with self.assertRaises(NotImplementedError):
                gate.commit_gain(service, confirmed=True)
        self.assertEqual(gate.current_gain_db, 0.0)
        self.assertTrue(gate.is_staged)
        self.assertEqual(service.mock_calls, [])


if __name__ == "__main__":
    unittest.main()
