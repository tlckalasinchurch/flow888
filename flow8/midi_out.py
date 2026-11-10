"""
Behringer FLOW 8 Outbound USB MIDI Engine.
Production-grade wrapper for Windows Multimedia MIDI Out (winmm.dll).

Scope: Behringer FLOW 8 ONLY. Channel/CC scope is enforced in `send_cc`, which
is a deliberate SUPERSET of Flow8CommandBoundary.ACTIVE_ALLOWLIST: the transport
gate must reject addresses the hardware cannot have, while the command boundary
is the authority on which of those addresses are sanctioned for use.

Dispatch semantics
------------------
`send_cc` returning normally means ONLY that `midiOutShortMsg` accepted the short
message into the Windows driver queue (MMSYSERR_NOERROR). It does NOT prove USB
transmission, that the mixer parsed the message, that any parameter changed, or
that the audio changed. Callers must never report hardware confirmation from a
successful return.
"""

import threading
import ctypes
import sys
from typing import Optional, Union, Tuple
from ctypes import wintypes

from .midi_constants import (
    WinMmError,
    FLOW8_MIDI_OUT_NAME,
    MIDI_CH_INPUT_1,
    MIDI_CH_MAIN,
    MIDI_CH_MON1,
    MIDI_CH_MON2,
    MIDI_CH_FX1,
    MIDI_CH_FX2,
    CC_VOLUME_FADER,
    CC_MUTE,
    CC_SOLO,
    CC_PAN,
    CC_GAIN,
    CC_LOW_CUT,
    CC_COMPRESSOR,
    CC_PHANTOM,
    CC_EQ_LOW,
    CC_EQ_LOW_MID,
    CC_EQ_HI_MID,
    CC_EQ_HI,
    CC_SEND_MON1,
    CC_SEND_MON2,
    CC_SEND_FX1,
    CC_SEND_FX2,
    CC_VAL_MIN,
    CC_VAL_MAX,
    MUTE_VAL_OFF,
    MUTE_VAL_ON,
)
from .parameter_mapping import (
    fader_db_to_midi,
    pan_percent_to_midi,
    mute_bool_to_midi,
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class Flow8MidiError(Exception):
    """Base exception for all FLOW 8 MIDI operations."""
    pass

class Flow8NotConnectedError(Flow8MidiError):
    """Raised when an operation is attempted without an active MIDI endpoint."""
    pass

class Flow8ValidationError(Flow8MidiError):
    """Raised when an out-of-range or unverified MIDI parameter is passed."""
    pass

class Flow8DeviceBusyError(Flow8MidiError):
    """Raised when the Windows MIDI endpoint is locked by another process."""
    pass

# ---------------------------------------------------------------------------
# CTypes Structures
# ---------------------------------------------------------------------------

class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ('wMid', wintypes.WORD),
        ('wPid', wintypes.WORD),
        ('vDriverVersion', wintypes.DWORD),
        ('szPname', wintypes.WCHAR * 32),
        ('wTechnology', wintypes.WORD),
        ('wVoices', wintypes.WORD),
        ('wNotes', wintypes.WORD),
        ('wChannelMask', wintypes.WORD),
        ('dwSupport', wintypes.DWORD)
    ]

# ---------------------------------------------------------------------------
# Flow8MidiOut Implementation
# ---------------------------------------------------------------------------

class Flow8MidiOut:
    """
    Thread-safe outbound MIDI controller dedicated to Behringer FLOW 8.
    """

    def __init__(self, target_device_name: str = FLOW8_MIDI_OUT_NAME):
        self._target_name = target_device_name
        self._winmm = ctypes.windll.winmm if sys.platform == "win32" else None
        self._handle: Optional[wintypes.HANDLE] = None
        self._device_id: Optional[int] = None
        self._device_name: Optional[str] = None
        self._lock = threading.RLock()
        self._is_open = False

    def _require_winmm(self) -> None:
        if self._winmm is None:
            raise Flow8MidiError(
                "Windows WinMM MIDI is unavailable on this platform; "
                "use a mock MIDI backend for offline operation."
            )

    @property
    def is_connected(self) -> bool:
        """Return True if the MIDI OUT endpoint is currently open."""
        with self._lock:
            return self._is_open and (self._handle is not None)

    @property
    def device_info(self) -> Tuple[Optional[int], Optional[str]]:
        """Return (device_id, device_name)."""
        with self._lock:
            return self._device_id, self._device_name

    def find_device_id(self) -> Optional[int]:
        """Enumerate system MIDI Out devices and find the FLOW 8 endpoint ID."""
        self._require_winmm()
        num_devs = self._winmm.midiOutGetNumDevs()
        for i in range(num_devs):
            caps = MIDIOUTCAPSW()
            res = self._winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
            if res == WinMmError.MMSYSERR_NOERROR:
                if self._target_name in caps.szPname:
                    return i
        return None

    def open(self, device_id: Optional[int] = None) -> None:
        """
        Open the FLOW 8 MIDI OUT endpoint.
        If device_id is omitted, auto-discovers by name.
        """
        with self._lock:
            self._require_winmm()
            if self._is_open:
                # Prevent duplicate handles; close existing first
                self.close()

            if device_id is None:
                dev_id = self.find_device_id()
                if dev_id is None:
                    raise Flow8NotConnectedError(
                        f"Device '{self._target_name}' not found in MIDI Out enumeration."
                    )
            else:
                dev_id = device_id

            # Retrieve caps to store device name
            caps = MIDIOUTCAPSW()
            if self._winmm.midiOutGetDevCapsW(dev_id, ctypes.byref(caps), ctypes.sizeof(caps)) == WinMmError.MMSYSERR_NOERROR:
                dev_name = caps.szPname
            else:
                dev_name = f"MIDI Out Device #{dev_id}"

            new_handle = wintypes.HANDLE()
            res = self._winmm.midiOutOpen(ctypes.byref(new_handle), dev_id, 0, 0, 0)

            if res == WinMmError.MMSYSERR_ALLOCATED:
                raise Flow8DeviceBusyError(
                    f"MIDI Out endpoint {dev_id} ({dev_name}) is already locked by another process."
                )
            elif res != WinMmError.MMSYSERR_NOERROR:
                err_enum = WinMmError(res) if res in WinMmError._value2member_map_ else res
                raise Flow8MidiError(f"Failed to open MIDI Out endpoint {dev_id}: error code {err_enum}")

            self._handle = new_handle
            self._device_id = dev_id
            self._device_name = dev_name
            self._is_open = True

    def close(self) -> None:
        """Close the MIDI OUT endpoint safely."""
        with self._lock:
            if self._is_open and self._handle is not None:
                try:
                    self._winmm.midiOutClose(self._handle)
                except Exception:
                    pass
            self._handle = None
            self._device_id = None
            self._device_name = None
            self._is_open = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -----------------------------------------------------------------------
    # Low-level Message Dispatch & Validation
    # -----------------------------------------------------------------------

    def send_cc(self, channel: int, cc: int, value: int) -> int:
        """
        Submit a validated MIDI Control Change (CC) message to the Windows driver.

        - channel: 1 to 16
        - cc: 0 to 127
        - value: 0 to 127

        Returns the 24-bit short message handed to `midiOutShortMsg` so callers can
        record exactly what was submitted. A successful return is NOT proof of
        delivery: the driver queues the message and may fail to transmit it.
        """
        # Strict validation
        if not (1 <= channel <= 16):
            raise Flow8ValidationError(f"Invalid MIDI channel: {channel} (must be 1–16)")
        if not (0 <= cc <= 127):
            raise Flow8ValidationError(f"Invalid CC number: {cc} (must be 0–127)")
        if not (0 <= value <= 127):
            raise Flow8ValidationError(f"Invalid CC value: {value} (must be 0–127)")

        # Phase C Verified FLOW 8 Parameter Scope
        is_verified = False
        if 1 <= channel <= 4:
            is_verified = cc in (
                CC_EQ_LOW, CC_EQ_LOW_MID, CC_EQ_HI_MID, CC_EQ_HI,
                CC_MUTE, CC_SOLO, CC_VOLUME_FADER, CC_GAIN, CC_LOW_CUT,
                CC_PAN, CC_COMPRESSOR, CC_SEND_MON1, CC_SEND_MON2,
                CC_SEND_FX1, CC_SEND_FX2
            ) or (channel in (1, 2) and cc == CC_PHANTOM)
        elif channel in (5, 6, 7):
            is_verified = cc in (
                CC_EQ_LOW, CC_EQ_LOW_MID, CC_EQ_HI_MID, CC_EQ_HI,
                CC_MUTE, CC_SOLO, CC_VOLUME_FADER, CC_PAN,
                CC_SEND_MON1, CC_SEND_MON2, CC_SEND_FX1, CC_SEND_FX2
            )
        elif channel == MIDI_CH_MAIN:  # Ch 8
            is_verified = cc in (CC_VOLUME_FADER, CC_PAN, 8) or (11 <= cc <= 19)
        elif channel in (MIDI_CH_MON1, MIDI_CH_MON2):  # Ch 9, 10
            is_verified = cc in (CC_VOLUME_FADER, 8) or (11 <= cc <= 19)
        elif channel in (MIDI_CH_FX1, MIDI_CH_FX2):  # Ch 11, 12
            is_verified = (cc == CC_VOLUME_FADER)

        if not is_verified:
            raise Flow8ValidationError(
                f"Unverified or unsupported parameter for FLOW 8: Channel {channel}, CC {cc}."
            )

        with self._lock:
            if not self._is_open or not self._handle:
                raise Flow8NotConnectedError("Cannot send MIDI: device is not connected.")

            # Status byte for CC: 0xB0 | (channel - 1)
            status_byte = 0xB0 | ((channel - 1) & 0x0F)
            msg = status_byte | ((cc & 0x7F) << 8) | ((value & 0x7F) << 16)

            res = self._winmm.midiOutShortMsg(self._handle, msg)
            if res != WinMmError.MMSYSERR_NOERROR:
                # Check for possible disconnection
                if res in (WinMmError.MMSYSERR_INVALHANDLE, WinMmError.MMSYSERR_NODRIVER):
                    self.close()
                    raise Flow8NotConnectedError(f"MIDI device disconnected during dispatch (error {res})")
                raise Flow8MidiError(f"Failed to send MIDI CC (0x{msg:06X}): error code {res}")

            # Driver accepted the message. This is an API acknowledgement only.
            return msg

    # -----------------------------------------------------------------------
    # Verified High-Level Parameter Methods
    # -----------------------------------------------------------------------

    def set_main_fader(self, value: int) -> None:
        """Set Main Bus Fader level using raw MIDI value (0–127)."""
        self.send_cc(MIDI_CH_MAIN, CC_VOLUME_FADER, value)

    def set_main_fader_db(self, db: Union[float, int]) -> None:
        """Set Main Bus Fader level using decibels (dB). [UNVERIFIED APPROXIMATION]"""
        raw = fader_db_to_midi(db)
        self.set_main_fader(raw)

    def set_channel1_fader(self, value: int) -> None:
        """Set Channel 1 (Mic 1) Fader level using raw MIDI value (0–127)."""
        self.send_cc(MIDI_CH_INPUT_1, CC_VOLUME_FADER, value)

    def set_channel1_fader_db(self, db: Union[float, int]) -> None:
        """Set Channel 1 (Mic 1) Fader level using decibels (dB). [UNVERIFIED APPROXIMATION]"""
        raw = fader_db_to_midi(db)
        self.set_channel1_fader(raw)

    def set_channel1_mute(self, muted: bool) -> None:
        """Set Channel 1 (Mic 1) Mute state (True = Muted / 127, False = Unmuted / 0)."""
        val = mute_bool_to_midi(muted)
        self.send_cc(MIDI_CH_INPUT_1, CC_MUTE, val)

    def set_channel1_pan(self, value: int) -> None:
        """Set Channel 1 (Mic 1) Panning using raw MIDI value (0–127, Center = 64)."""
        self.send_cc(MIDI_CH_INPUT_1, CC_PAN, value)

    def set_channel1_pan_percent(self, percent: float) -> None:
        """Set Channel 1 (Mic 1) Panning using percentage (-100.0% to +100.0%)."""
        val = pan_percent_to_midi(percent)
        self.set_channel1_pan(val)
