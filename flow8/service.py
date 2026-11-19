"""Application Service for Behringer FLOW 8 Workstation.

Orchestrates the communication chain according to the architectural rules:
    UI -> Application Service -> Parameter Engine -> Command Boundary -> MIDI Driver

Handles MIDI port lifecycle, command dispatch, and inbound observation recording.
Inbound CC handling is not a claim that the FLOW 8 provides complete two-way sync.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional

logger = logging.getLogger(__name__)

from flow8.command_boundary import Flow8CommandBoundary, Flow8CommandRejectedError
from flow8.safety import BLOCKED_PARAMETER_TYPES
from flow8.domain_model import LOGICAL_CHANNELS
from flow8.ledger import CommandLedger, CommandRecord
from flow8.midi_constants import CC_VOLUME_FADER, CC_MUTE, CC_PAN, CC_PHANTOM, CC_GAIN
from flow8.midi_in import Flow8MidiIn
from flow8.midi_out import Flow8MidiOut
from flow8.parameter_engine import Flow8ParameterEngine
from flow8.parameter_mapping import fader_midi_to_db, pan_midi_to_percent
from flow8.scenes import SceneManager, SceneSnapshot
from flow8.state_model import EventSource, Flow8StateStore, ParameterProvenance, ParameterState


LEDGER_CAPACITY = 50
SCENE_CAPACITY = 15
MAIN_CHANNEL = 8
# Pseudo parameter id sent to state listeners when a connect/disconnect has reset all state.
RECONCILE_EVENT = "__reconcile__"
# Pseudo parameter id: software-side state changed in bulk (preset, undo, redo).
STATE_CHANGED_EVENT = "__changed__"

#: The only parameters the ledger and scenes may ever touch. +48V phantom power
#: and preamp gain are deliberately absent: neither is undoable nor part of a scene.
REVERSIBLE_PARAMETERS = (
    "fader", "pan", "mute",
    "eq_low", "eq_low_mid", "eq_hi_mid", "eq_hi",
    "low_cut", "compressor",
    "send_mon1", "send_mon2", "send_fx1", "send_fx2",
)


#: Bus faders stored in scenes besides inputs 1-7 and Main L/R.
SCENE_BUSES = ("mon1", "mon2", "fx1", "fx2")

#: Recall filters, as "WHAT TO LOAD" in the FLOW 8 app. Routing (ROUT) has no
#: verified MIDI address, so scenes hold no routing values.
RECALL_SCOPES = ("CH", "FX", "MAIN", "MON")


def recall_scope_of(channel: Any, parameter: str) -> str:
    """Recall scope of one stored value: CH, FX, MAIN or MON."""
    if channel in ("mon1", "mon2") or parameter in ("send_mon1", "send_mon2"):
        return "MON"
    if channel in ("fx1", "fx2") or parameter in ("send_fx1", "send_fx2"):
        return "FX"
    if channel == MAIN_CHANNEL or channel == "main":
        return "MAIN"
    return "CH"


@dataclass
class SceneRecallResult:
    """Outcome of a scene recall: commands accepted vs. rejected by the boundary."""

    name: str
    applied: int = 0
    failed: list = field(default_factory=list)  # (channel_index, parameter, error)


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

        # Undo/redo and scenes. Both only ever dispatch through the public set_*
        # methods below, i.e. through the existing command boundary.
        self._ledger_lock = threading.RLock()
        self._replay_state = threading.local()
        self.ledger = CommandLedger(capacity=LEDGER_CAPACITY, executor=self._replay)
        self.scenes = SceneManager(max_snapshots=SCENE_CAPACITY)

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

                # Open MIDI In if needed, then independently ensure it is listening.
                if not self.midi_in.is_connected:
                    self.midi_in.open()
                    self.midi_in.register_callback(self._on_midi_in_event)
                if not self.midi_in.is_listening:
                    self.midi_in.start()

                self._connected = True
                self._connection_error = None
                self.reconcile_connection()
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
            self.reconcile_connection()

    def check_connection_health(self) -> bool:
        """Detect physical USB unplug or power-off; reconcile to UNSYNCED if gone."""
        with self._lock:
            if not self._connected:
                return False
            try:
                out_id = self.midi_out.find_device_id()
                in_id = self.midi_in.find_device_id()
            except Exception:
                out_id = None
                in_id = None
            if out_id is None or in_id is None:
                logger.warning("FLOW 8 USB MIDI endpoint disappeared; disconnecting and reconciling.")
                self.disconnect()
                self._connection_error = "FLOW 8 USB disconnected"
                return False
            return True

    def reconcile_connection(self) -> None:
        """Reconcile ledger history and state store on reconnect or disconnect."""
        with self._ledger_lock:
            self.ledger.reconcile_connection()
        self.state_store.reconcile_reconnect()
        self._notify_listeners(RECONCILE_EVENT, None)

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
        elif channel in (9, 10, 11, 12):
            bus_by_ch = {9: "mon1", 10: "mon2", 11: "fx1", 12: "fx2"}
            if cc == CC_VOLUME_FADER:
                param_id = f"{bus_by_ch[channel]}.fader"
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
            previous = self._known_value("fader", channel_index)
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_fader,
                clamped, unit="raw",
            )
        elif channel_index == MAIN_CHANNEL:
            previous = self._known_value("fader", channel_index)
            self._dispatch_and_notify(
                self.parameter_engine.set_main_fader, clamped, unit="raw",
            )
        else:
            return
        self._record("fader", channel_index, previous, clamped)

    def set_bus_fader(self, bus_id: str, raw_value: int) -> None:
        """Set master fader for output/FX bus ('mon1', 'mon2', 'fx1', 'fx2')."""
        b_key = bus_id.lower()
        if b_key not in ("mon1", "mon2", "fx1", "fx2"):
            return
        clamped = max(0, min(127, int(raw_value)))
        previous = self._known_value("fader", b_key)
        self._dispatch_and_notify(
            self.parameter_engine.bus(b_key).set_fader,
            clamped, unit="raw",
        )
        self._record("fader", b_key, previous, clamped)

    def set_mute(self, channel_index: int, muted: bool) -> None:
        """Set mute state (1..7 for input strips)."""
        if 1 <= channel_index <= 7:
            previous = self._known_value("mute", channel_index)
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_mute, bool(muted),
            )
            self._record("mute", channel_index, previous, bool(muted))

    def set_pan(self, channel_index: int, raw_value: int) -> None:
        """Set pan/balance (1..7 for input strips, 8 for Main bus)."""
        clamped = max(0, min(127, int(raw_value)))
        if 1 <= channel_index <= 7:
            previous = self._known_value("pan", channel_index)
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_pan,
                clamped, unit="raw",
            )
        elif channel_index == MAIN_CHANNEL:
            previous = self._known_value("pan", channel_index)
            self._dispatch_and_notify(
                self.parameter_engine.set_main_balance, clamped, unit="raw",
            )
        else:
            return
        self._record("pan", channel_index, previous, clamped)

    def set_phantom(self, channel_index: int, enabled: bool) -> None:
        """Set +48V phantom power (Channels 1 and 2 only).

        Never recorded in the ledger and never part of a scene: undo, redo and
        scene recall must not be able to energise or de-energise the relay.
        """
        if channel_index in (1, 2):
            self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_phantom,
                bool(enabled),
            )

    def set_gain(self, channel_index: int, value: Union[int, float], unit: str = "raw") -> None:
        """Set Preamp Gain (Channels 1 to 4 only).

        Unit: 'raw' (0-127) or 'dB' (-20.0 to +60.0 dB).

        Preamp gain is blocked by the safety policy (SR-05): this always raises while the policy
        blocks it, before any state is read or written. The command boundary refuses it as well.
        """
        if "gain" in BLOCKED_PARAMETER_TYPES:
            raise Flow8CommandRejectedError(
                f"[{BLOCKED_PARAMETER_TYPES['gain']}] Preamp gain is blocked by safety policy; nothing was sent.")
        if 1 <= channel_index <= 4:
            previous = self._known_value("gain", channel_index)
            log_entry = self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_gain,
                value, unit=unit,
            )
            raw = log_entry.raw_midi_prepared if log_entry else None
            if raw is not None:
                self._record("gain", channel_index, previous, raw)

    def set_low_cut(self, channel_index: int, value: Union[int, float], unit: str = "raw") -> None:
        """Set Low Cut filter frequency (Channels 1 to 4 only).

        Unit: 'raw' (0-127) or 'Hz' (20.0 to 600.0 Hz).
        """
        if 1 <= channel_index <= 4:
            previous = self._known_value("low_cut", channel_index)
            log_entry = self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_low_cut,
                value, unit=unit,
            )
            raw = log_entry.raw_midi_prepared if log_entry else None
            if raw is not None:
                self._record("low_cut", channel_index, previous, raw)

    def set_compressor(self, channel_index: int, value: Union[int, float], unit: str = "raw") -> None:
        """Set 1-Knob Dynamics Compressor intensity (Channels 1 to 4 only).

        Unit: 'raw' (0-127) or '%' (0.0 to 100.0%).
        """
        if 1 <= channel_index <= 4:
            previous = self._known_value("compressor", channel_index)
            log_entry = self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_compressor,
                value, unit=unit,
            )
            raw = log_entry.raw_midi_prepared if log_entry else None
            if raw is not None:
                self._record("compressor", channel_index, previous, raw)

    def set_eq_band(
        self,
        channel_index: int,
        band: str,
        value: Union[int, float],
        unit: str = "raw"
    ) -> None:
        """Set 4-Band Parametric EQ gain (Channels 1 to 7).

        Band: 'low', 'low_mid', 'hi_mid', or 'hi'.
        Unit: 'raw' (0-127) or 'dB' (-15.0 to +15.0 dB).
        """
        b_key = band.lower().replace("-", "_")
        param_type = f"eq_{b_key}"
        if 1 <= channel_index <= 7:
            previous = self._known_value(param_type, channel_index)
            log_entry = self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_eq_band,
                band, value, unit=unit,
            )
            raw = log_entry.raw_midi_prepared if log_entry else None
            if raw is not None:
                self._record(param_type, channel_index, previous, raw)

    def set_send(
        self,
        channel_index: int,
        target: str,
        value: Union[int, float],
        unit: str = "raw"
    ) -> None:
        """Set auxiliary send level to monitor or FX (Channels 1 to 7).

        Target: 'mon1', 'mon2', 'fx1', or 'fx2'.
        Unit: 'raw' (0-127) or 'dB' (-70.0 to +10.0 dB).
        """
        t_key = target.lower()
        param_type = f"send_{t_key}"
        if 1 <= channel_index <= 7:
            previous = self._known_value(param_type, channel_index)
            log_entry = self._dispatch_and_notify(
                self.parameter_engine.channel(channel_index).set_send,
                target, value, unit=unit,
            )
            raw = log_entry.raw_midi_prepared if log_entry else None
            if raw is not None:
                self._record(param_type, channel_index, previous, raw)

    # -- Presets & FX Profiles (CueAir adaptation) ----------------------------

    def list_channel_presets(self, category: Optional[str] = None):
        """List available curated channel presets, optionally filtered by category."""
        from .presets import list_channel_presets
        return list_channel_presets(category)

    def get_channel_preset(self, preset_id: str):
        """Retrieve a channel preset definition by ID."""
        from .presets import get_channel_preset
        return get_channel_preset(preset_id)

    def apply_channel_preset(
        self,
        channel_index: int,
        preset_id: str,
        preserve_levels: bool = True
    ) -> bool:
        """Apply an audio engineering preset to a channel strip.

        Level Preservation Guarantee:
        When preserve_levels is True, the channel's fader volume, pan/balance,
        and analog preamp gain are left unchanged, ensuring acoustic stability.
        All modified parameters are grouped into an atomic batch for full undo/redo.
        """
        from .presets import get_channel_preset
        preset = get_channel_preset(preset_id)
        if preset is None or not (1 <= channel_index <= 7):
            return False

        with self._ledger_lock:
            self.begin_batch()
            try:
                # Apply 4-band Parametric EQ
                self.set_eq_band(channel_index, "low", preset.eq_low_db, unit="dB")
                self.set_eq_band(channel_index, "low_mid", preset.eq_low_mid_db, unit="dB")
                self.set_eq_band(channel_index, "hi_mid", preset.eq_hi_mid_db, unit="dB")
                self.set_eq_band(channel_index, "hi", preset.eq_hi_db, unit="dB")

                # Apply Low Cut (Channels 1-4)
                if channel_index <= 4 and preset.low_cut_hz is not None:
                    self.set_low_cut(channel_index, preset.low_cut_hz, unit="Hz")

                # Apply Compressor (Channels 1-4)
                if channel_index <= 4 and preset.compressor_percent is not None:
                    self.set_compressor(channel_index, preset.compressor_percent, unit="%")
            finally:
                self.end_batch()
                self._notify_listeners(STATE_CHANGED_EVENT, None)

        return True

    def list_fx_presets(self, group: Optional[str] = None):
        """List available FX starting points, optionally filtered by group."""
        from .presets import list_fx_presets
        return list_fx_presets(group)

    def get_fx_preset(self, preset_id: str):
        """Retrieve an FX preset definition by ID."""
        from .presets import get_fx_preset
        return get_fx_preset(preset_id)

    # -- Undo / redo ledger ---------------------------------------------------

    @staticmethod
    def _param_id(parameter: str, channel_index: Any) -> str:
        if isinstance(channel_index, str):
            return f"{channel_index}.{parameter}"
        if channel_index == MAIN_CHANNEL:
            return "main.balance" if parameter == "pan" else f"main.{parameter}"
        return f"ch{channel_index}.{parameter}"

    def _known_value(self, parameter: str, channel_index: int) -> Optional[Any]:
        """Last software command, else last hardware observation, else None.

        The state store's start-up defaults are app assumptions, not values the
        mixer is known to hold, so they are never used as an undo target or a
        scene value: restoring a guess could mute or blast a live channel.
        """
        state = self.state_store.get_parameter(self._param_id(parameter, channel_index))
        if state is None or state.provenance == ParameterProvenance.UNSYNCED:
            return None
        raw = state.commanded_raw_midi
        if raw is None:
            raw = state.observed_raw_midi
        if raw is None:
            return None
        return bool(raw) if parameter == "mute" else int(raw)

    @contextmanager
    def _replaying(self) -> Iterator[None]:
        self._replay_state.active = True
        try:
            yield
        finally:
            self._replay_state.active = False

    def _record(self, parameter: str, channel_index: int, previous: Any, new: Any) -> None:
        """Record an accepted change. Called only after the boundary accepted it."""
        if getattr(self._replay_state, "active", False) or previous is None:
            return
        with self._ledger_lock:
            self.ledger.push(
                CommandLedger.make_record(parameter, channel_index, previous, new)
            )

    def _replay(self, parameter_type: str, channel_index: Any, value: Any) -> None:
        """Ledger executor: replay through the public setters (and so the boundary)."""
        if isinstance(channel_index, str) and parameter_type == "fader":
            self.set_bus_fader(channel_index, value)
        elif parameter_type == "fader":
            self.set_fader(channel_index, value)
        elif parameter_type == "pan":
            self.set_pan(channel_index, value)
        elif parameter_type == "mute":
            self.set_mute(channel_index, bool(value))
        elif parameter_type == "gain":
            self.set_gain(channel_index, value)
        elif parameter_type == "low_cut":
            self.set_low_cut(channel_index, value)
        elif parameter_type == "compressor":
            self.set_compressor(channel_index, value)
        elif parameter_type.startswith("eq_"):
            band = parameter_type[3:]
            self.set_eq_band(channel_index, band, value)
        elif parameter_type.startswith("send_"):
            target = parameter_type[5:]
            self.set_send(channel_index, target, value)
        else:
            raise ValueError(f"{parameter_type!r} cannot be replayed")

    def begin_batch(self) -> None:
        """Start a drag gesture: its changes become one undoable step."""
        with self._ledger_lock:
            self.ledger.end_batch()  # commit a gesture whose release was missed
            self.ledger.begin_batch()

    def end_batch(self) -> int:
        """Finish a drag gesture; returns the number of undo steps it produced."""
        with self._ledger_lock:
            return self.ledger.end_batch()

    def undo(self) -> tuple[CommandRecord, ...]:
        """Re-send the previous values of the newest step; () when nothing to undo.

        Raises if the boundary rejects a replay; the step then stays undoable.
        """
        try:
            with self._ledger_lock, self._replaying():
                if self.ledger.undo() is None:
                    return ()
                return self.ledger.last_applied
        finally:
            self._notify_listeners(STATE_CHANGED_EVENT, None)

    def redo(self) -> tuple[CommandRecord, ...]:
        """Re-send the values of the newest undone step; () when nothing to redo."""
        try:
            with self._ledger_lock, self._replaying():
                if self.ledger.redo() is None:
                    return ()
                return self.ledger.last_applied
        finally:
            self._notify_listeners(STATE_CHANGED_EVENT, None)

    # -- Scenes ---------------------------------------------------------------

    def known_mix_state(self) -> dict[Any, dict[str, Any]]:
        """Known values of inputs 1-7, Main L/R and the MON/FX bus faders.

        Values come from software commands or hardware observations only; a
        parameter nothing has set or reported is left out rather than guessed.
        +48V and preamp gain are never included.
        """
        state: dict[Any, dict[str, Any]] = {}
        for channel in list(range(1, MAIN_CHANNEL + 1)) + list(SCENE_BUSES):
            if isinstance(channel, str):
                parameters = ("fader",)
            elif channel == MAIN_CHANNEL:
                parameters = ("fader", "pan")
            else:
                parameters = REVERSIBLE_PARAMETERS
            values = {
                parameter: value
                for parameter in parameters
                if (value := self._known_value(parameter, channel)) is not None
            }
            if values:
                state[channel] = values
        return state

    def capture_scene(self, name: str) -> SceneSnapshot:
        """Store the known mix values (see known_mix_state) as a named scene."""
        state = self.known_mix_state()
        if not state:
            raise ValueError(
                "No commanded or observed fader, pan or mute values to capture; "
                "nothing was stored."
            )
        return self.scenes.save_snapshot(name, state)

    def recall_scene(self, name: str, scope: Optional[Iterable[str]] = None) -> SceneRecallResult:
        """Dispatch a stored scene through the boundary as one undoable step.

        scope limits the recall to some RECALL_SCOPES (None = all). Raises
        KeyError for an unknown scene. Commands the boundary rejects are
        reported in the result, not hidden; the rest are still applied.
        """
        snapshot = self.scenes.get(name)
        return self.apply_mix_state(snapshot.name, snapshot.parameters, scope)

    def apply_mix_state(self, label: str, parameters: Mapping[Any, Mapping[str, Any]],
                        scope: Optional[Iterable[str]] = None) -> SceneRecallResult:
        """Send stored mix values as one undoable step, filtered by recall scope."""
        scopes = set(RECALL_SCOPES) if scope is None else {str(s).upper() for s in scope}
        unknown = scopes - set(RECALL_SCOPES)
        if unknown:
            raise ValueError(f"unknown recall scope: {sorted(unknown)}")
        result = SceneRecallResult(name=label)
        with self._ledger_lock:
            self.begin_batch()
            try:
                for channel, values in parameters.items():
                    for parameter in REVERSIBLE_PARAMETERS:
                        if parameter not in values or recall_scope_of(channel, parameter) not in scopes:
                            continue
                        try:
                            self._replay(parameter, channel, values[parameter])
                            result.applied += 1
                        except Exception as error:
                            logger.exception(
                                "Scene %r: %s on channel %s was not sent", label, parameter, channel
                            )
                            result.failed.append((channel, parameter, str(error)))
            finally:
                self.end_batch()
                self._notify_listeners(STATE_CHANGED_EVENT, None)
        return result
