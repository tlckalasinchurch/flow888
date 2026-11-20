"""Inbound MIDI telemetry: decode, map to parameters, and count.

The FLOW 8 reports some controls over USB MIDI when they move on the hardware.
This module is the one place that turns a raw MIDI message into a parameter the
application already trusts, using the **verified command allowlist** as the map:
if a (channel, CC) pair cannot be sent, it is not accepted as telemetry either.

Nothing here sends a command. Inbound telemetry is observation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from flow8.command_boundary import Flow8CommandBoundary

CC_STATUS = 0xB0
PROGRAM_CHANGE_STATUS = 0xC0

#: The one forbidden Program Change: PC 16 on MIDI channel 16 resets the mixer.
FORBIDDEN_PROGRAM_RESET = (16, 16)


@dataclass(frozen=True)
class InboundEvent:
    """One decoded inbound message, already normalised to a parameter when known."""

    kind: str                 # "cc" | "program_change" | "other"
    channel: int              # 1-based
    controller: Optional[int]
    value: Optional[int]
    param_id: Optional[str]
    parameter_type: Optional[str]
    is_boolean: bool

    @property
    def mapped(self) -> bool:
        return self.param_id is not None


def inbound_parameter_map() -> dict[tuple[int, int], dict[str, Any]]:
    """(MIDI channel, CC) -> parameter, taken from the verified allowlist."""
    mapping: dict[tuple[int, int], dict[str, Any]] = {}
    for param_id, spec in Flow8CommandBoundary.ACTIVE_ALLOWLIST.items():
        if spec.get("cc") is None:
            continue  # FX preset select is a Program Change; inbound Program Changes are counted, not applied
        mapping[(int(spec["channel"]), int(spec["cc"]))] = {
            "paramId": param_id,
            "type": str(spec["type"]),
            "boolean": bool(spec.get("boolean", False)),
        }
    return mapping


def decode(event: Mapping[str, Any], mapping: Optional[Mapping[tuple[int, int], Mapping[str, Any]]] = None) -> InboundEvent:
    """Decode one event dict from Flow8MidiIn. Never raises on a malformed message."""
    lookup = inbound_parameter_map() if mapping is None else mapping
    status = int(event.get("status", 0) or 0)
    channel = int(event.get("channel", (status & 0x0F) + 1) or 1)
    command = status & 0xF0

    if command == PROGRAM_CHANGE_STATUS:
        return InboundEvent("program_change", channel, None, int(event.get("data1", 0) or 0),
                            None, None, False)
    if command != CC_STATUS:
        return InboundEvent("other", channel, None, None, None, None, False)

    controller = int(event.get("data1", 0) or 0)
    value = int(event.get("data2", 0) or 0)
    entry = lookup.get((channel, controller))
    if entry is None:
        return InboundEvent("cc", channel, controller, value, None, None, False)
    return InboundEvent(
        "cc", channel, controller, value,
        str(entry["paramId"]), str(entry["type"]), bool(entry["boolean"]),
    )


def observed_value(event: InboundEvent) -> Optional[Any]:
    """The value stored for an observed parameter: bool for switches, else raw int."""
    if not event.mapped or event.value is None:
        return None
    return bool(event.value) if event.is_boolean else int(event.value)


def is_forbidden_program_reset(event: InboundEvent) -> bool:
    """True only for PC 16 on channel 16 (the mixer's reset message)."""
    return event.kind == "program_change" and (event.channel, event.value) == FORBIDDEN_PROGRAM_RESET


class TelemetryStats:
    """Thread-safe counters for inbound telemetry (observation only)."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.cc_received = 0
            self.mapped = 0
            self.ignored = 0
            self.program_changes = 0
            self.forbidden_resets = 0
            self.last_param_id: Optional[str] = None
            self.last_channel: Optional[int] = None
            self.last_controller: Optional[int] = None
            self.last_value: Optional[int] = None
            self.last_at: Optional[str] = None
            self.first_at: Optional[str] = None

    def record(self, event: InboundEvent) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            if event.kind == "program_change":
                self.program_changes += 1
                if is_forbidden_program_reset(event):
                    self.forbidden_resets += 1
            elif event.kind != "cc":
                return
            else:
                self.cc_received += 1
                if event.mapped:
                    self.mapped += 1
                else:
                    self.ignored += 1
            if self.first_at is None:
                self.first_at = stamp
            self.last_at = stamp
            self.last_param_id = event.param_id
            self.last_channel = event.channel
            self.last_controller = event.controller
            self.last_value = event.value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ccReceived": self.cc_received,
                "mapped": self.mapped,
                "ignored": self.ignored,
                "programChanges": self.program_changes,
                "forbiddenResets": self.forbidden_resets,
                "firstAt": self.first_at,
                "lastAt": self.last_at,
                "lastParamId": self.last_param_id,
                "lastChannel": self.last_channel,
                "lastController": self.last_controller,
                "lastValue": self.last_value,
                "mappedParameters": len(inbound_parameter_map()),
            }
