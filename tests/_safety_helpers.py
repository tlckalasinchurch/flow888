"""Helpers for safety tests. No bypass: authorised phantom ON goes through the real gate."""
from ctypes import wintypes
from unittest.mock import MagicMock

from flow8.midi_constants import WinMmError
from flow8.midi_out import Flow8MidiOut
from flow8.ui.safety_dialogs import PhantomPowerSafetyGate  # re-exported from flow8.safety after S1.2


def fake_open_port(out=None):
    """Make *out* look open with a MagicMock driver. No real handle, nothing can be transmitted."""
    out = out if out is not None else Flow8MidiOut()
    driver = MagicMock()
    driver.midiOutShortMsg.return_value = WinMmError.MMSYSERR_NOERROR
    out._winmm = driver
    out._is_open = True
    out._handle = wintypes.HANDLE(0x1234)
    return out, driver


def dword(channel, cc, value):
    """Independent reference encoder for a control change."""
    return (0xB0 | (channel - 1)) | (cc << 8) | (value << 16)


class EngineAdapter:
    """Gives a Flow8ParameterEngine the `set_phantom(channel, enabled)` shape of a service."""

    def __init__(self, engine):
        self.engine = engine

    def set_phantom(self, channel, enabled):
        return self.engine.channel(channel).set_phantom(enabled)


def authorize_phantom_on(target, channel):
    """Enable +48 V the only legitimate way: issue a token, then confirm through the gate."""
    token = PhantomPowerSafetyGate.issue_token(channel)
    ok = PhantomPowerSafetyGate.confirm_and_dispatch(target, channel, token)
    assert ok, "gate refused a valid token"
    return token
