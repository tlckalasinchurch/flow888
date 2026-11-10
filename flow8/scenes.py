"""In-memory mixer scene snapshot manager."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional


@dataclass(frozen=True)
class SceneSnapshot:
    name: str
    parameters: dict[Any, dict[str, Any]]
    captured_at: datetime


class SceneManager:
    """Stores a bounded collection of named snapshots.

    Snapshots intentionally contain only fader, pan and mute values. Phantom
    power is neither captured nor restored, even if supplied by a caller.
    """

    ALLOWED_PARAMETERS = frozenset({"fader", "pan", "mute"})

    def __init__(self, max_snapshots: int = 8, state_provider: Optional[Callable[[], Mapping[Any, Mapping[str, Any]]]] = None,
                 state_loader: Optional[Callable[[Mapping[Any, Mapping[str, Any]]], Any]] = None):
        if max_snapshots < 1:
            raise ValueError("max_snapshots must be positive")
        self.max_snapshots = max_snapshots
        self._provider = state_provider
        self._loader = state_loader
        self._snapshots: dict[str, SceneSnapshot] = {}
        self._order: list[str] = []

    def save_snapshot(self, name: str, state: Optional[Mapping[Any, Mapping[str, Any]]] = None) -> SceneSnapshot:
        name = str(name).strip()
        if not name:
            raise ValueError("snapshot name cannot be empty")
        source = state if state is not None else (self._provider() if self._provider else {})
        parameters = {
            channel: {key: deepcopy(value) for key, value in values.items() if key in self.ALLOWED_PARAMETERS}
            for channel, values in source.items()
        }
        snapshot = SceneSnapshot(name, parameters, datetime.now(timezone.utc))
        if name not in self._snapshots and len(self._order) >= self.max_snapshots:
            oldest = self._order.pop(0)
            del self._snapshots[oldest]
        if name in self._order:
            self._order.remove(name)
        self._order.append(name)
        self._snapshots[name] = snapshot
        return snapshot

    def load_snapshot(self, name: str) -> SceneSnapshot:
        try:
            snapshot = self._snapshots[name]
        except KeyError as exc:
            raise KeyError(f"unknown snapshot: {name}") from exc
        if self._loader:
            self._loader(deepcopy(snapshot.parameters))
        return snapshot

    def delete_snapshot(self, name: str) -> None:
        self._snapshots.pop(name)
        self._order.remove(name)

    def list_snapshots(self) -> tuple[SceneSnapshot, ...]:
        return tuple(self._snapshots[name] for name in self._order)

    def names(self) -> tuple[str, ...]:
        return tuple(self._order)

    def get(self, name: str) -> SceneSnapshot:
        return self._snapshots[name]
