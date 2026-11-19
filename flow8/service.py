"""Application Service for Behringer FLOW 8 Workstation.

Orchestrates the communication chain according to the architectural rules:
    UI -> Application Service -> Parameter Engine -> Command Boundary -> MIDI Driver

Handles MIDI port lifecycle, command dispatch, and inbound observation recording.
Inbound CC handling is not a claim that the FLOW 8 provides complete two-way sync.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional

logger = logging.getLogger(__name__)

from flow8.command_boundary import Flow8CommandBoundary, Flow8CommandRejectedError
from flow8.safety import BLOCKED_PARAMETER_TYPES
from flow8.ledger import CommandLedger, CommandRecord
from flow8.midi_in import Flow8MidiIn
from flow8.midi_out import Flow8MidiOut
from flow8.parameter_engine import Flow8ParameterEngine
from flow8.parameter_mapping import fader_midi_to_db, pan_midi_to_percent
from flow8.scenes import SceneManager, SceneSnapshot
from flow8.state_model import EventSource, Flow8StateStore, ParameterProvenance, ParameterState
from flow8.telemetry import TelemetryStats, decode, inbound_parameter_map, observed_value
from flow8.transport_router import TRANSPORT_FEATURES, TransportRouter


LEDGER_CAPACITY = 50
SCENE_CAPACITY = 15
#: How often the link watchdog checks the endpoints and retries a lost mixer.
WATCHDOG_INTERVAL_S = 1.0
RECONNECT_INTERVAL_S = 2.0
#: A staged plan is trusted for this long, and at most this many are remembered.
PREVIEW_TTL_S = 300.0
MAX_PENDING_PREVIEWS = 32
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

    def __init__(
        self,
        auto_connect: bool = True,
        watchdog_interval: float = WATCHDOG_INTERVAL_S,
        reconnect_interval: float = RECONNECT_INTERVAL_S,
    ) -> None:
        self.state_store = Flow8StateStore()
        self.midi_out = Flow8MidiOut()
        self.midi_in = Flow8MidiIn()
        # Single-writer transport router: every boundary command is routed to
        # exactly one of USB MIDI / BLE according to the active mode.
        self._ble_transport: Any = None
        self._transport_router = TransportRouter(
            self.midi_out, ble_provider=lambda: self._ble_transport
        )
        self.command_boundary = Flow8CommandBoundary(
            midi_out=self.midi_out,
            state_store=self.state_store,
            transport_router=self._transport_router,
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
        self._meter_listeners: list[Callable[[dict[str, dict[str, float]]], None]] = []
        self._latest_meters: dict[str, dict[str, float]] = {}
        self._last_meter_time: float = 0.0
        self._active_bus: str = "main"
        self._active_view: str = "mixer"

        # Undo/redo and scenes. Both only ever dispatch through the public set_*
        # methods below, i.e. through the existing command boundary.
        self._ledger_lock = threading.RLock()
        self._replay_state = threading.local()
        self.ledger = CommandLedger(capacity=LEDGER_CAPACITY, executor=self._replay)
        self.scenes = SceneManager(max_snapshots=SCENE_CAPACITY)
        # Known mix state captured before the most recent committed change plan.
        # Kept apart from the 15 user scene slots so an auto snapshot never evicts one.
        self._pre_change: Optional[SceneSnapshot] = None

        # Inbound telemetry: observation only, mapped by the verified allowlist.
        self.telemetry = TelemetryStats()
        self._inbound_map = inbound_parameter_map()

        # Link watchdog: notices an unplugged mixer and reconnects without a restart.
        self._watchdog_interval = max(0.05, float(watchdog_interval))
        self._reconnect_interval = max(0.05, float(reconnect_interval))
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()
        self._auto_reconnect = bool(auto_connect)
        self._last_reconnect_attempt = 0.0

        # Staged change plans: guard -> preview snapshot, so commit can refuse a plan
        # whose targeted values changed after the engineer reviewed them.
        self._preview_lock = threading.Lock()
        self._previews: dict[str, dict[str, Any]] = {}
        self._transport_mode: str = "usb_midi"

        if auto_connect:
            self.connect()
            self.start_watchdog()

    @property
    def transport_mode(self) -> str:
        """Active control transport mode: 'usb_midi', 'ble', or 'hybrid'."""
        with self._lock:
            return self._transport_mode

    def set_transport_mode(self, mode: str) -> str:
        """Switch between 'usb_midi', 'ble', and 'hybrid' (BLE faders + USB rest/meters).

        The router enforces the single-writer policy: in 'ble' mode only the
        verified BLE fader set (strips 1-6) is accepted; everything else is
        rejected explicitly instead of silently falling back to USB.
        """
        m_key = str(mode or "usb_midi").lower()
        if m_key not in ("usb_midi", "ble", "hybrid"):
            raise ValueError(f"Unsupported transport mode: {mode!r}")
        self._transport_router.set_mode(m_key)
        with self._lock:
            self._transport_mode = m_key
            ble = self._ble_transport
        if m_key in ("ble", "hybrid"):
            if ble is None:
                from flow8.ble_transport import BleTransport
                ble = BleTransport(
                    on_parameter=self._on_ble_parameter,
                    on_status=lambda _st: self._notify_listeners(STATE_CHANGED_EVENT, None),
                    on_snapshot_names=lambda _names: self._notify_listeners(
                        STATE_CHANGED_EVENT, None
                    ),
                )
                with self._lock:
                    self._ble_transport = ble
            ble.start()
        elif ble is not None:
            ble.stop()
        self._notify_listeners(STATE_CHANGED_EVENT, None)
        return m_key

    def ble_status_snapshot(self) -> dict[str, Any]:
        """Return live BLE transport status (connected, authenticated, device, rx/tx)."""
        with self._lock:
            ble = self._ble_transport
        if ble is None:
            return {
                "connected": False,
                "authenticated": False,
                "device": None,
                "address": None,
                "packetsRx": 0,
                "packetsTx": 0,
                "snapshotNames": [],
                "error": None,
            }
        return ble.status_snapshot()

    def request_ble_dump(self) -> bool:
        """Send Type 0x4B BLE dump trigger if BLE transport is connected."""
        with self._lock:
            ble = self._ble_transport
        if ble is None:
            return False
        return bool(ble.request_dump_trigger())

    def _on_ble_parameter(self, param_id: str, raw_midi: int) -> None:
        """Record decoded BLE hardware notification as OBSERVED without echoing."""
        try:
            self.state_store.set_observed_value(
                param_id=param_id,
                value=raw_midi,
                raw_midi_value=raw_midi,
                source=EventSource.PHYSICAL_HARDWARE,
            )
        except Exception:
            return
        self._notify_listeners(param_id, raw_midi)

    @property
    def active_bus(self) -> str:
        """Currently selected Sends-on-Fader bus ('main', 'mon1', 'mon2', 'fx1', 'fx2')."""
        with self._lock:
            return self._active_bus

    def set_active_bus(self, bus_id: str) -> str:
        """Set the active Sends-on-Fader bus and notify UI listeners if changed."""
        b_key = str(bus_id or "main").lower()
        if b_key not in ("main", "mon1", "mon2", "fx1", "fx2"):
            raise ValueError(f"Unsupported bus: {bus_id!r}")
        with self._lock:
            if self._active_bus == b_key:
                return self._active_bus
            self._active_bus = b_key
        self._notify_listeners(STATE_CHANGED_EVENT, None)
        return b_key

    @property
    def active_view(self) -> str:
        """Currently selected workstation view mode ('mixer' or 'stage')."""
        with self._lock:
            return self._active_view

    def set_active_view(self, view: str) -> str:
        """Set the active workstation view mode ('mixer' or 'stage') and notify listeners."""
        v_key = str(view or "mixer").lower()
        if v_key not in ("mixer", "stage"):
            raise ValueError(f"Unsupported view mode: {view!r}")
        with self._lock:
            if self._active_view == v_key:
                return self._active_view
            self._active_view = v_key
        self._notify_listeners(STATE_CHANGED_EVENT, None)
        return v_key

    def add_meter_listener(self, listener: Callable[[dict[str, dict[str, float]]], None]) -> None:
        """Register listener for measured USB audio meter frames."""
        with self._lock:
            if listener not in self._meter_listeners:
                self._meter_listeners.append(listener)

    def remove_meter_listener(self, listener: Callable[[dict[str, dict[str, float]]], None]) -> None:
        with self._lock:
            if listener in self._meter_listeners:
                self._meter_listeners.remove(listener)

    def publish_meters(self, levels: Mapping[str, Mapping[str, float]]) -> None:
        """Broadcast measured USB capture meter levels to registered UI listeners."""
        clean = {
            str(k): {
                "peak": round(float(v.get("peak", -120.0)), 1),
                "rms": round(float(v.get("rms", -120.0)), 1),
            }
            for k, v in levels.items()
        }
        with self._lock:
            self._latest_meters = clean
            self._last_meter_time = time.monotonic()
            callbacks = list(self._meter_listeners)
        for cb in callbacks:
            try:
                cb(clean)
            except Exception:
                logger.exception("FLOW 8 meter listener failed")

    @property
    def meter_feed_live(self) -> bool:
        with self._lock:
            return self._last_meter_time > 0.0 and (time.monotonic() - self._last_meter_time) < 2.0

    @property
    def latest_meters(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return dict(self._latest_meters)

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

    @property
    def control_connected(self) -> bool:
        """True when the *active control transport* is connected.

        USB audio meters keep flowing over MIDI IN regardless of this flag;
        this reports only whether commands can currently be dispatched.
        """
        mode = self._transport_router.mode
        if mode == "usb_midi":
            return self.midi_out.is_connected
        with self._lock:
            ble = self._ble_transport
        if ble is None:
            return False
        snap = ble.status_snapshot()
        return bool(snap.get("connected") and snap.get("authenticated"))

    def transport_status(self) -> dict[str, Any]:
        """Connection/transport/auth/error snapshot for UI and LAN hub."""
        mode = self._transport_router.mode
        with self._lock:
            ble = self._ble_transport
        ble_snap = ble.status_snapshot() if ble is not None else {
            "connected": False,
            "authenticated": False,
            "deviceName": None,
            "deviceAddress": None,
            "error": None,
        }
        last_ble_error = ble_snap.get("error")
        return {
            "mode": mode,
            "usb": {
                "connected": self.midi_out.is_connected,
                "listening": self.midi_in.is_listening,
                "metersLive": self.meter_feed_live,
                "error": self._connection_error,
            },
            "ble": {
                "connected": bool(ble_snap.get("connected")),
                "authenticated": bool(ble_snap.get("authenticated")),
                "deviceName": ble_snap.get("device"),
                "deviceAddress": ble_snap.get("address"),
                "packetsRx": ble_snap.get("packetsRx", 0),
                "packetsTx": ble_snap.get("packetsTx", 0),
                "dumpChunks": ble_snap.get("dumpChunks", 0),
                "dumpBytes": ble_snap.get("dumpBytes", 0),
                "lastError": last_ble_error,
                "error": last_ble_error,
            },
            "controlConnected": self.control_connected,
            "lastError": (
                last_ble_error
                if mode in ("ble", "hybrid") and last_ble_error
                else self._connection_error
            ),
            "features": TRANSPORT_FEATURES.get(mode, {}),
            "featuresByTransport": TRANSPORT_FEATURES,
        }

    def state_sync_snapshot(self) -> dict[str, Any]:
        """Per-parameter synchronization rollup for status reporting."""
        counts: dict[str, int] = {}
        divergent: list[str] = []
        for param_id, snap in self.state_store.get_all_parameters().items():
            key = str(snap.get("sync_status", "unknown"))
            counts[key] = counts.get(key, 0) + 1
            if key == "divergent":
                divergent.append(param_id)
        return {
            "counts": counts,
            "divergent": divergent,
            "note": (
                "commanded/observed values are tracked; hardware verification "
                "requires an explicit observed confirmation (3068-byte state "
                "dump decoding is not yet verified and is intentionally "
                "unsupported)"
            ),
        }

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

    def connect(self, quiet: bool = False) -> bool:
        """Attempt to locate and open the FLOW 8 hardware endpoints.

        `quiet` is for the watchdog's periodic retries: a missing mixer is normal
        there and must not fill the log with tracebacks.
        """
        with self._lock:
            try:
                # Open MIDI Out
                if not self.midi_out.is_connected:
                    self.midi_out.open()

                # Open MIDI In if needed, then independently ensure it is listening.
                if not self.midi_in.is_connected:
                    self.midi_in.open()
                # register_callback is idempotent, so a reconnect never doubles events.
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
                if quiet:
                    logger.debug("FLOW 8 MIDI connection retry failed: %s", e)
                else:
                    logger.exception("FLOW 8 MIDI connection failed")
                return False

    def disconnect(self) -> None:
        """Close the endpoints on purpose: auto-reconnect stays off until asked."""
        self._auto_reconnect = False
        with self._lock:
            ble = self._ble_transport
        if ble is not None:
            ble.stop()
        self._drop_connection()

    def _drop_connection(self) -> None:
        """Close endpoints after an unplug. Does not change the auto-reconnect wish."""
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
                self._drop_connection()
                self._connection_error = "FLOW 8 USB disconnected"
                return False
            return True

    # -- Link watchdog: unplug detection and auto-reconnect -------------------

    @property
    def watchdog_running(self) -> bool:
        thread = self._watchdog_thread
        return thread is not None and thread.is_alive()

    @property
    def auto_reconnect(self) -> bool:
        return self._auto_reconnect

    def set_auto_reconnect(self, enabled: bool) -> None:
        """Remember whether a lost mixer should be re-opened automatically."""
        self._auto_reconnect = bool(enabled)
        if enabled:
            self.start_watchdog(auto_reconnect=True)
        else:
            self.stop_watchdog()

    def start_watchdog(self, auto_reconnect: bool = True) -> None:
        """Start one background thread that notices an unplug and retries the ports."""
        with self._lock:
            self._auto_reconnect = bool(auto_reconnect)
            if self.watchdog_running:
                return
            self._watchdog_stop.clear()
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, name="flow8-link-watchdog", daemon=True,
            )
            self._watchdog_thread.start()

    def stop_watchdog(self) -> None:
        self._watchdog_stop.set()
        thread = self._watchdog_thread
        self._watchdog_thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _watchdog_loop(self) -> None:
        while not self._watchdog_stop.wait(self._watchdog_interval):
            try:
                if self._connected:
                    self.check_connection_health()
                    continue
                if not self._auto_reconnect:
                    continue
                now = time.monotonic()
                if now - self._last_reconnect_attempt < self._reconnect_interval:
                    continue
                self._last_reconnect_attempt = now
                if self.connect(quiet=True):
                    logger.info("FLOW 8 reconnected; state was reconciled to UNSYNCED")
            except Exception:
                logger.exception("FLOW 8 link watchdog iteration failed")

    def reconcile_connection(self) -> None:
        """Reconcile ledger history and state store on reconnect or disconnect."""
        with self._ledger_lock:
            self.ledger.reconcile_connection()
        self.state_store.reconcile_reconnect()
        self._notify_listeners(RECONCILE_EVENT, None)

    def _on_midi_in_event(self, event: dict) -> None:
        """Record allowlisted inbound CC as OBSERVED; never echo it as a command.

        Runs on the MIDI driver's callback thread. It only writes to the thread-safe
        state store and notifies listeners, so it can never send MIDI out. Any CC
        pair the verified allowlist does not know is counted and ignored.
        """
        try:
            decoded = decode(event, self._inbound_map)
        except Exception:
            logger.exception("Could not decode inbound MIDI event: %r", event)
            return
        self.telemetry.record(decoded)
        if not decoded.mapped or decoded.kind != "cc":
            return

        value = observed_value(decoded)
        try:
            self.state_store.set_observed_value(
                param_id=decoded.param_id,
                value=value,
                raw_midi_value=decoded.value,
                source=EventSource.PHYSICAL_HARDWARE,
            )
        except KeyError:
            return
        except Exception:
            logger.exception(
                "Failed to record inbound FLOW 8 MIDI observation: "
                "param=%s channel=%s cc=%s value=%s",
                decoded.param_id, decoded.channel, decoded.controller, decoded.value,
            )
            return

        self._notify_listeners(decoded.param_id, value)

    def telemetry_status(self) -> dict[str, Any]:
        """Inbound telemetry counters plus the link state, for the hub and the probe."""
        status = self.telemetry.snapshot()
        status.update({
            "midiInOpen": self.midi_in_open,
            "listening": self.midi_in_listening,
            "device": self.midi_in.device_info[1],
            "watchdog": self.watchdog_running,
            "autoReconnect": self._auto_reconnect,
        })
        return status
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
        preserve_levels: bool = True,
        scopes: Optional[list[str]] = None,
    ) -> bool:
        """Apply an audio engineering preset to a channel strip.

        Level Preservation Guarantee:
        When preserve_levels is True, the channel's fader volume, pan/balance,
        and analog preamp gain are left unchanged, ensuring acoustic stability.
        All modified parameters are grouped into an atomic batch for full undo/redo.
        Optional ``scopes`` filters which sections apply ("eq", "low_cut", "compressor").
        """
        from .presets import get_channel_preset
        preset = get_channel_preset(preset_id)
        if preset is None or not (1 <= channel_index <= 7):
            return False

        active_scopes = {s.lower() for s in scopes} if scopes is not None else {"eq", "low_cut", "compressor"}

        with self._ledger_lock:
            self.begin_batch()
            try:
                if "eq" in active_scopes:
                    self.set_eq_band(channel_index, "low", preset.eq_low_db, unit="dB")
                    self.set_eq_band(channel_index, "low_mid", preset.eq_low_mid_db, unit="dB")
                    self.set_eq_band(channel_index, "hi_mid", preset.eq_hi_mid_db, unit="dB")
                    self.set_eq_band(channel_index, "hi", preset.eq_hi_db, unit="dB")

                # Apply Low Cut (Channels 1-4)
                if "low_cut" in active_scopes and channel_index <= 4 and preset.low_cut_hz is not None:
                    self.set_low_cut(channel_index, preset.low_cut_hz, unit="Hz")

                # Apply Compressor (Channels 1-4)
                if "compressor" in active_scopes and channel_index <= 4 and preset.compressor_percent is not None:
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
        # OBSERVED means the mixer reported this value: that is the current truth.
        # COMMANDED means only this app knows the value; nothing else reported one.
        if state.provenance == ParameterProvenance.OBSERVED and state.observed_raw_midi is not None:
            raw = state.observed_raw_midi
        elif state.commanded_raw_midi is not None:
            raw = state.commanded_raw_midi
        else:
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
        snapshot = self.scenes.save_snapshot(name, state)
        self._notify_listeners(STATE_CHANGED_EVENT, None)
        return snapshot

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

    # -- Staged change plans (F7) --------------------------------------------

    @property
    def pre_change_snapshot(self) -> Optional[SceneSnapshot]:
        """Known mix state captured before the last committed change plan."""
        with self._ledger_lock:
            return self._pre_change

    def _raw_and_provenance(self, param_id: str) -> tuple[Optional[Any], str]:
        """Known raw value and provenance; a start-up assumption counts as unknown."""
        state = self.state_store.get_parameter(param_id)
        if state is None:
            return None, ParameterProvenance.UNSYNCED.value
        if state.provenance == ParameterProvenance.OBSERVED and state.observed_raw_midi is not None:
            raw = state.observed_raw_midi
        else:
            raw = state.commanded_raw_midi
            if raw is None:
                raw = state.observed_raw_midi
        if raw is None or state.provenance == ParameterProvenance.UNSYNCED:
            return None, state.provenance.value
        return (bool(raw) if param_id.endswith(".mute") else int(raw)), state.provenance.value

    def preview_change_plan(self, plan: Any) -> tuple:
        """One preview row per change: current value, provenance, and whether it differs.

        Read-only: no command is dispatched and no state is written.
        """
        from .change_plan import PreviewRow

        rows = []
        for change in plan.changes:
            current, provenance = self._raw_and_provenance(change.parameter_id)
            same = current is not None and current == change.value
            rows.append(PreviewRow(
                channel=change.channel,
                parameter=change.parameter,
                parameter_id=change.parameter_id,
                to_value=change.value,
                from_value=current,
                from_provenance=provenance,
                status="no_change" if same else "change",
                reason=change.reason,
                risk=change.risk,
            ))
        return tuple(rows)

    def stage_change_plan(self, plan: Any) -> tuple:
        """Preview a plan and remember it, returning (rows, guard).

        The guard is the handle the console sends back on commit. It binds the
        preview the engineer saw to the values that were current at that moment.
        """
        rows = self.preview_change_plan(plan)
        guard = uuid.uuid4().hex
        record = {
            "planId": plan.plan_id,
            "changes": tuple((c.channel, c.parameter, c.value) for c in plan.changes),
            "snapshot": tuple((r.parameter_id, r.from_value, r.from_provenance) for r in rows),
            "at": time.monotonic(),
        }
        with self._preview_lock:
            self._previews[guard] = record
            self._prune_previews_locked()
        return rows, guard

    def _prune_previews_locked(self) -> None:
        if len(self._previews) <= MAX_PENDING_PREVIEWS:
            return
        oldest = sorted(self._previews.items(), key=lambda item: item[1]["at"])
        for guard, _ in oldest[: len(self._previews) - MAX_PENDING_PREVIEWS]:
            self._previews.pop(guard, None)

    def _stale_rows_for(self, plan: Any, guard: str, fresh_rows: tuple) -> list[dict[str, Any]]:
        """Consume a guard and list every targeted value that moved since preview."""
        from .change_plan import PreviewRequiredError

        with self._preview_lock:
            record = self._previews.pop(guard, None)
        if record is None:
            raise PreviewRequiredError(
                "This preview expired or was already used. Preview the plan again before committing."
            )
        if time.monotonic() - record["at"] > PREVIEW_TTL_S:
            raise PreviewRequiredError(
                "This preview is older than five minutes. Preview the plan again before committing."
            )
        expected = tuple((c.channel, c.parameter, c.value) for c in plan.changes)
        # The guard is bound to the reviewed changes, not to a request object: the
        # console rebuilds the plan at commit time and gets a fresh plan id.
        if record["changes"] != expected:
            return [{"parameterId": "*", "reason": "plan_changed",
                     "previewFrom": None, "currentFrom": None,
                     "previewProvenance": None, "currentProvenance": None}]

        stale: list[dict[str, Any]] = []
        for row, (param_id, from_value, from_prov) in zip(fresh_rows, record["snapshot"]):
            if (row.parameter_id != param_id
                    or row.from_value != from_value
                    or row.from_provenance != from_prov):
                stale.append({
                    "parameterId": row.parameter_id,
                    "reason": "value_moved",
                    "previewFrom": from_value,
                    "previewProvenance": from_prov,
                    "currentFrom": row.from_value,
                    "currentProvenance": row.from_provenance,
                })
        return stale

    def commit_change_plan(
        self,
        plan: Any,
        guard: Optional[str] = None,
        require_guard: bool = False,
    ) -> Any:
        """Send a reviewed plan as one undoable step, capturing the mix first.

        Every change is validated against the command allowlist before anything
        is sent. With `require_guard` (the console and the LAN API) a live preview
        must exist and nothing may have changed on any targeted parameter since
        then; otherwise the plan is refused as stale and nothing is sent.
        """
        from .change_plan import ChangePlanResult, PreviewRequiredError

        if require_guard and not guard:
            raise PreviewRequiredError(
                "Preview this plan before committing: reviewing the diff is part of the safety contract."
            )

        rows = self.preview_change_plan(plan)
        if guard is not None:
            stale = self._stale_rows_for(plan, guard, rows)
            if stale:
                return ChangePlanResult(
                    plan_id=plan.plan_id,
                    title=plan.title,
                    stale=True,
                    stale_rows=stale,
                    fresh_rows=[row.as_dict() for row in rows],
                    error="The mix changed after this plan was reviewed; nothing was sent.",
                )

        changed = [row for row in rows if row.status == "change"]
        result = ChangePlanResult(
            plan_id=plan.plan_id, title=plan.title, skipped=len(rows) - len(changed)
        )
        if not changed:
            return result

        result.snapshot_label = f"BEFORE {plan.title}"[:60]
        with self._ledger_lock:
            known = self.known_mix_state()
            self._pre_change = (
                SceneSnapshot(result.snapshot_label, deepcopy(known), datetime.now(timezone.utc))
                if known else None
            )
            if self._pre_change is None:
                result.snapshot_label = None

            self.begin_batch()
            applied = []
            try:
                for row in changed:
                    self._replay(row.parameter, row.channel, row.to_value)
                    applied.append(row)
            except Exception as error:
                self.ledger.cancel_batch()
                result.rolled_back = self._rollback(applied)
                result.error = str(error)
                result.failed = [
                    {"channel": row.channel, "parameter": row.parameter, "error": str(error)}
                    for row in applied
                ]
                self._notify_listeners(STATE_CHANGED_EVENT, None)
                return result

            self.end_batch()
            result.applied = len(applied)
            result.undo_ready = self.ledger.can_undo
        self._notify_listeners(STATE_CHANGED_EVENT, None)
        return result

    def _rollback(self, applied: list) -> bool:
        """Re-send the pre-commit values of the changes already sent (no ledger)."""
        complete = True
        with self._replaying():
            for row in reversed(applied):
                if row.from_value is None:
                    complete = False
                    continue
                try:
                    self._replay(row.parameter, row.channel, row.from_value)
                except Exception:
                    complete = False
                    logger.exception(
                        "Change plan rollback failed for %s on %s", row.parameter, row.channel
                    )
        return complete

    def restore_pre_change(self) -> SceneRecallResult:
        """Recall the pre-change snapshot as one undoable step."""
        with self._ledger_lock:
            snapshot = self._pre_change
        if snapshot is None:
            raise ValueError("No pre-change snapshot was captured; commit a plan first.")
        return self.apply_mix_state(snapshot.name, snapshot.parameters)
