"""Application Service for Behringer FLOW 8 Workstation.

Orchestrates the communication chain according to the architectural rules:
    UI -> Application Service -> Parameter Engine -> Command Boundary -> MIDI Driver

Handles hardware discovery, connection lifecycle, and bidirectional synchronization.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

from flow8.command_boundary import CommandLogEntry, Flow8CommandBoundary
from flow8.domain_model import LOGICAL_CHANNELS
from flow8.midi_constants import CC_VOLUME_FADER, CC_MUTE, CC_PAN, CC_PHANTOM, CC_GAIN
from flow8.midi_in import Flow8MidiIn
from flow8.midi_out import Flow8MidiOut
from flow8.parameter_engine import Flow8ParameterEngine
from flow8.parameter_mapping import fader_midi_to_db, pan_midi_to_percent
from flow8.state_model import EventSource, Flow8StateStore, ParameterState


class Flow8Service:
    """Thread-safe application service managing FLOW 8 hardware and parameter engine."""

    def __init__(self, auto_connect: bool = True) -> None:
        self.state_store = Flow8StateStore()
        self.midi_out = Flow8MidiOut()
        self.midi_in = Flow8MidiIn()
        self.command_boundary = Flow8CommandBoundary(
            midi_out=self.midi_out,
            state_store=self.state_store,
        )
        self.parameter_engine = Flow8ParameterEngine(
            command_boundary=self.command_boundary,
            state_store=self.state_store,
        )

        self._lock = threading.RLock()
        self._connected = False
        self._last_connection_error: Optional[str] = None
        self._listeners: list[Callable[[str, Any], None]] = []

        if auto_connect:
            self.connect()

    @property
    def is_connected(self) -> bool:
        """True if both MIDI OUT and IN endpoints are open and ready."""
        with self._lock:
            return self._connected and self.midi_out.is_connected

    def add_listener(self, listener: Callable[[str, Any], None]) -> None:
        """Register listener for state changes: listener(param_id, value)."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, Any], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify_listeners(self, param_id: str, value: Any) -> None:
        with self._lock:
            callbacks = list(self._listeners)
        for cb in callbacks:
            try:
                cb(param_id, value)
            except Exception:
                pass

    def connect(self) -> bool:
        """Attempt to locate and open the FLOW 8 hardware endpoints."""
        with self._lock:
            try:
                # Open MIDI Out
                if not self.midi_out.is_connected:
                    self.midi_out.open()

                # Open and start MIDI In
                if not self.midi_in.is_connected:
                    self.midi_in.open()
                    self.midi_in.register_callback(self._on_midi_in_event)
                    self.midi_in.start()

                self._connected = True
                self._last_connection_error = None
                return True
            except Exception as error:
                self._connected = False
                self._last_connection_error = str(error) or error.__class__.__name__
                try:
                    self.midi_in.close()
                    self.midi_out.close()
                except Exception:
                    pass
                return False

    @property
    def last_connection_error(self) -> Optional[str]:
        return self._last_connection_error

    def disconnect(self) -> None:
        """Cleanly close all endpoints."""
        with self._lock:
            try:
                self.midi_in.close()
            except Exception:
                pass
            try:
                self.midi_out.close()
            except Exception:
                pass
            self._connected = False

    def _on_midi_in_event(self, event: dict) -> None:
        """Handle incoming MIDI event from FLOW 8 physical hardware."""
        # CC status is 0xB0 to 0xBF
        if (event.get('status', 0) & 0xF0) != 0xB0:
            return

        channel = event.get('channel', 0)   # 1 to 8 (1..7 strips, 8 main)
        cc = event.get('data1', 0)
        val = event.get('data2', 0)

        param_id = None
        if 1 <= channel <= 7:
            prefix = f"ch{channel}"
            if cc == CC_VOLUME_FADER:
                param_id = f"{prefix}.fader"
            elif cc == CC_MUTE:
                param_id = f"{prefix}.mute"
            elif cc == CC_PAN:
                param_id = f"{prefix}.pan"
            elif cc == CC_PHANTOM:
                param_id = f"{prefix}.phantom"
            elif cc == CC_GAIN:
                param_id = f"{prefix}.gain"
        elif channel == 8:
            if cc == CC_VOLUME_FADER:
                param_id = "main.fader"
            elif cc == CC_PAN:
                param_id = "main.balance"

        if param_id:
            try:
                self.state_store.commit_inbound_observed(
                    param_id=param_id,
                    observed_value=val,
                    raw_midi=val,
                    source=EventSource.PHYSICAL_HARDWARE,
                )
                self._notify_listeners(param_id, val)
            except Exception:
                pass

    # -- High-level UI dispatch methods -------------------------------------

    def set_fader(self, channel_index: int, raw_value: int) -> CommandLogEntry:
        """Set fader level (1..7 for input strips, 8 for Main bus)."""
        clamped = max(0, min(127, int(raw_value)))
        if 1 <= channel_index <= 7:
            return self.parameter_engine.channel(channel_index).set_fader(clamped, unit="raw")
        elif channel_index == 8:
            return self.parameter_engine.set_main_fader(clamped, unit="raw")
        raise ValueError(f"Invalid FLOW 8 channel index: {channel_index}")

    def set_mute(self, channel_index: int, muted: bool) -> CommandLogEntry:
        """Set mute state (1..7 for input strips)."""
        if 1 <= channel_index <= 7:
            return self.parameter_engine.channel(channel_index).set_mute(bool(muted))
        raise ValueError(f"Invalid FLOW 8 channel index: {channel_index}")

    def set_pan(self, channel_index: int, raw_value: int) -> CommandLogEntry:
        """Set pan/balance (1..7 for input strips, 8 for Main bus)."""
        clamped = max(0, min(127, int(raw_value)))
        if 1 <= channel_index <= 7:
            return self.parameter_engine.channel(channel_index).set_pan(clamped, unit="raw")
        elif channel_index == 8:
            return self.parameter_engine.set_main_balance(clamped, unit="raw")
        raise ValueError(f"Invalid FLOW 8 channel index: {channel_index}")

    def set_phantom(self, channel_index: int, enabled: bool) -> CommandLogEntry:
        """Set +48V phantom power (Channels 1 and 2 only)."""
        if channel_index in (1, 2):
            return self.parameter_engine.channel(channel_index).set_phantom(bool(enabled))
        raise ValueError(f"Phantom power is unavailable on channel {channel_index}")
