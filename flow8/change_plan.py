"""Staged change plans (F7): propose, preview, confirm, commit.

A plan is plain data: a list of parameter changes, each with a reason and a
risk label. Building and previewing a plan sends nothing; only
`Flow8Service.commit_change_plan` dispatches, through the public setters and
therefore through the command boundary, as one ledger transaction. The known
mix state is captured before the first command so one undo puts everything
back.

Safety rules are not duplicated here: a change is accepted only when its
parameter id is on the verified command-boundary allowlist (which excludes
preamp gain), and only for parameters the ledger and scenes may touch.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Hashable, Mapping, Optional, Sequence

MAIN_CHANNEL = 8
BUSES = ("mon1", "mon2", "fx1", "fx2")
REVERSIBLE_PARAMETERS = (
    "fader", "pan", "mute",
    "eq_low", "eq_low_mid", "eq_hi_mid", "eq_hi",
    "low_cut", "compressor",
    "send_mon1", "send_mon2", "send_fx1", "send_fx2",
)
RISK_LEVELS = ("low", "medium", "high")
MAX_CHANGES = 64
MAX_REASON = 200
MAX_TITLE = 60

PARAMETER_LABELS = {
    "fader": "Fader",
    "pan": "Pan / balance",
    "mute": "Mute",
    "eq_low": "EQ Low",
    "eq_low_mid": "EQ Low-Mid",
    "eq_hi_mid": "EQ Hi-Mid",
    "eq_hi": "EQ High",
    "low_cut": "Low Cut",
    "compressor": "Compressor",
    "send_mon1": "Send Mon 1",
    "send_mon2": "Send Mon 2",
    "send_fx1": "Send FX 1",
    "send_fx2": "Send FX 2",
}


class ChangePlanError(ValueError):
    """A plan a caller asked for is malformed or would change a blocked parameter."""


class PreviewRequiredError(ValueError):
    """A commit arrived without a live preview, so nothing may be sent."""


@dataclass(frozen=True)
class PlannedChange:
    """One proposed parameter value, in raw MIDI units (0-127, or bool for mute)."""

    channel: Hashable
    parameter: str
    value: Any
    reason: str = ""
    risk: str = "low"

    @property
    def parameter_id(self) -> str:
        return parameter_id(self.channel, self.parameter)

    @property
    def label(self) -> str:
        return PARAMETER_LABELS.get(self.parameter, self.parameter)


@dataclass(frozen=True)
class ChangePlan:
    """An ordered set of proposed changes, reviewed before anything is sent."""

    title: str
    changes: tuple[PlannedChange, ...]
    plan_id: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class PreviewRow:
    """One plan line as it stands against the current known mix state."""

    channel: Hashable
    parameter: str
    parameter_id: str
    to_value: Any
    from_value: Optional[Any]
    from_provenance: str
    status: str  # "change" | "no_change"
    reason: str = ""
    risk: str = "low"

    @property
    def note(self) -> str:
        if self.from_value is None:
            return "Current value unknown; undo cannot restore it."
        if self.status == "no_change":
            return "Already at this value; nothing would be sent."
        return ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "parameter": self.parameter,
            "parameterId": self.parameter_id,
            "parameterLabel": PARAMETER_LABELS.get(self.parameter, self.parameter),
            "from": self.from_value,
            "fromProvenance": self.from_provenance,
            "to": self.to_value,
            "status": self.status,
            "note": self.note,
            "reason": self.reason,
            "risk": self.risk,
        }


@dataclass
class ChangePlanResult:
    """Outcome of one commit: what was sent, what failed, whether it was undone."""

    plan_id: str
    title: str
    applied: int = 0
    skipped: int = 0
    rolled_back: bool = False
    snapshot_label: Optional[str] = None
    undo_ready: bool = False
    error: Optional[str] = None
    failed: list[dict[str, Any]] = field(default_factory=list)
    #: True when the mix changed after the preview, so nothing was sent.
    stale: bool = False
    stale_rows: list[dict[str, Any]] = field(default_factory=list)
    fresh_rows: list[dict[str, Any]] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalise_channel(raw: Any) -> Hashable:
    """1-8 as int, or one of the bus ids. Raises ChangePlanError."""
    if isinstance(raw, bool):
        raise ChangePlanError(f"channel must be 1-8 or a bus id; got {raw!r}")
    if isinstance(raw, int) or (isinstance(raw, str) and raw.strip().isdigit()):
        value = int(raw)
        if not (1 <= value <= MAIN_CHANNEL):
            raise ChangePlanError(f"channel {value} is outside 1-{MAIN_CHANNEL}")
        return value
    key = str(raw).strip().lower()
    if key in BUSES:
        return key
    raise ChangePlanError(f"channel must be 1-8 or one of {BUSES}; got {raw!r}")


def parameter_id(channel: Hashable, parameter: str) -> str:
    """The command-boundary parameter id for a channel and parameter."""
    if channel in BUSES:
        return f"{channel}.{parameter}"
    if int(channel) == MAIN_CHANNEL:
        return "main.balance" if parameter == "pan" else f"main.{parameter}"
    return f"ch{int(channel)}.{parameter}"


def _allowed(a_parameter: str, channel: Hashable) -> bool:
    from flow8.command_boundary import Flow8CommandBoundary

    return parameter_id(channel, a_parameter) in Flow8CommandBoundary.ACTIVE_ALLOWLIST


def validate_change(change: PlannedChange) -> None:
    """Raise ChangePlanError unless this change targets a verified address and value."""
    if change.parameter not in REVERSIBLE_PARAMETERS:
        raise ChangePlanError(
            f"{change.parameter!r} is not a reversible mixer parameter"
            + (" (preamp gain and +48V are never part of a plan)" if change.parameter in ("gain", "phantom") else "")
        )
    if not _allowed(change.parameter, change.channel):
        raise ChangePlanError(
            f"{parameter_id(change.channel, change.parameter)} is not on the verified "
            f"command allowlist (unsupported on channel {change.channel})"
        )
    if change.risk not in RISK_LEVELS:
        raise ChangePlanError(f"risk must be one of {RISK_LEVELS}; got {change.risk!r}")
    if len(str(change.reason)) > MAX_REASON:
        raise ChangePlanError(f"reason is longer than {MAX_REASON} characters")
    if change.parameter == "mute":
        if not isinstance(change.value, bool):
            raise ChangePlanError("mute takes true or false")
        return
    if isinstance(change.value, bool) or not isinstance(change.value, int):
        raise ChangePlanError(f"{change.parameter} takes an integer 0-127; got {change.value!r}")
    if not (0 <= int(change.value) <= 127):
        raise ChangePlanError(f"{change.parameter} value {change.value} is outside 0-127")


def make_plan(title: Any, changes: Sequence[Mapping[str, Any]]) -> ChangePlan:
    """Build a validated plan from request data. Sends nothing."""
    title_text = str(title or "Change plan").strip()[:MAX_TITLE] or "Change plan"
    if not changes:
        raise ChangePlanError("a plan needs at least one change")
    if len(changes) > MAX_CHANGES:
        raise ChangePlanError(f"a plan may hold at most {MAX_CHANGES} changes")

    built: list[PlannedChange] = []
    seen: set[tuple[Hashable, str]] = set()
    for raw in changes:
        if not isinstance(raw, Mapping):
            raise ChangePlanError("each change must be an object")
        if "channel" not in raw or "parameter" not in raw or "value" not in raw:
            raise ChangePlanError("each change needs channel, parameter and value")
        change = PlannedChange(
            channel=normalise_channel(raw["channel"]),
            parameter=str(raw["parameter"]).strip().lower(),
            value=raw["value"],
            reason=str(raw.get("reason", "") or ""),
            risk=str(raw.get("risk", "low") or "low").lower(),
        )
        validate_change(change)
        key = (change.channel, change.parameter)
        if key in seen:
            raise ChangePlanError(
                f"channel {change.channel} {change.parameter} appears twice; "
                "combine it into one change"
            )
        seen.add(key)
        built.append(change)

    return ChangePlan(
        title=title_text,
        changes=tuple(built),
        plan_id=uuid.uuid4().hex[:12],
        created_at=_now(),
    )
