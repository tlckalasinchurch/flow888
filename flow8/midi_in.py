"""
Behringer FLOW 8 Inbound USB MIDI Listener Preparation.
Safe lifecycle wrapper for Windows Multimedia MIDI In (winmm.dll).

Note: This component prepares the receiver interface and driver lifecycle.
Bidirectional state synchronization is NOT claimed in this phase.
"""

import threading
import ctypes
from typing import Optional, Callable, Tuple, List
from ctypes import wintypes
from datetime import datetime

from .midi_constants import (
    WinMmError,
    FLOW8_MIDI_IN_NAME,
    MIM_DATA,
    CALLBACK_FUNCTION
)
from .midi_out import Flow8MidiError, Flow8NotConnectedError, Flow8DeviceBusyError

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ('wMid', wintypes.WORD),
        ('wPid', wintypes.WORD),
        ('vDriverVersion', wintypes.DWORD),
        ('szPname', wintypes.WCHAR * 32),
        ('dwSupport', wintypes.DWORD)
    ]

# Define 64-bit compatible DWORD_PTR / UINT_PTR
DWORD_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else wintypes.DWORD

MidiInProc = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.UINT,
    DWORD_PTR,
    DWORD_PTR,
    DWORD_PTR
)

class Flow8MidiIn:
    """
    Prepared asynchronous MIDI IN listener for Behringer FLOW 8.
    """

    def __init__(self, target_device_name: str = FLOW8_MIDI_IN_NAME):
        self._target_name = target_device_name
        self._winmm = ctypes.windll.winmm
        self._handle: Optional[wintypes.HANDLE] = None
        self._device_id: Optional[int] = None
        self._device_name: Optional[str] = None
        self._lock = threading.RLock()
        self._is_open = False
        self._is_listening = False
        self._callbacks: List[Callable[[dict], None]] = []
        self._c_callback_ref = None

    @property
    def is_connected(self) -> bool:
        """Return True if the endpoint handle is open."""
        with self._lock:
            return self._is_open and (self._handle is not None)

    @property
    def is_listening(self) -> bool:
        """Return True if actively receiving incoming MIDI streams."""
        with self._lock:
            return self._is_listening

    @property
    def device_info(self) -> Tuple[Optional[int], Optional[str]]:
        """Return (device_id, device_name)."""
        with self._lock:
            return self._device_id, self._device_name

    def register_callback(self, callback: Callable[[dict], None]) -> None:
        """Register a callback to receive incoming MIDI event dictionaries."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[dict], None]) -> None:
        """Unregister a previously registered callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def find_device_id(self) -> Optional[int]:
        """Locate FLOW 8 MIDI IN device ID from system enumeration."""
        num_devs = self._winmm.midiInGetNumDevs()
        for i in range(num_devs):
            caps = MIDIINCAPSW()
            res = self._winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
            if res == WinMmError.MMSYSERR_NOERROR:
                if self._target_name in caps.szPname:
                    return i
        return None

    def _internal_c_callback(self, hMidiIn, wMsg, dwInstance, dwParam1, dwParam2):
        if wMsg == MIM_DATA:
            status = dwParam1 & 0xFF
            b1 = (dwParam1 >> 8) & 0xFF
            b2 = (dwParam1 >> 16) & 0xFF
            ts_driver = dwParam2
            event = {
                'timestamp': datetime.now().isoformat(),
                'driver_ts_ms': ts_driver,
                'status': status,
                'channel': (status & 0x0F) + 1,
                'command': status & 0xF0,
                'data1': b1,
                'data2': b2
            }
            # Snapshot callbacks to avoid deadlock during iteration
            with self._lock:
                listeners = list(self._callbacks)
            for cb in listeners:
                try:
                    cb(event)
                except Exception:
                    pass

    def open(self, device_id: Optional[int] = None) -> None:
        """Open the MIDI IN endpoint safely."""
        with self._lock:
            if self._is_open:
                self.close()

            if device_id is None:
                dev_id = self.find_device_id()
                if dev_id is None:
                    raise Flow8NotConnectedError(
                        f"Device '{self._target_name}' not found in MIDI In enumeration."
                    )
            else:
                dev_id = device_id

            caps = MIDIINCAPSW()
            if self._winmm.midiInGetDevCapsW(dev_id, ctypes.byref(caps), ctypes.sizeof(caps)) == WinMmError.MMSYSERR_NOERROR:
                dev_name = caps.szPname
            else:
                dev_name = f"MIDI In Device #{dev_id}"

            self._c_callback_ref = MidiInProc(self._internal_c_callback)
            new_handle = wintypes.HANDLE()
            res = self._winmm.midiInOpen(
                ctypes.byref(new_handle),
                dev_id,
                self._c_callback_ref,
                0,
                CALLBACK_FUNCTION
            )

            if res == WinMmError.MMSYSERR_ALLOCATED:
                raise Flow8DeviceBusyError(f"MIDI In endpoint {dev_id} ({dev_name}) is busy.")
            elif res != WinMmError.MMSYSERR_NOERROR:
                raise Flow8MidiError(f"Failed to open MIDI In {dev_id}: error code {res}")

            self._handle = new_handle
            self._device_id = dev_id
            self._device_name = dev_name
            self._is_open = True

    def start(self) -> None:
        """Start receiving incoming MIDI data."""
        with self._lock:
            if not self._is_open or not self._handle:
                raise Flow8NotConnectedError("Cannot start listening: MIDI In not open.")
            if not self._is_listening:
                res = self._winmm.midiInStart(self._handle)
                if res != WinMmError.MMSYSERR_NOERROR:
                    raise Flow8MidiError(f"midiInStart failed with code {res}")
                self._is_listening = True

    def stop(self) -> None:
        """Stop listening for incoming MIDI data."""
        with self._lock:
            if self._is_open and self._handle and self._is_listening:
                self._winmm.midiInStop(self._handle)
                self._is_listening = False

    def close(self) -> None:
        """Close endpoint and release resources cleanly."""
        with self._lock:
            if self._is_open and self._handle is not None:
                if self._is_listening:
                    self.stop()
                try:
                    self._winmm.midiInReset(self._handle)
                    self._winmm.midiInClose(self._handle)
                except Exception:
                    pass
            self._handle = None
            self._device_id = None
            self._device_name = None
            self._is_open = False
            self._is_listening = False
            self._c_callback_ref = None

    def __enter__(self):
        self.open()
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
