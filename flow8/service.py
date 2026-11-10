"""Application Service for Behringer FLOW 8 Workstation.

Orchestrates the communication chain according to the architectural rules:
    UI -> Application Service -> Parameter Engine -> Command Boundary -> MIDI Driver

Handles hardware discovery, connection lifecycle, and bidirectional synchronization.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

from flow8.command_boundary import Flow8CommandBoundary
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
        self._connection_error: Optional[str] = None
        self._listeners: list[Callable[[str, Any], None]] = []
        self._command_log_listeners: list[Callable[[list], None]] = []

        if auto_connect:
            self.connect()

    @property
    def is_connected(self) -> bool:
        """True only when both MIDI endpoints are open and MIDI IN is listening."""
        with self._lock:
            return (
                self._connected
                and self.midi_out.is_connected
                and self.midi_in.is_connected
                and self.midi_in.is_listening
            )

    @property
    def midi_out_open(self) -> bool:
        """Whether the MIDI OUT endpoint handle is open."""
        return self.midi_out.is_connected

    @property
    def midi_in_open(self) -> bool:
        """Whether the MIDI IN endpoint handle is open."""
        return self.midi_in.is_connected

    @property
    def midi_in_listening(self) -> bool:
        """Whether the MIDI IN endpoint is actively receiving events."""
        return self.midi_in.is_listening

    @property
    def connection_error(self) -> Optional[str]:
        """Most recent connection error, if a port could not be opened."""
        with self._lock:
            return self._connection_error

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
                logger.exception("FLOW 8 state listener failed for %s", param_id)

    def add_command_log_listener(self, listener: Callable[[list], None]) -> None:
        """Register a listener for command-log snapshots."""
        with self._lock:
            if listener not in self._command_log_listeners:
                self._command_log_listeners.append(listener)

    def remove_command_log_listener(self, listener: Callable[[list], None]) -> None:
        """Remove a command-log listener."""
        with self._lock:
            if listener in self._command_log_listeners:
                self._command_log_listeners.remove(listener)

    def _notify_command_log_listeners(self) -> None:
        entries = self.command_boundary.command_log
        with self._lock:
            callbacks = list(self._command_log_listeners)
        for callback in callbacks:
            try:
                callback(entries)
            except Exception:
                logger.exception("FLOW 8 command-log listener failed")

    def _dispatch_and_notify(self, callback: Callable, *args, **kwargs):
        """Notify audit listeners even when a command attempt raises."""
        try:
            return callback(*args, **kwargs)
        finally:
            self._notify_command_log_listeners()

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
                self._connection_error = None
                return True
            except Exception as e:
                self._connected = False
                self._connection_error = str(e)
                logger.exception("FLOW 8 MIDI connection failed")
                return False

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
            self._connection_error = None

    def _on_midi_in_event(self, event: dict) -> None:
        """Record recognized inbound CC as observed state; never echo it as a command."""
        if (event.get("status", 0) & 0xF0) != 0xB0:
            return

        channel = event.get("channel", 0)  # MIDI channels are one-based here.
        cc = event.get("data1", 0)
        raw_value = event.get("data2", 0)

        param_id = None
        if channel == 8:
            if cc == CC_VOLUME_FADER:
                param_id = "main.fader"
            elif cc == CC_PAN:
                param_id = "main.balance"
        else:
            # Resolve MIDI channel through the shared logical-channel model.
            # MIDI ch6 is logical strip ch6 (the 7/8 stereo pair), not input 6.
            channel_spec = next(
                (
                    spec for spec in LOGICAL_CHANNELS.values()
                    if spec.midi_channel == channel
                ),
                None,
            )
            if channel_spec is not None:
                prefix = f"ch{channel_spec.channel_index}"
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

        if not param_id or param_id not in self.command_boundary.ACTIVE_ALLOWLIST:
            return

        observed_value = (
            bool(raw_value) if cc in (CC_MUTE, CC_PHANTOM) else raw_value
        )
        try:
            self.state_store.set_observed_value(
                param_id=param_id,
                value=observed_value,
                raw_midi_value=raw_value,
                source=EventSource.PHYSICAL_HARDWARE,
            )
        except Exception:
            logger.exception(
                "Failed to record inbound FLOW 8 MIDI observation: "
                "param=%s channel=%s cc=%s value=%s",
                param_id, channel, cc, raw_value,
            )
            return

        self._notify_listeners(param_id, observed_value)

    # -- High-level UI dispatch methods -------------------------------------

    def set_fader(self, channel_index: int, raw_value: int) -> None:
        """Set fader level (1..7 for input strips, 8 for Main bus)."""
        clamped = max(0, min(127, int(raw_value)))
        if 1 <= channel_index <= 7:
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_fader,
                clamped, unit="raw",
            )
        elif channel_index == 8:
            self._dispatch_and_notify(
                self.parameter_engine.set_main_fader, clamped, unit="raw",
            )

    def set_mute(self, channel_index: int, muted: bool) -> None:
        """Set mute state (1..7 for input strips)."""
        if 1 <= channel_index <= 7:
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_mute, bool(muted),
            )

    def set_pan(self, channel_index: int, raw_value: int) -> None:
        """Set pan/balance (1..7 for input strips, 8 for Main bus)."""
        clamped = max(0, min(127, int(raw_value)))
        if 1 <= channel_index <= 7:
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_pan,
                clamped, unit="raw",
            )
        elif channel_index == 8:
            self._dispatch_and_notify(
                self.parameter_engine.set_main_balance, clamped, unit="raw",
            )

    def set_phantom(self, channel_index: int, enabled: bool) -> None:
        """Set +48V phantom power (Channels 1 and 2 only)."""
        if channel_index in (1, 2):
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_phantom,
                bool(enabled),
            )
