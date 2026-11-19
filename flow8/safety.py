"""Shared FLOW 8 safety policy (S1.2). Standard library only: no tkinter, no flow8.ui.

One place decides what the application may transmit. The command boundary, the low-level
port and the ledger all read this module, so the rules hold on every call path and not
merely behind a UI control.

Rules (docs/product/FLOW8_SAFETY_POLICY.md):
  SR-01  only Control Change messages may leave the application
  SR-02  Program Change 16 on channel 16 (mixer reset) is forbidden
  SR-04  channel 16 (global/snapshot) is not available
  SR-05  preamp gain is blocked absolutely (no runtime, environment or development override)
  SR-06  +48V ON needs a grant created by the user-confirmation flow; OFF never does
  SR-07  only allowlisted (channel, CC) pairs may be sent

Changing a rule is a reviewed code change to this file; nothing in the program can alter it.
"""

from __future__ import annotations

import contextlib
import contextvars
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Optional

__all__ = [
    "BLOCKED_PARAMETER_TYPES",
    "NEVER_LEDGERED",
    "SafetyPolicyError",
    "PhantomPowerConfirmationToken",
    "PhantomPowerSafetyGate",
    "authorize_command",
    "validate_outbound",
]

# Parameter types that no layer may send. Read-only mapping: item assignment raises TypeError.
BLOCKED_PARAMETER_TYPES = MappingProxyType({"gain": "SR-05"})

# Ledger parameter types that are never recorded, so undo/redo can never replay them.
NEVER_LEDGERED = frozenset({"phantom_power", "phantom", "gain"})


class SafetyPolicyError(Exception):
    """A message or command was refused by the safety policy. `rule` names the rule."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"[{rule}] {message}")
        self.rule = rule


# ---------------------------------------------------------------------------
# +48V phantom power: token, gate, grant and permit
# ---------------------------------------------------------------------------

class PhantomPowerConfirmationToken:
    """Opaque, single-use capability token for a phantom confirmation request.

    Instances carry no public state that can be forged into validity: a token is
    accepted by ``PhantomPowerSafetyGate`` only if its object identity was
    registered by an active dialog request. Manually constructing one yields an
    unregistered (and therefore rejected) token.
    """

    def __init__(self, _nonce: Optional[object] = None) -> None:
        # The nonce is never inspected for validity; identity of the instance
        # plus the gate registry is what authorises dispatch.
        self._nonce = _nonce if _nonce is not None else object()


@dataclass
class _PhantomPendingRequest:
    channel_index: int
    consumed: bool = False
    active: bool = True
    issued_at: float = 0.0
    clock: Callable[[], float] = field(default=time.monotonic)


@dataclass
class _Grant:
    channel_index: int
    consumed: bool = False


# A grant lives only for the duration of one synchronous confirm_and_dispatch call in one thread
# (context variables are per thread). The command boundary consumes it once and then opens a permit
# for the single send_cc call.
_grant_var: contextvars.ContextVar = contextvars.ContextVar("flow8_phantom_on_grant", default=None)
_permit_var: contextvars.ContextVar = contextvars.ContextVar("flow8_phantom_on_permit", default=None)


@contextlib.contextmanager
def _grant_phantom_on(channel_index: int):
    grant = _Grant(channel_index)
    token = _grant_var.set(grant)
    try:
        yield grant
    finally:
        grant.consumed = True
        _grant_var.reset(token)


def _consume_phantom_on_grant(channel_index: int) -> None:
    grant = _grant_var.get()
    if grant is None or grant.consumed or grant.channel_index != channel_index:
        raise SafetyPolicyError(
            "SR-06",
            f"+48V ON for channel {channel_index} requires user confirmation; no valid authorization is active.",
        )
    grant.consumed = True


@contextlib.contextmanager
def _phantom_on_permit(channel_index: int):
    token = _permit_var.set(channel_index)
    try:
        yield
    finally:
        _permit_var.reset(token)


def _permit_active(channel_index: int) -> bool:
    return _permit_var.get() == channel_index


class PhantomPowerSafetyGate:
    """Headless logic gate enforcing +48V phantom power safety rules."""

    ALLOWED_CHANNELS = (1, 2)
    WARNING_TEXT = (
        "WARNING: +48V Phantom Power should ONLY be applied to microphones "
        "requiring phantom power (e.g. condenser mics).\n\n"
        "Energizing +48V into ribbon microphones, unbalanced dynamic mics, "
        "or line-level equipment can cause permanent physical or transducer damage."
    )

    # Registry of active/inactive pending confirmation requests, keyed by
    # token identity (id(token)). Only tokens present here with active=True and
    # consumed=False can authorise a dispatch.
    _pending: dict = {}

    @classmethod
    def validate_channel(cls, channel_index: int) -> bool:
        """Validate whether the channel physically supports +48V phantom power."""
        if channel_index not in cls.ALLOWED_CHANNELS:
            raise ValueError(
                f"+48V Phantom Power is physically restricted to Channels 1 and 2 only. "
                f"Channel {channel_index} has no hardware phantom relay."
            )
        return True

    @classmethod
    def issue_token(
        cls,
        channel_index: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> PhantomPowerConfirmationToken:
        """Mint a single-use, channel-bound confirmation token.

        The token is registered in the gate's internal pending-request registry.
        Unregistered (forged) tokens are rejected by ``confirm_and_dispatch``.
        """
        cls.validate_channel(channel_index)
        token = PhantomPowerConfirmationToken()
        cls._pending[id(token)] = _PhantomPendingRequest(
            channel_index=channel_index,
            issued_at=clock(),
            clock=clock,
        )
        return token

    @classmethod
    def revoke_token(cls, token: Any) -> None:
        """Invalidate a pending token (cancel / escape / close / supersede)."""
        record = cls._pending.get(id(token))
        if record is not None:
            record.active = False

    @classmethod
    def confirm_and_dispatch(
        cls,
        service: Any,
        channel_index: int,
        confirmation_token: Any,
        clock: Optional[Callable[[], float]] = None,
        ttl: Optional[float] = None,
    ) -> bool:
        """Dispatch +48V through the service iff *confirmation_token* is a valid,
        active, unconsumed, channel-bound token issued by this gate.

        Returns True on successful dispatch, False on any rejection. Never calls
        the service for a rejected/invalid token. The service call runs inside a
        one-shot grant that the command boundary consumes.
        """
        # Reject anything that is not a gate-issued token instance.
        if not isinstance(confirmation_token, PhantomPowerConfirmationToken):
            return False

        record = cls._pending.get(id(confirmation_token))
        if record is None:
            return False
        if not record.active or record.consumed:
            return False
        if record.channel_index != channel_index:
            return False

        # Channel must be a physically valid phantom channel.
        try:
            cls.validate_channel(channel_index)
        except ValueError:
            record.active = False
            return False

        # Optional TTL check using the issuing clock (or an override).
        effective_clock = clock if clock is not None else record.clock
        if ttl is not None:
            if effective_clock() - record.issued_at > ttl:
                record.active = False
                return False

        # Consume before dispatch: a second call with the same token is rejected.
        record.consumed = True
        record.active = False

        with _grant_phantom_on(channel_index):
            service.set_phantom(channel_index, True)
        return True

    @classmethod
    def disable_and_dispatch(cls, service: Any, channel_index: int) -> bool:
        """Request +48V OFF through the service after validating the channel.

        OFF needs no authorization and no warning dialog: it de-energises the relay.
        """
        cls.validate_channel(channel_index)
        service.set_phantom(channel_index, False)
        return True


# ---------------------------------------------------------------------------
# Command and message policy
# ---------------------------------------------------------------------------

_tables_cache: dict = {}


def _tables() -> dict:
    """(channel, CC) tables derived from the boundary allowlist (single source of truth).

    Imported lazily because the boundary imports this module.
    """
    if not _tables_cache:
        from flow8.command_boundary import Flow8CommandBoundary

        allowed, blocked, phantom = set(), set(), set()
        for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
            pair = (spec["channel"], spec["cc"])
            if spec["type"] in BLOCKED_PARAMETER_TYPES:
                blocked.add(pair)
            else:
                allowed.add(pair)
            if param_id.endswith(".phantom"):
                phantom.add(pair)
        _tables_cache.update(allowed=frozenset(allowed), blocked=frozenset(blocked), phantom=frozenset(phantom))
    return _tables_cache


def _is_on(value: Any) -> bool:
    """True for the only values the boundary accepts as +48V ON (True or integer 1).

    Any other value is either OFF (False, 0) or is rejected by the boundary's value validation
    before anything can be sent, so it cannot energise the relay.
    """
    return value is True or (isinstance(value, int) and not isinstance(value, bool) and value == 1)


def authorize_command(param_id: str, value: Any):
    """Policy check for a boundary command. Returns the context manager to dispatch under.

    Raises SafetyPolicyError for blocked parameters (gain) and for +48V ON without a grant.
    +48V OFF and every other parameter pass.
    """
    prefix, _, name = param_id.rpartition(".")
    rule = BLOCKED_PARAMETER_TYPES.get(name)
    if rule is not None:
        raise SafetyPolicyError(rule, f"{param_id}: preamp gain is blocked by safety policy and cannot be sent.")
    if name == "phantom" and _is_on(value):
        channel = int(prefix[2:]) if prefix.startswith("ch") and prefix[2:].isdigit() else -1
        _consume_phantom_on_grant(channel)
        return _phantom_on_permit(channel)
    return contextlib.nullcontext()


def validate_outbound(status: int, data1: int, data2: int) -> None:
    """Refuse every message that is not an allowlisted, non-blocked Control Change.

    Used by the low-level port and by the standalone tools, so the same rules apply to all senders.
    """
    for name, byte in (("status", status), ("data1", data1), ("data2", data2)):
        if not isinstance(byte, int) or isinstance(byte, bool):
            raise SafetyPolicyError("SR-01", f"{name} must be an integer")
    if not 0x80 <= status <= 0xFF:
        raise SafetyPolicyError("SR-01", f"status byte {status!r} is not a MIDI status byte")
    if status & 0xF0 != 0xB0:
        if status == 0xCF and data1 == 16:
            raise SafetyPolicyError("SR-02", "mixer reset (Program Change 16 on channel 16) is forbidden")
        raise SafetyPolicyError(
            "SR-01", "only Control Change messages may be sent; Program Change, Note, SysEx and system messages are disabled")
    if not (0 <= data1 <= 127 and 0 <= data2 <= 127):
        raise SafetyPolicyError("SR-01", "data bytes must be 0..127")
    channel = (status & 0x0F) + 1
    if channel == 16:
        raise SafetyPolicyError("SR-04", "channel 16 (global controls and snapshots) is not available")
    pair = (channel, data1)
    tables = _tables()
    if pair in tables["blocked"]:
        raise SafetyPolicyError("SR-05", f"channel {channel} CC {data1}: preamp gain is blocked by safety policy")
    if pair not in tables["allowed"]:
        raise SafetyPolicyError("SR-07", f"channel {channel} CC {data1} is not an allowlisted FLOW 8 parameter")
    if pair in tables["phantom"] and data2 > 0 and not _permit_active(channel):
        raise SafetyPolicyError("SR-06", f"+48V ON on channel {channel} needs user-confirmation authorization")


class AnalogGainSafetyGate:
    """Staged editing safety controller for Analog Preamp Gain (gated by SR-05)."""

    ALLOWED_CHANNELS = (1, 2, 3, 4)
    MIN_DB = -20.0
    MAX_DB = 60.0

    def __init__(self, channel_index: int, initial_gain_db: float = 0.0) -> None:
        if channel_index not in self.ALLOWED_CHANNELS:
            raise ValueError(
                f"Analog preamp gain is restricted to Channels 1-4. Channel {channel_index} has no analog preamp."
            )
        self.channel_index = channel_index
        self.current_gain_db = float(initial_gain_db)
        self.preview_gain_db = float(initial_gain_db)
        self.is_staged = False

    @staticmethod
    def is_verified_mapping_available() -> bool:
        return "gain" not in BLOCKED_PARAMETER_TYPES

    def stage_preview(self, proposed_db: float) -> float:
        clamped = max(self.MIN_DB, min(self.MAX_DB, float(proposed_db)))
        self.preview_gain_db = clamped
        self.is_staged = (self.preview_gain_db != self.current_gain_db)
        return self.preview_gain_db

    def cancel_staged(self) -> float:
        self.preview_gain_db = self.current_gain_db
        self.is_staged = False
        return self.current_gain_db

    def commit_gain(self, service: Any, confirmed: bool = False) -> bool:
        if not self.is_verified_mapping_available():
            raise RuntimeError(
                "Hardware gain dispatch is gated: Preamp Gain dB curve is an UNVERIFIED APPROXIMATION. "
                "Physical hardware calibration evidence is required before automatic dispatch."
            )
        if not confirmed:
            raise RuntimeError("Gain commit requires explicit confirmation; nothing sent.")
        raise NotImplementedError("No analog-gain dispatch path exists; nothing sent.")
