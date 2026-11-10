"""Flow8 service boundary for mixer state and MIDI command dispatch."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Hashable, Mapping, Optional

from .ledger import CommandLedger
from .scenes import SceneManager

INPUT_CHANNELS = tuple(range(7))
MAIN_CHANNELS = ("main_l", "main_r")
ALL_CHANNELS = INPUT_CHANNELS + MAIN_CHANNELS


class Flow8Service:
    """Hardware-independent mixer service used by UI and tests."""

    def __init__(self) -> None:
        self.state: dict[Hashable, dict[str, Any]] = {
            channel: {"fader": 0, "mute": False, **({"pan": 0} if isinstance(channel, int) else {})}
            for channel in ALL_CHANNELS
        }
        self.phantom_power: dict[int, bool] = {channel: False for channel in INPUT_CHANNELS}
        self.midi_commands: list[tuple[str, Hashable, Any]] = []
        self.status_message = "READY"
        self.provenance: dict[tuple[Hashable, str], str] = {}
        self._replaying = False
        self.ledger = CommandLedger(capacity=50, executor=self._apply_from_ledger)
        self.scenes = SceneManager(max_snapshots=8, state_provider=self.snapshot_state, state_loader=self._recall_state)

    def _validate(self, channel: Hashable, parameter: str) -> None:
        if channel not in self.state:
            raise KeyError(f"unknown channel: {channel}")
        if parameter not in self.state[channel] and parameter != "phantom_power":
            raise KeyError(f"unsupported parameter {parameter} for channel {channel}")
        if parameter == "phantom_power" and not isinstance(channel, int):
            raise ValueError("phantom power exists only on input channels")

    def set_parameter(self, channel: Hashable, parameter: str, value: Any, *, record: bool = True, source: str = "user") -> None:
        self._validate(channel, parameter)
        if parameter == "phantom_power":
            # Deliberately no ledger record. A production adapter should place
            # its explicit safety gate before calling this method.
            self.phantom_power[channel] = bool(value)
            self._dispatch(parameter, channel, bool(value))
            self.status_message = f"PHANTOM CH {channel + 1}: {'ON' if value else 'OFF'}"
            return
        old = self.state[channel][parameter]
        if old == value:
            return
        self.state[channel][parameter] = value
        self._dispatch(parameter, channel, value)
        self.provenance[(channel, parameter)] = "COMMANDED"
        if record and not self._replaying:
            self.ledger.push(self.ledger.make_record(parameter, channel, old, value))
        self.status_message = f"{source.upper()}: CH {channel} {parameter.upper()} = {value}"

    def _dispatch(self, parameter: str, channel: Hashable, value: Any) -> None:
        self.midi_commands.append((parameter, channel, value))

    def _apply_from_ledger(self, parameter: str, channel: Hashable, value: Any) -> None:
        self._replaying = True
        try:
            self.set_parameter(channel, parameter, value, record=False, source="undo/redo")
        finally:
            self._replaying = False

    def undo(self) -> Optional[Any]:
        record = self.ledger.undo()
        self.status_message = "NOTHING TO UNDO" if record is None else f"UNDO: CH {record.channel_index} {record.parameter_type.upper()} RESTORED TO {record.previous_value}"
        return record

    def redo(self) -> Optional[Any]:
        record = self.ledger.redo()
        self.status_message = "NOTHING TO REDO" if record is None else f"REDO: CH {record.channel_index} {record.parameter_type.upper()} RESTORED TO {record.new_value}"
        return record

    def begin_drag(self) -> None:
        self.ledger.begin_batch()

    def end_drag(self) -> int:
        return self.ledger.end_batch()

    def snapshot_state(self) -> dict[Hashable, dict[str, Any]]:
        return deepcopy(self.state)

    def _recall_state(self, parameters: Mapping[Hashable, Mapping[str, Any]]) -> None:
        for channel, values in parameters.items():
            for parameter in ("fader", "pan", "mute"):
                if parameter in values and parameter in self.state[channel]:
                    self.set_parameter(channel, parameter, values[parameter], record=False, source="scene")
        self.status_message = "SCENE RECALLED (PHANTOM POWER UNCHANGED)"

    def save_scene(self, name: str):
        return self.scenes.save_snapshot(name)

    def recall_scene(self, name: str):
        return self.scenes.load_snapshot(name)
