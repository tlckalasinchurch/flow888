"""
Behringer FLOW 8 Command Boundary & Dispatcher.
Enforces strict parameter allowlists, range validation, and command logging.
Scope: Behringer FLOW 8 ONLY.

Phase C.2 dispatch semantics
----------------------------
A command passes through four *distinct* gates, and the log records each one
separately so no consumer can confuse them:

    command_accepted   the boundary accepted and validated the command
    driver_dispatched  midiOutShortMsg returned MMSYSERR_NOERROR (driver queue)
    hardware_applied   the mixer actually applied it -- ALWAYS None (unconfirmed)
    observed_value     value reported back by hardware -- None until inbound sync exists

`midiOutShortMsg` returning 0 proves only that the Windows MIDI driver accepted
the short message. It does NOT prove USB transmission, mixer application, or any
audible change. `hardware_applied` therefore remains None by design; there is no
code path that may set it True without a confirmation channel.
"""

import time
import threading
from dataclasses import dataclass
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from .domain_model import LOGICAL_CHANNELS
from .state_model import Flow8StateStore, EventSource, VerificationLevel, SyncStatus
from .midi_out import Flow8MidiOut, Flow8ValidationError, Flow8NotConnectedError
from .safety import SafetyPolicyError, authorize_command
from .parameter_mapping import (
    fader_db_to_midi,
    pan_percent_to_midi,
    mute_bool_to_midi,
    gain_db_to_midi,
    low_cut_hz_to_midi,
    eq_db_to_midi,
    compressor_percent_to_midi,
)

# In-memory command log window. Totals live in Flow8CommandBoundary.command_counts.
COMMAND_LOG_CAPACITY = 2000

class Flow8CommandError(Exception):
    """Base exception for command boundary errors."""
    pass

class Flow8CommandRejectedError(Flow8CommandError):
    """Raised when a command targets an unverified or disallowed parameter."""
    pass


# ---------------------------------------------------------------------------
# Dispatch status vocabulary (Phase C.2)
# ---------------------------------------------------------------------------

class DispatchStatus:
    """Explicit, non-overlapping dispatch outcomes."""
    REJECTED = "REJECTED"                    # not in allowlist / refused by transport policy
    VALIDATION_FAILED = "VALIDATION_FAILED"  # value out of range / bad type
    ACCEPTED_OFFLINE = "ACCEPTED_OFFLINE"    # validated + state committed, NOT sent
    DRIVER_DISPATCHED = "DRIVER_DISPATCHED"  # handed to WinMM (device may not have applied)
    BLE_WRITE_ACCEPTED = "BLE_WRITE_ACCEPTED"  # GATT write accepted (mixer application unconfirmed)
    DISPATCH_FAILED = "DISPATCH_FAILED"      # connected, but the transport call failed


# MIDI channel assignment for the output/send buses (protocol chart sec. 3)
BUS_MIDI_CHANNELS: Dict[str, int] = {
    "main": 8,
    "mon1": 9,
    "mon2": 10,
    "fx1": 11,
    "fx2": 12,
}

# MIDI channel of each FX engine slot (protocol chart "FX CONTROL"). The FX1/FX2
# *buses* above carry the return level; the *engines* carry preset and parameters.
FX_ENGINE_MIDI_CHANNELS: Dict[str, int] = {
    "fxe1": 13,
    "fxe2": 14,
}

# Buses with a limiter (CC 8) and a 9-band graphic EQ (CC 11-19): MAIN, MON1, MON2.
# GEQ bands in chart order: 62 Hz, 125, 250, 500, 1k, 2k, 4k, 8k, 16 kHz -> geq1..geq9.
LIMITER_GEQ_BUSES = ("main", "mon1", "mon2")
GEQ_BAND_COUNT = 9

#: Allowlist entries sent as a Program Change instead of a Control Change.
PROGRAM_CHANGE = "program_change"


@dataclass
class CommandLogEntry:
    """
    One auditable record of a single command attempt.

    Field semantics are strict (Phase C.2):
    - `raw_midi_sent` is populated ONLY when bytes were actually submitted to the
      driver. It is None for rejected, invalid, offline, and failed commands.
    - `raw_midi_prepared` is the value that was computed, for troubleshooting.
    - `success` means "accepted and processed without a dispatch failure"; it does
      NOT mean the mixer applied anything. Check `dispatch_status` / `driver_dispatched`.
    - `latency_us` is HOST-SIDE function execution time only (validation +
      conversion + WinMM call + state update). It is not USB, mixer, or audio latency.
    """
    timestamp: float
    param_id: str
    target_value: Any
    raw_midi_sent: Optional[int]
    source: EventSource
    success: bool
    latency_us: float
    dispatched_to_hardware: bool = False
    error_message: Optional[str] = None
    # --- Phase C.2 explicit dispatch semantics (backward compatible additions) ---
    command_accepted: bool = True
    driver_dispatched: bool = False
    hardware_applied: Optional[bool] = None
    raw_midi_prepared: Optional[int] = None
    dispatch_status: str = DispatchStatus.ACCEPTED_OFFLINE
    observed_value: Any = None
    verification_level: Optional[VerificationLevel] = None
    midi_channel: Optional[int] = None
    midi_cc: Optional[int] = None
    # Which control transport accepted the command ("usb_midi"/"ble"), if any.
    transport: Optional[str] = None


def _expected_channel_for_param(param_id: str) -> Optional[int]:
    """
    Resolve the MIDI channel a parameter's identity implies.

    This is the identity check that prevents a param ID from ever addressing the
    wrong physical strip: `ch6.*` must resolve to the MIDI channel declared by
    LOGICAL_CHANNELS[6] (which is the Channel 7/8 pair), never to a guessed index.
    """
    prefix = param_id.split(".", 1)[0]
    if prefix.startswith("ch") and prefix[2:].isdigit():
        idx = int(prefix[2:])
        spec = LOGICAL_CHANNELS.get(idx)
        return spec.midi_channel if spec else None
    if prefix in FX_ENGINE_MIDI_CHANNELS:
        return FX_ENGINE_MIDI_CHANNELS[prefix]
    return BUS_MIDI_CHANNELS.get(prefix)


def _build_phase_c_allowlist() -> Dict[str, Dict[str, Any]]:
    """
    Build the active verified parameter allowlist for Behringer FLOW 8.

    MIDI channel numbers are taken from the shared domain model
    (LOGICAL_CHANNELS[n].midi_channel) rather than assumed from the loop index,
    so the logical-strip -> MIDI-channel binding lives in exactly one place.
    """
    al: Dict[str, Dict[str, Any]] = {}

    # Master & Monitor Busses
    for bus_id, midi_ch in BUS_MIDI_CHANNELS.items():
        al[f"{bus_id}.fader"] = {
            "type": "fader", "min": 0, "max": 127,
            "channel": midi_ch, "cc": 7,
        }
    # Main stereo balance (MAIN only, per protocol chart sec. 3)
    al["main.balance"] = {
        "type": "pan", "min": 0, "max": 127,
        "channel": BUS_MIDI_CHANNELS["main"], "cc": 10,
    }

    # Bus limiter and 9-band GEQ on MAIN / MON1 / MON2 (chart: NOT on FX1/2 bus).
    # Owner approval 2026-11-20; documented (E01), not hardware-verified.
    for bus_id in LIMITER_GEQ_BUSES:
        midi_ch = BUS_MIDI_CHANNELS[bus_id]
        al[f"{bus_id}.limiter"] = {"type": "limiter", "min": 0, "max": 127, "channel": midi_ch, "cc": 8}
        for band in range(1, GEQ_BAND_COUNT + 1):
            al[f"{bus_id}.geq{band}"] = {"type": "eq", "min": 0, "max": 127, "channel": midi_ch, "cc": 10 + band}

    # FX engines (MIDI ch 13 / 14): preset select by Program Change 1-16, parameter 1
    # (CC 1, 0-100 %) and parameter 2 (CC 2, A/B switch). FX mute and tap tempo live on
    # channel 16 with the mixer reset and stay out of the allowlist (SR-02 / SR-04).
    for engine_id, midi_ch in FX_ENGINE_MIDI_CHANNELS.items():
        al[f"{engine_id}.preset"] = {
            "type": "fx_preset", "message": PROGRAM_CHANGE, "min": 1, "max": 16,
            "channel": midi_ch, "cc": None,
        }
        al[f"{engine_id}.param1"] = {"type": "fx_param", "min": 0, "max": 127, "channel": midi_ch, "cc": 1}
        al[f"{engine_id}.param2"] = {
            "type": "switch", "min": 0, "max": 127, "boolean": True, "channel": midi_ch, "cc": 2,
        }

    # Input Channels 1-7
    for ch in range(1, 8):
        spec = LOGICAL_CHANNELS.get(ch)
        if spec is None:
            raise RuntimeError(f"Phase C allowlist: no domain model entry for channel {ch}")
        midi_ch = spec.midi_channel
        c_prefix = f"ch{ch}"

        al[f"{c_prefix}.fader"] = {"type": "fader", "min": 0, "max": 127, "channel": midi_ch, "cc": 7}
        al[f"{c_prefix}.mute"] = {"type": "mute", "min": 0, "max": 127, "boolean": True, "channel": midi_ch, "cc": 5}
        al[f"{c_prefix}.pan"] = {"type": "pan", "min": 0, "max": 127, "channel": midi_ch, "cc": 10}
        al[f"{c_prefix}.eq_low"] = {"type": "eq", "min": 0, "max": 127, "channel": midi_ch, "cc": 1}
        al[f"{c_prefix}.eq_low_mid"] = {"type": "eq", "min": 0, "max": 127, "channel": midi_ch, "cc": 2}
        al[f"{c_prefix}.eq_hi_mid"] = {"type": "eq", "min": 0, "max": 127, "channel": midi_ch, "cc": 3}
        al[f"{c_prefix}.eq_hi"] = {"type": "eq", "min": 0, "max": 127, "channel": midi_ch, "cc": 4}
        al[f"{c_prefix}.send_mon1"] = {"type": "send", "min": 0, "max": 127, "channel": midi_ch, "cc": 14}
        al[f"{c_prefix}.send_mon2"] = {"type": "send", "min": 0, "max": 127, "channel": midi_ch, "cc": 15}
        al[f"{c_prefix}.send_fx1"] = {"type": "send", "min": 0, "max": 127, "channel": midi_ch, "cc": 16}
        al[f"{c_prefix}.send_fx2"] = {"type": "send", "min": 0, "max": 127, "channel": midi_ch, "cc": 17}

        # Mic/Line Channels 1-4 only: Preamp Gain, Low Cut, Compressor
        if 1 <= ch <= 4:
            al[f"{c_prefix}.gain"] = {"type": "gain", "min": 0, "max": 127, "channel": midi_ch, "cc": 8}
            al[f"{c_prefix}.low_cut"] = {"type": "low_cut", "min": 0, "max": 127, "channel": midi_ch, "cc": 9}
            al[f"{c_prefix}.compressor"] = {"type": "compressor", "min": 0, "max": 127, "channel": midi_ch, "cc": 11}

        # Mic Channels 1-2 only: +48V Phantom Power
        if ch in (1, 2):
            al[f"{c_prefix}.phantom"] = {
                "type": "mute", "min": 0, "max": 127, "boolean": True,
                "channel": midi_ch, "cc": 12,
            }

    return al


def _validate_allowlist(al: Dict[str, Dict[str, Any]]) -> None:
    """
    Fail-fast structural validation of the allowlist at import time.

    Enforces, for every entry: channel scope, CC scope, value bounds,
    parameter identity (param ID -> MIDI channel), and uniqueness of the
    (MIDI channel, CC) pair so no two parameters can silently collide.
    """
    seen: Dict[tuple, str] = {}
    for param_id, spec in al.items():
        for key in ("type", "min", "max", "channel", "cc"):
            if key not in spec:
                raise RuntimeError(f"Allowlist entry '{param_id}' is missing '{key}'")

        ch = spec["channel"]
        cc = spec["cc"]
        lo = spec["min"]
        hi = spec["max"]

        if not (1 <= ch <= 16):
            raise RuntimeError(f"Allowlist '{param_id}': MIDI channel {ch} out of range 1-16")
        if spec.get("message") == PROGRAM_CHANGE:
            # Program Change only on the FX engine channels, presets 1-16 (never channel 16).
            if ch not in FX_ENGINE_MIDI_CHANNELS.values() or cc is not None or not (1 <= lo <= hi <= 16):
                raise RuntimeError(f"Allowlist '{param_id}': Program Change outside FX engines 1-16")
        elif not (isinstance(cc, int) and 0 <= cc <= 127):
            raise RuntimeError(f"Allowlist '{param_id}': CC {cc} out of range 0-127")
        if not (0 <= lo <= hi <= 127):
            raise RuntimeError(f"Allowlist '{param_id}': invalid bounds min={lo} max={hi}")

        expected = _expected_channel_for_param(param_id)
        if expected is None:
            raise RuntimeError(f"Allowlist '{param_id}': cannot resolve parameter identity")
        if expected != ch:
            raise RuntimeError(
                f"Allowlist identity mismatch for '{param_id}': param ID implies MIDI "
                f"channel {expected}, entry declares {ch}"
            )

        pair = (ch, PROGRAM_CHANGE if cc is None else cc)
        if pair in seen:
            raise RuntimeError(
                f"Allowlist collision: '{param_id}' and '{seen[pair]}' both address "
                f"channel {ch} CC {cc}"
            )
        seen[pair] = param_id


class Flow8CommandBoundary:
    """
    Transactional command gateway between host software and FLOW 8 hardware.
    Enforces parameter allowlist and disallows undocumented writes.
    """

    # Phase C verified command allowlist
    ACTIVE_ALLOWLIST = _build_phase_c_allowlist()

    # Structural self-check: a malformed allowlist fails at import, not at runtime.
    _validate_allowlist(ACTIVE_ALLOWLIST)

    def __init__(
        self,
        midi_out: Flow8MidiOut,
        state_store: Flow8StateStore,
        transport_router: Optional[Any] = None,
    ):
        self._midi_out = midi_out
        self._state_store = state_store
        # Optional TransportRouter (flow8/transport_router.py). When present it
        # is the single writer chooser for every command; when absent the
        # legacy USB-only path below is used unchanged.
        self._transport_router = transport_router
        self._lock = threading.RLock()
        # Bounded window: a long show must not grow memory or per-command copy cost.
        self._log: Deque[CommandLogEntry] = deque(maxlen=COMMAND_LOG_CAPACITY)
        self._counts = {"commands": 0, "accepted": 0, "driverDispatched": 0, "rejected": 0}

    def _append(self, entry: CommandLogEntry) -> None:
        with self._lock:
            self._log.append(entry)
            self._counts["commands"] += 1
            self._counts["accepted"] += bool(entry.command_accepted)
            self._counts["driverDispatched"] += bool(entry.driver_dispatched)
            self._counts["rejected"] += not entry.success

    @property
    def allowlist(self) -> List[str]:
        return list(self.ACTIVE_ALLOWLIST.keys())

    @property
    def command_log(self) -> List[CommandLogEntry]:
        """The newest COMMAND_LOG_CAPACITY entries, oldest first."""
        with self._lock:
            return list(self._log)

    @property
    def command_counts(self) -> Dict[str, int]:
        """Totals since start, including entries that left the bounded log."""
        with self._lock:
            return dict(self._counts)

    def _get_state(self, param_id: str):
        try:
            return self._state_store.get_parameter(param_id)
        except Exception:
            return None

    def execute_command(
        self,
        param_id: str,
        value: Any,
        source: EventSource = EventSource.LOCAL_HOST,
        unit: str = "raw"
    ) -> CommandLogEntry:
        """
        Validate and execute a parameter change.

        On success the commanded value is committed to the state store.
        On a dispatch FAILURE the state store is deliberately NOT updated, so a
        value the mixer never received is never recorded as commanded.
        """
        t0 = time.perf_counter()
        now = time.time()

        # 1. Allowlist Validation
        if param_id not in self.ACTIVE_ALLOWLIST:
            err = f"Parameter '{param_id}' is not in the active FLOW 8 command allowlist."
            entry = CommandLogEntry(
                timestamp=now,
                param_id=param_id,
                target_value=value,
                raw_midi_sent=None,
                source=source,
                success=False,
                latency_us=0.0,
                dispatched_to_hardware=False,
                error_message=err,
                command_accepted=False,
                driver_dispatched=False,
                hardware_applied=None,
                raw_midi_prepared=None,
                dispatch_status=DispatchStatus.REJECTED,
                observed_value=None,
                verification_level=None,
            )
            self._append(entry)
            raise Flow8CommandRejectedError(err)

        spec = self.ACTIVE_ALLOWLIST[param_id]
        raw_midi: int = 0

        # 1b. Safety policy (S1.2): gain is blocked absolutely; +48V ON needs a grant created by the
        # user-confirmation flow. OFF and every other parameter pass. Applies to every caller (service,
        # engine, ledger replay, direct calls) because this is the single choke point.
        try:
            dispatch_scope = authorize_command(param_id, value)
        except SafetyPolicyError as policy_error:
            err = f"Command refused by safety policy: {policy_error}"
            state = self._get_state(param_id)
            entry = CommandLogEntry(
                timestamp=now,
                param_id=param_id,
                target_value=value,
                raw_midi_sent=None,
                source=source,
                success=False,
                latency_us=(time.perf_counter() - t0) * 1e6,
                dispatched_to_hardware=False,
                error_message=err,
                command_accepted=False,
                driver_dispatched=False,
                hardware_applied=None,
                raw_midi_prepared=None,
                dispatch_status=DispatchStatus.REJECTED,
                observed_value=state.observed_value if state else None,
                verification_level=state.verification_level if state else None,
                midi_channel=spec["channel"],
                midi_cc=spec["cc"],
            )
            self._append(entry)
            raise Flow8CommandRejectedError(err) from policy_error

        # 2. Value Conversion & Validation
        try:
            ptype = spec["type"]
            if ptype == "fader":
                if unit == "dB":
                    raw_midi = fader_db_to_midi(value)
                else:
                    raw_midi = int(value)

            elif ptype in ("mute", "switch"):
                # Boolean parameters accept only a genuine boolean or 0/1.
                if isinstance(value, bool):
                    is_muted = value
                elif isinstance(value, int) and value in (0, 1):
                    is_muted = bool(value)
                else:
                    raise ValueError(
                        f"Boolean parameter requires True/False/0/1; got {value!r}"
                    )
                raw_midi = mute_bool_to_midi(is_muted)

            elif ptype == "pan":
                if unit == "%":
                    raw_midi = pan_percent_to_midi(value)
                else:
                    raw_midi = int(value)

            elif ptype == "gain":
                if unit == "dB":
                    raw_midi = gain_db_to_midi(value)
                else:
                    raw_midi = int(value)

            elif ptype == "low_cut":
                if unit == "Hz":
                    raw_midi = low_cut_hz_to_midi(value)
                else:
                    raw_midi = int(value)

            elif ptype == "eq":
                if unit == "dB":
                    raw_midi = eq_db_to_midi(value)
                else:
                    raw_midi = int(value)

            elif ptype == "compressor":
                if unit == "%":
                    raw_midi = compressor_percent_to_midi(value)
                else:
                    raw_midi = int(value)

            elif ptype == "send":
                if unit == "dB":
                    raw_midi = fader_db_to_midi(value)
                else:
                    raw_midi = int(value)
            else:
                raw_midi = int(value)

            # Per-entry bounds (allowlist min/max) then the global MIDI domain.
            lo = spec.get("min", 0)
            hi = spec.get("max", 127)
            if raw_midi < lo:
                raise ValueError(
                    f"Value for '{param_id}' below allowlist minimum {lo}: {raw_midi}"
                )
            if raw_midi > hi:
                raise ValueError(
                    f"Value for '{param_id}' above allowlist maximum {hi}: {raw_midi}"
                )
            if not (0 <= raw_midi <= 127):
                raise ValueError(f"Value for '{param_id}' out of valid range (0-127): {raw_midi}")

        except Exception as e:
            err = f"Value conversion error for '{param_id}': {e}"
            state = self._get_state(param_id)
            entry = CommandLogEntry(
                timestamp=now,
                param_id=param_id,
                target_value=value,
                raw_midi_sent=None,
                source=source,
                success=False,
                latency_us=(time.perf_counter() - t0) * 1e6,
                dispatched_to_hardware=False,
                error_message=err,
                command_accepted=False,
                driver_dispatched=False,
                hardware_applied=None,
                raw_midi_prepared=None,
                dispatch_status=DispatchStatus.VALIDATION_FAILED,
                observed_value=state.observed_value if state else None,
                verification_level=state.verification_level if state else None,
                midi_channel=spec["channel"],
                midi_cc=spec["cc"],
            )
            self._append(entry)
            raise Flow8ValidationError(err)

        # 3. Hardware Dispatch (only if connected)
        dispatch_success = True
        driver_dispatched = False
        transport_used: Optional[str] = None
        transport_rejected: Optional[str] = None
        err_msg = None
        router = self._transport_router
        try:
            if router is not None:
                # The router enforces the single-writer transport policy (USB /
                # BLE / Hybrid). It runs inside dispatch_scope so a phantom-ON
                # permit still wraps whichever transport performs the send.
                with dispatch_scope:
                    transport_used = router.dispatch(param_id, spec, raw_midi)
                if transport_used is None:
                    # No control transport connected: accepted but NOT sent.
                    dispatch_status = DispatchStatus.ACCEPTED_OFFLINE
                else:
                    driver_dispatched = True
                    dispatch_status = (
                        DispatchStatus.BLE_WRITE_ACCEPTED
                        if transport_used == "ble"
                        else DispatchStatus.DRIVER_DISPATCHED
                    )
            elif self._midi_out.is_connected:
                with dispatch_scope:
                    if spec.get("message") == PROGRAM_CHANGE:
                        self._midi_out.send_program_change(spec["channel"], raw_midi)
                    else:
                        self._midi_out.send_cc(spec["channel"], spec["cc"], raw_midi)
                driver_dispatched = True
                transport_used = "usb_midi"
                dispatch_status = DispatchStatus.DRIVER_DISPATCHED
            else:
                # Offline: validated and accepted, but NOTHING was sent to the driver.
                dispatch_status = DispatchStatus.ACCEPTED_OFFLINE
        except Flow8CommandRejectedError as rej:
            # Transport policy refusal (e.g. parameter unsupported over BLE).
            # Logged as REJECTED — distinct from an actual transport failure.
            transport_rejected = str(rej)
            dispatch_success = False
            dispatch_status = DispatchStatus.REJECTED
            err_msg = transport_rejected
        except Exception as e:
            dispatch_success = False
            dispatch_status = DispatchStatus.DISPATCH_FAILED
            err_msg = str(e)

        elapsed_us = (time.perf_counter() - t0) * 1e6

        # 4. State Store Update -- only when the command was not a dispatch failure.
        state = None
        if dispatch_success:
            state = self._state_store.set_commanded_value(
                param_id=param_id,
                value=value,
                source=source,
                raw_midi_value=raw_midi
            )
            if state is None:
                state = self._get_state(param_id)
        else:
            # Do NOT commit commanded state for a value the mixer never received.
            self._state_store.set_dispatch_failed(param_id)
            state = self._get_state(param_id)

        entry = CommandLogEntry(
            timestamp=now,
            param_id=param_id,
            target_value=value,
            # Bytes actually submitted to the driver, else None.
            raw_midi_sent=raw_midi if driver_dispatched else None,
            source=source,
            success=dispatch_success,
            latency_us=round(elapsed_us, 2),
            dispatched_to_hardware=driver_dispatched,
            error_message=err_msg,
            command_accepted=transport_rejected is None,
            driver_dispatched=driver_dispatched,
            hardware_applied=None,  # never confirmed without an observation channel
            raw_midi_prepared=raw_midi,
            dispatch_status=dispatch_status,
            observed_value=state.observed_value if state else None,
            verification_level=state.verification_level if state else None,
            midi_channel=spec["channel"],
            midi_cc=spec["cc"],
            transport=transport_used,
        )

        self._append(entry)

        if transport_rejected is not None:
            raise Flow8CommandRejectedError(transport_rejected)
        if not dispatch_success:
            raise Flow8CommandError(
                f"Hardware dispatch failed for '{param_id}' "
                f"(status={dispatch_status}, prepared={raw_midi}): {err_msg}"
            )

        return entry
