"""Honest status vocabulary for the FLOW 8 desktop shell (UI.2-T1).

Every value here describes what the software actually knows at shell start-up:
no port has been opened, no parameter has been dispatched, and no observation
path exists yet (decision D-4 keeps observation out of UI.2).

Dispatch vocabulary that must stay distinct once commands exist — see
``flow8.command_boundary.DispatchStatus``::

    ACCEPTED_OFFLINE | DRIVER_DISPATCHED | DISPATCH_FAILED
    | API_ACKNOWLEDGED | UNKNOWN

None of those may ever be rendered as physical hardware confirmation. This
build performs no dispatch at all, so it renders none of them.

``FORBIDDEN_CLAIMS`` lists the statements the shell must never make. The UI
test suite asserts that none of them appears in any rendered string.
"""

from __future__ import annotations

from dataclasses import dataclass

DEVICE_NOT_VERIFIED = "NOT VERIFIED"
MIDI_UNKNOWN = "UNKNOWN"
MIDI_OUT_UNKNOWN = "UNKNOWN"
MIDI_IN_UNKNOWN = "UNKNOWN"
USB_AUDIO_NOT_INTEGRATED = "NOT INTEGRATED"
AUDIO_TELEMETRY_NONE = "NO TELEMETRY"
OBSERVATION_UNKNOWN = "UNCONFIRMED"

#: Claims that require a verified observation path. None exists in UI.2.
FORBIDDEN_CLAIMS = (
    "HARDWARE APPLIED",
    "HARDWARE CONFIRMED",
    "SYNCED",
)


@dataclass(frozen=True)
class SessionStatus:
    """Immutable snapshot of what the shell is entitled to display.

    The defaults are the only honest values for a shell that has not opened a
    port, has no audio engine, and has no telemetry source. They are not
    placeholders awaiting a real value: they are the correct answer today.
    """

    device: str = DEVICE_NOT_VERIFIED
    midi: str = MIDI_UNKNOWN
    midi_out: str = MIDI_OUT_UNKNOWN
    midi_in: str = MIDI_IN_UNKNOWN
    usb_audio: str = USB_AUDIO_NOT_INTEGRATED
    audio_telemetry: str = AUDIO_TELEMETRY_NONE
    hardware_observation: str = OBSERVATION_UNKNOWN

    def transport_rows(self) -> tuple[tuple[str, str], ...]:
        """Return ``(label, value)`` pairs for the status bar."""
        return (
            ("MIDI OUT", self.midi_out),
            ("MIDI IN", self.midi_in),
            ("USB AUDIO", self.usb_audio),
            ("AUDIO TELEMETRY", self.audio_telemetry),
            ("HARDWARE OBSERVATION", self.hardware_observation),
        )
