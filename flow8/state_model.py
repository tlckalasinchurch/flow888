"""
Behringer FLOW 8 Parameter State Model.
Tracks commanded vs observed values, verification levels, and synchronization status.
Scope: Behringer FLOW 8 ONLY.
"""

import time
import threading
from enum import Enum, auto
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Callable, List

# ---------------------------------------------------------------------------
# Strict Verification Levels
# ---------------------------------------------------------------------------

class VerificationLevel(Enum):
    """
    Strict evidence grades. Each level means exactly what it says, and a weaker
    observation must never be promoted to a stronger one.

    HARDWARE_SPECIFIED   documented hardware feature, no control address evidence
    PROTOCOL_VERIFIED    mapping supported by protocol documentation
    API_ACKNOWLEDGED     only proof is that the Windows MIDI driver accepted a
                         message (midiOutShortMsg returned 0). Says nothing about
                         USB transmission, mixer application, or audio change.
    IMPLEMENTED          implemented in software
    HARDWARE_TESTED      physical mixer behaviour actually observed
    UNKNOWN              capability asserted but evidence absent/unresolved

    API acknowledgement, USB transmission, mixer application, and audible change
    are four different things; only the last may justify HARDWARE_TESTED.
    """
    HARDWARE_SPECIFIED = "HARDWARE_SPECIFIED"
    PROTOCOL_VERIFIED = "PROTOCOL_VERIFIED"
    API_ACKNOWLEDGED = "API_ACKNOWLEDGED"
    IMPLEMENTED = "IMPLEMENTED"
    HARDWARE_TESTED = "HARDWARE_TESTED"
    UNKNOWN = "UNKNOWN"

class SyncStatus(Enum):
    SYNCED = "SYNCED"
    PENDING_DISPATCH = "PENDING_DISPATCH"
    DIVERGENT = "DIVERGENT"
    UNKNOWN = "UNKNOWN"

class EventSource(Enum):
    LOCAL_HOST = "LOCAL_HOST"
    PHYSICAL_HARDWARE = "PHYSICAL_HARDWARE"
    REMOTE_GATEWAY = "REMOTE_GATEWAY"
    SNAPSHOT_LOAD = "SNAPSHOT_LOAD"
    INITIALIZATION = "INITIALIZATION"

# ---------------------------------------------------------------------------
# Parameter State Record
# ---------------------------------------------------------------------------

@dataclass
class ParameterState:
    param_id: str                      # e.g. "ch1.fader", "main.geq_1k"
    channel_index: int                 # 1..8 or 0 for global
    parameter_name: str                # e.g. "fader", "mute", "pan"
    commanded_value: Any               # Last value sent by software
    observed_value: Any                # Last value confirmed by hardware
    sync_status: SyncStatus
    source: EventSource
    timestamp: float                   # Epoch seconds
    verification_level: VerificationLevel
    raw_midi_value: Optional[int] = None
    min_value: Any = 0
    max_value: Any = 127
    unit: str = "raw"                  # "raw", "dB", "%", "bool"
    # Raw-domain mirrors used for sync comparison, independent of whichever
    # engineering unit the caller used (prevents dB-vs-integer false divergence).
    commanded_raw_midi: Optional[int] = None
    observed_raw_midi: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "param_id": self.param_id,
            "channel_index": self.channel_index,
            "parameter_name": self.parameter_name,
            "commanded_value": self.commanded_value,
            "observed_value": self.observed_value,
            "sync_status": self.sync_status.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "verification_level": self.verification_level.value,
            "raw_midi_value": self.raw_midi_value,
            "unit": self.unit,
            "commanded_raw_midi": self.commanded_raw_midi,
            "observed_raw_midi": self.observed_raw_midi
        }

# ---------------------------------------------------------------------------
# Flow8StateStore Implementation
# ---------------------------------------------------------------------------

class Flow8StateStore:
    """
    Central thread-safe state store for all FLOW 8 parameters.
    Maintains synchronization status and disallows unverified claims.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._parameters: Dict[str, ParameterState] = {}
        self._listeners: List[Callable[[ParameterState], None]] = []
        self._initialize_baseline_parameters()

    def _initialize_baseline_parameters(self):
        """Register all verified and specified parameters with strict levels."""
        now = time.time()

        # Phase 2A initial 4 parameters.
        # Phase C.2 correction: the only retained evidence for these is that
        # midiOutShortMsg returned MMSYSERR_NOERROR. No inbound confirmation was
        # ever captured and no operator observation is recorded, so they are
        # graded API_ACKNOWLEDGED -- never HARDWARE_TESTED.
        self._parameters["main.fader"] = ParameterState(
            param_id="main.fader",
            channel_index=8,
            parameter_name="fader",
            commanded_value=0,
            observed_value=None,
            sync_status=SyncStatus.UNKNOWN,
            source=EventSource.INITIALIZATION,
            timestamp=now,
            verification_level=VerificationLevel.API_ACKNOWLEDGED,
            raw_midi_value=0,
            unit="raw"
        )
        self._parameters["ch1.fader"] = ParameterState(
            param_id="ch1.fader",
            channel_index=1,
            parameter_name="fader",
            commanded_value=0,
            observed_value=None,
            sync_status=SyncStatus.UNKNOWN,
            source=EventSource.INITIALIZATION,
            timestamp=now,
            verification_level=VerificationLevel.API_ACKNOWLEDGED,
            raw_midi_value=0,
            unit="raw"
        )
        self._parameters["ch1.mute"] = ParameterState(
            param_id="ch1.mute",
            channel_index=1,
            parameter_name="mute",
            commanded_value=False,
            observed_value=None,
            sync_status=SyncStatus.UNKNOWN,
            source=EventSource.INITIALIZATION,
            timestamp=now,
            verification_level=VerificationLevel.API_ACKNOWLEDGED,
            raw_midi_value=0,
            unit="bool"
        )
        self._parameters["ch1.pan"] = ParameterState(
            param_id="ch1.pan",
            channel_index=1,
            parameter_name="pan",
            commanded_value=64,
            observed_value=None,
            sync_status=SyncStatus.UNKNOWN,
            source=EventSource.INITIALIZATION,
            timestamp=now,
            verification_level=VerificationLevel.API_ACKNOWLEDGED,
            raw_midi_value=64,
            unit="raw"
        )

        # Channels 2-7 Parameters (PROTOCOL_VERIFIED)
        for ch in range(2, 8):
            ch_name = f"ch{ch}"
            self._parameters[f"{ch_name}.fader"] = ParameterState(
                param_id=f"{ch_name}.fader",
                channel_index=ch,
                parameter_name="fader",
                commanded_value=0,
                observed_value=None,
                sync_status=SyncStatus.UNKNOWN,
                source=EventSource.INITIALIZATION,
                timestamp=now,
                verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                raw_midi_value=0,
                unit="raw"
            )
            self._parameters[f"{ch_name}.mute"] = ParameterState(
                param_id=f"{ch_name}.mute",
                channel_index=ch,
                parameter_name="mute",
                commanded_value=False,
                observed_value=None,
                sync_status=SyncStatus.UNKNOWN,
                source=EventSource.INITIALIZATION,
                timestamp=now,
                verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                raw_midi_value=0,
                unit="bool"
            )
            self._parameters[f"{ch_name}.pan"] = ParameterState(
                param_id=f"{ch_name}.pan",
                channel_index=ch,
                # Stereo pairs carry BALANCE, not mono PAN (Phase C.2 F-03).
                parameter_name="balance" if ch >= 5 else "pan",
                commanded_value=64,
                observed_value=None,
                sync_status=SyncStatus.UNKNOWN,
                source=EventSource.INITIALIZATION,
                timestamp=now,
                verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                raw_midi_value=64,
                unit="raw"
            )

        # Channels 1-7 Extended Channel Strip Parameters (PROTOCOL_VERIFIED)
        for ch in range(1, 8):
            c_prefix = f"ch{ch}"
            # 4-Band PEQ (Low, Low-Mid, High-Mid, High)
            for eq_band in ("eq_low", "eq_low_mid", "eq_hi_mid", "eq_hi"):
                self._parameters[f"{c_prefix}.{eq_band}"] = ParameterState(
                    param_id=f"{c_prefix}.{eq_band}",
                    channel_index=ch,
                    parameter_name=eq_band,
                    commanded_value=64,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                    raw_midi_value=64,
                    unit="raw"
                )

            # Sends (Mon 1, Mon 2, FX 1, FX 2)
            for send_name in ("send_mon1", "send_mon2", "send_fx1", "send_fx2"):
                self._parameters[f"{c_prefix}.{send_name}"] = ParameterState(
                    param_id=f"{c_prefix}.{send_name}",
                    channel_index=ch,
                    parameter_name=send_name,
                    commanded_value=0,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                    raw_midi_value=0,
                    unit="raw"
                )

            # Preamp Gain, Low Cut, Compressor (Channels 1-4 only)
            if 1 <= ch <= 4:
                self._parameters[f"{c_prefix}.gain"] = ParameterState(
                    param_id=f"{c_prefix}.gain",
                    channel_index=ch,
                    parameter_name="gain",
                    commanded_value=0,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                    raw_midi_value=0,
                    unit="raw"
                )
                self._parameters[f"{c_prefix}.low_cut"] = ParameterState(
                    param_id=f"{c_prefix}.low_cut",
                    channel_index=ch,
                    parameter_name="low_cut",
                    commanded_value=0,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                    raw_midi_value=0,
                    unit="raw"
                )
                self._parameters[f"{c_prefix}.compressor"] = ParameterState(
                    param_id=f"{c_prefix}.compressor",
                    channel_index=ch,
                    parameter_name="compressor",
                    commanded_value=0,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                    raw_midi_value=0,
                    unit="raw"
                )

            # Compressor on the stereo pairs (Ch 5/6, 7/8): the hardware model
            # states the capability exists, but no verified MIDI control address
            # exists. Registered as UNKNOWN so the gap is visible rather than
            # silently absent. Ch 7 (USB/BT) has no compressor stage at all.
            if ch in (5, 6):
                self._parameters[f"{c_prefix}.compressor"] = ParameterState(
                    param_id=f"{c_prefix}.compressor",
                    channel_index=ch,
                    parameter_name="compressor",
                    commanded_value=None,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.UNKNOWN,
                    unit="raw"
                )

            # +48V Phantom Power (Channels 1-2 only)
            if ch in (1, 2):
                self._parameters[f"{c_prefix}.phantom"] = ParameterState(
                    param_id=f"{c_prefix}.phantom",
                    channel_index=ch,
                    parameter_name="phantom",
                    commanded_value=False,
                    observed_value=None,
                    sync_status=SyncStatus.UNKNOWN,
                    source=EventSource.INITIALIZATION,
                    timestamp=now,
                    verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                    raw_midi_value=0,
                    unit="bool"
                )

        # Output Busses Parameters (PROTOCOL_VERIFIED)
        bus_params = [
            ("main.balance", 8, "balance", 64, "raw"),
            ("mon1.fader", 9, "fader", 0, "raw"),
            ("mon2.fader", 10, "fader", 0, "raw"),
            ("fx1.fader", 11, "fader", 0, "raw"),
            ("fx2.fader", 12, "fader", 0, "raw"),
        ]
        for pid, ch_idx, pname, init_val, p_unit in bus_params:
            self._parameters[pid] = ParameterState(
                param_id=pid,
                channel_index=ch_idx,
                parameter_name=pname,
                commanded_value=init_val,
                observed_value=None,
                sync_status=SyncStatus.UNKNOWN,
                source=EventSource.INITIALIZATION,
                timestamp=now,
                verification_level=VerificationLevel.PROTOCOL_VERIFIED,
                raw_midi_value=init_val if isinstance(init_val, int) else 0,
                unit=p_unit
            )

        # Hardware Specified but unverified protocol features (HARDWARE_SPECIFIED)
        self._parameters["global.ez_gain"] = ParameterState(
            param_id="global.ez_gain",
            channel_index=0,
            parameter_name="ez_gain",
            commanded_value=None,
            observed_value=None,
            sync_status=SyncStatus.UNKNOWN,
            source=EventSource.INITIALIZATION,
            timestamp=now,
            verification_level=VerificationLevel.HARDWARE_SPECIFIED,
            unit="action"
        )

    def subscribe(self, listener: Callable[[ParameterState], None]):
        """Register a callback for state changes."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[ParameterState], None]):
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def set_commanded_value(
        self,
        param_id: str,
        value: Any,
        source: EventSource,
        raw_midi_value: Optional[int] = None
    ) -> ParameterState:
        """Update commanded value when host sends an action."""
        with self._lock:
            if param_id not in self._parameters:
                raise KeyError(f"Unknown parameter ID: {param_id}")

            param = self._parameters[param_id]
            param.commanded_value = value
            param.source = source
            param.timestamp = time.time()
            if raw_midi_value is not None:
                param.raw_midi_value = raw_midi_value
                param.commanded_raw_midi = raw_midi_value

            # Determine sync status. Prefer the raw MIDI domain: the commanded
            # side may be dB/%/Hz while an observed value arriving from hardware
            # is always a raw integer, so mixing units would always diverge.
            if param.observed_value is None:
                param.sync_status = SyncStatus.PENDING_DISPATCH
            elif (param.commanded_raw_midi is not None
                  and param.observed_raw_midi is not None):
                param.sync_status = (
                    SyncStatus.SYNCED
                    if param.commanded_raw_midi == param.observed_raw_midi
                    else SyncStatus.DIVERGENT
                )
            elif param.observed_value == value:
                param.sync_status = SyncStatus.SYNCED
            else:
                param.sync_status = SyncStatus.DIVERGENT

            # Snapshot listeners
            callbacks = list(self._listeners)

        for cb in callbacks:
            try:
                cb(param)
            except Exception:
                pass

        return param

    def set_observed_value(
        self,
        param_id: str,
        value: Any,
        source: EventSource,
        raw_midi_value: Optional[int] = None
    ) -> ParameterState:
        """Update observed value when hardware telemetry arrives."""
        with self._lock:
            if param_id not in self._parameters:
                raise KeyError(f"Unknown parameter ID: {param_id}")

            param = self._parameters[param_id]
            param.observed_value = value
            param.source = source
            param.timestamp = time.time()
            if raw_midi_value is not None:
                param.raw_midi_value = raw_midi_value
                param.observed_raw_midi = raw_midi_value

            if (param.commanded_raw_midi is not None
                    and param.observed_raw_midi is not None):
                param.sync_status = (
                    SyncStatus.SYNCED
                    if param.commanded_raw_midi == param.observed_raw_midi
                    else SyncStatus.DIVERGENT
                )
            elif param.commanded_value == value:
                param.sync_status = SyncStatus.SYNCED
            else:
                param.sync_status = SyncStatus.DIVERGENT

            callbacks = list(self._listeners)

        for cb in callbacks:
            try:
                cb(param)
            except Exception:
                pass

        return param

    def get_parameter(self, param_id: str) -> Optional[ParameterState]:
        with self._lock:
            return self._parameters.get(param_id)

    def get_all_parameters(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._parameters.items()}
