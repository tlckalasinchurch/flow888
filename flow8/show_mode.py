"""Show Mode: an ordered macro list that writes only the parameters it names.

A mode is plain data: steps of (parameter, channels, value). `compile_mode`
turns a ready mode into change-plan changes in a fixed safe order, and the
caller sends them through the normal change-plan path, so the command
allowlist, rollback and one-step undo all apply. Gain and +48V are not in
SHOW_MODE_PARAMETERS and can never be listed.
"""

from __future__ import annotations

from typing import Any, Mapping

SHOW_MODE_PARAMETERS = ("mute", "fader", "send_fx1", "send_fx2", "send_mon1", "send_mon2")
INPUT_CHANNELS = range(1, 8)  # channel 8 (main) is never part of a mode
BUS_IDS = ("fx1", "fx2", "mon1", "mon2")
MAX_STEPS = 32
MAX_CHANNELS_PER_STEP = 16
MAX_NAME = 40


class ShowModeError(ValueError):
    """A mode is malformed, or it cannot run yet."""


def _channel(raw: Any, parameter: str) -> Any:
    if isinstance(raw, bool):
        raise ShowModeError(f"channel must be 1-7 or a bus id; got {raw!r}")
    if isinstance(raw, int) or (isinstance(raw, str) and raw.strip().isascii() and raw.strip().isdigit()):
        value = int(raw)
        if value in INPUT_CHANNELS:
            return value
        raise ShowModeError(f"channel {value} is not allowed in a show mode (inputs 1-7 only)")
    key = str(raw).strip().lower()
    if key in BUS_IDS:
        if parameter != "fader":
            raise ShowModeError(f"{parameter} cannot target bus {key!r}; only fader can")
        return key
    raise ShowModeError(f"channel must be 1-7 or a bus id; got {raw!r}")


def _value(parameter: str, raw: Any) -> Any:
    if raw is None:
        return None  # NOT SET: the mode cannot run until this is filled in
    if parameter == "mute":
        if not isinstance(raw, bool):
            raise ShowModeError("mute takes true (mute) or false (unmute)")
        return raw
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 127:
        raise ShowModeError(f"{parameter} takes an integer 0-127; got {raw!r}")
    return raw


def validate_mode(mode: Mapping[str, Any]) -> dict:
    """Return a normalised copy of the mode, or raise ShowModeError."""
    if not isinstance(mode, Mapping):
        raise ShowModeError("a mode must be an object")
    name = " ".join(str(mode.get("name") or "").split())[:MAX_NAME]
    if not name:
        raise ShowModeError("a mode needs a name")
    raw_steps = mode.get("steps")
    if not isinstance(raw_steps, list):
        raise ShowModeError("steps must be a list")
    if len(raw_steps) > MAX_STEPS:
        raise ShowModeError(f"a mode may hold at most {MAX_STEPS} steps")

    steps, seen = [], set()
    for raw in raw_steps:
        if not isinstance(raw, Mapping):
            raise ShowModeError("each step must be an object")
        parameter = str(raw.get("parameter", "")).strip().lower()
        if parameter not in SHOW_MODE_PARAMETERS:
            raise ShowModeError(
                f"{parameter!r} is not allowed in a show mode"
                + (" (preamp gain and +48V are never part of a mode)"
                   if parameter in ("gain", "phantom") else "")
            )
        channels_raw = raw.get("channels")
        if not isinstance(channels_raw, list) or not channels_raw:
            raise ShowModeError("each step needs at least one channel")
        if len(channels_raw) > MAX_CHANNELS_PER_STEP:
            raise ShowModeError(f"a step may name at most {MAX_CHANNELS_PER_STEP} channels")
        channels = [_channel(c, parameter) for c in channels_raw]
        for channel in channels:
            if (channel, parameter) in seen:
                raise ShowModeError(f"channel {channel} {parameter} appears twice; combine it into one step")
            seen.add((channel, parameter))
        steps.append({"parameter": parameter, "channels": channels,
                      "value": _value(parameter, raw.get("value"))})
    return {"id": str(mode.get("id", "")), "name": name, "steps": steps}


def unset_steps(mode: Mapping[str, Any]) -> list[int]:
    """Indexes of steps whose value is NOT SET."""
    return [i for i, step in enumerate(mode.get("steps", [])) if step.get("value") is None]


def _is_cut_down(parameter: str, value: Any) -> bool:
    return value is True if parameter == "mute" else value == 0


def compile_mode(mode: Mapping[str, Any]) -> list[dict]:
    """Ordered change-plan changes: mutes and zeros first, then everything else.

    The order does not depend on current values (they may be unknown), so a
    mode always silences before it raises. Within a phase, list order holds.
    """
    clean = validate_mode(mode)
    unset = unset_steps(clean)
    if unset:
        raise ShowModeError(f"{len(unset)} step(s) are NOT SET; set them before running")
    reason = f"Show Mode: {clean['name']}"
    cut, rest = [], []
    for step in clean["steps"]:
        target = cut if _is_cut_down(step["parameter"], step["value"]) else rest
        for channel in step["channels"]:
            target.append({"channel": channel, "parameter": step["parameter"],
                           "value": step["value"], "reason": reason})
    return cut + rest


def default_modes() -> dict[str, dict]:
    """MC and BAND templates. Only values the owner stated are filled in; the rest are NOT SET.

    Channel defaults (my call, editable): vocal and MC mic Ch 1, instruments Ch 2-6,
    background music Ch 7, FX 1.
    """
    return {
        "mc": {"id": "mc", "name": "MC", "steps": [
            {"parameter": "send_fx1", "channels": [1], "value": 0},
            {"parameter": "mute", "channels": [2, 3, 4, 5, 6], "value": True},
            {"parameter": "mute", "channels": [1], "value": False},
            {"parameter": "fader", "channels": [1], "value": None},
            {"parameter": "fader", "channels": [7], "value": None},
        ]},
        "band": {"id": "band", "name": "BAND", "steps": [
            {"parameter": "fader", "channels": [7], "value": None},
            {"parameter": "mute", "channels": [2, 3, 4, 5, 6], "value": False},
            {"parameter": "send_fx1", "channels": [1], "value": None},
        ]},
    }
