import unittest
from unittest import mock

from flow8.ui.safety_dialogs import PhantomPowerSafetyGate


class PhantomPowerSafetyGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = PhantomPowerSafetyGate()
        self.service = mock.Mock()

    def test_confirm_dispatches_once(self):
        request = self.gate.request_confirmation(1)
        self.assertTrue(
            self.gate.confirm_and_dispatch(
                self.service, 1, request.confirmation_token
            )
        )
        self.assertFalse(
            self.gate.confirm_and_dispatch(
                self.service, 1, request.confirmation_token
            )
        )
        self.service.set_phantom.assert_called_once_with(1, True)

    def test_forged_none_bool_and_wrong_channel_tokens_dispatch_nothing(self):
        request = self.gate.request_confirmation(1)
        for token, channel in ((True, 1), (None, 1), (object(), 1), (request.confirmation_token, 2)):
            self.assertFalse(self.gate.confirm_and_dispatch(self.service, channel, token))
        self.service.set_phantom.assert_not_called()

    def test_cancelled_token_dispatches_nothing(self):
        request = self.gate.request_confirmation(1)
        request.cancel()
        self.assertFalse(self.gate.confirm_and_dispatch(self.service, 1, request.confirmation_token))
        self.service.set_phantom.assert_not_called()

    def test_superseded_token_dispatches_nothing(self):
        first = self.gate.request_confirmation(1)
        second = self.gate.request_confirmation(1)
        self.assertFalse(self.gate.confirm_and_dispatch(self.service, 1, first.confirmation_token))
        self.assertTrue(self.gate.confirm_and_dispatch(self.service, 1, second.confirmation_token))
        self.service.set_phantom.assert_called_once_with(1, True)

    def test_unsupported_channels_are_rejected(self):
        for channel in (0, 3, 4, 5, 6, 7, 8):
            with self.assertRaises(ValueError):
                self.gate.request_confirmation(channel)
        self.service.set_phantom.assert_not_called()

    def test_missing_service_does_not_dispatch(self):
        request = self.gate.request_confirmation(2)
        self.assertFalse(self.gate.confirm_and_dispatch(None, 2, request.confirmation_token))
        self.service.set_phantom.assert_not_called()


if __name__ == "__main__":
    unittest.main()
