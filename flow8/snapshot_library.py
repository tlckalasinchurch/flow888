"""Named snapshot library for the LAN remote (per vocalist, per venue).

Each entry holds known mix values in the scene format of Flow8Service
(channel 1-8 or bus id -> {parameter: value}). Entries are kept in one JSON
file on the host computer. Import validates every value: an entry can never
carry preamp gain, +48V, or a value outside the MIDI range.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from flow8.service import MAIN_CHANNEL, REVERSIBLE_PARAMETERS, SCENE_BUSES, recall_scope_of

LIBRARY_FORMAT = "flow8-snapshot-library-v1"
MAX_ENTRIES = 500
MAX_NAME = 40


def default_library_path() -> Path:
    return Path.home() / ".flow8" / "snapshot_library.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _channel_key(key: Any) -> Any:
    """JSON key -> scene channel: 1-8 as int, or a bus id. Raises ValueError."""
    text = str(key).strip().lower()
    if text.isdigit() and 1 <= int(text) <= MAIN_CHANNEL:
        return int(text)
    if text in SCENE_BUSES:
        return text
    raise ValueError(f"unknown channel {key!r}")


def _allowed_parameters(channel: Any) -> tuple[str, ...]:
    if isinstance(channel, str):
        return ("fader",)
    if channel == MAIN_CHANNEL:
        return ("fader", "pan")
    return REVERSIBLE_PARAMETERS


def normalise_parameters(raw: Mapping[Any, Any]) -> dict[Any, dict[str, Any]]:
    """Validate stored mix values. Unknown or out-of-range values raise ValueError."""
    if not isinstance(raw, Mapping):
        raise ValueError("parameters must be an object")
    out: dict[Any, dict[str, Any]] = {}
    for key, values in raw.items():
        channel = _channel_key(key)
        if not isinstance(values, Mapping):
            raise ValueError(f"channel {key!r}: values must be an object")
        allowed = _allowed_parameters(channel)
        clean: dict[str, Any] = {}
        for parameter, value in values.items():
            if parameter not in allowed:
                raise ValueError(f"channel {key!r}: parameter {parameter!r} is not allowed")
            if parameter == "mute":
                if not isinstance(value, bool):
                    raise ValueError(f"channel {key!r}: mute must be true or false")
                clean[parameter] = value
            else:
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
                    raise ValueError(f"channel {key!r}: {parameter} must be an integer 0-127")
                clean[parameter] = value
        if clean:
            out[channel] = clean
    return out


def scope_counts(parameters: Mapping[Any, Mapping[str, Any]]) -> dict[str, int]:
    counts = {"CH": 0, "FX": 0, "MAIN": 0, "MON": 0}
    for channel, values in parameters.items():
        for parameter in values:
            counts[recall_scope_of(channel, parameter)] += 1
    return counts


class SnapshotLibrary:
    """Thread-safe store of named snapshots, saved to a JSON file when a path is set."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else None
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self.load_error: Optional[str] = None
        if self.path is not None and self.path.exists():
            try:
                self._add_entries(json.loads(self.path.read_text(encoding="utf-8")), keep_ids=True)
            except Exception as exc:  # a damaged file must not stop the hub
                self.load_error = f"Snapshot library not loaded: {exc}"

    # -- Read ---------------------------------------------------------------

    def summaries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": e["id"], "name": e["name"],
                    "createdAt": e["createdAt"], "updatedAt": e["updatedAt"],
                    "scopes": scope_counts(e["parameters"]),
                }
                for e in self._entries.values()
            ]

    def get(self, entry_id: str) -> dict[str, Any]:
        with self._lock:
            if entry_id not in self._entries:
                raise KeyError(f"unknown snapshot: {entry_id}")
            return json.loads(json.dumps(self._serialise(self._entries[entry_id])))

    def parameters(self, entry_id: str) -> dict[Any, dict[str, Any]]:
        with self._lock:
            if entry_id not in self._entries:
                raise KeyError(f"unknown snapshot: {entry_id}")
            return {ch: dict(v) for ch, v in self._entries[entry_id]["parameters"].items()}

    def export(self) -> dict[str, Any]:
        with self._lock:
            return {
                "format": LIBRARY_FORMAT,
                "exportedAt": _now(),
                "snapshots": [self._serialise(e) for e in self._entries.values()],
            }

    # -- Write --------------------------------------------------------------

    def save(self, name: str, parameters: Mapping[Any, Mapping[str, Any]],
             entry_id: Optional[str] = None) -> dict[str, Any]:
        """Add a snapshot, or overwrite the values of entry_id."""
        name = self._clean_name(name)
        params = normalise_parameters(parameters)
        if not params:
            raise ValueError("No known mix values to save; nothing was stored.")
        with self._lock:
            if entry_id is not None:
                if entry_id not in self._entries:
                    raise KeyError(f"unknown snapshot: {entry_id}")
                entry = self._entries[entry_id]
                entry.update(name=name, parameters=params, updatedAt=_now())
            else:
                if len(self._entries) >= MAX_ENTRIES:
                    raise ValueError(f"The library is full ({MAX_ENTRIES} snapshots).")
                stamp = _now()
                entry = {"id": uuid.uuid4().hex[:12], "name": name, "createdAt": stamp,
                         "updatedAt": stamp, "parameters": params}
                self._entries[entry["id"]] = entry
            self._write()
            return {"id": entry["id"], "name": entry["name"]}

    def rename(self, entry_id: str, name: str) -> None:
        name = self._clean_name(name)
        with self._lock:
            if entry_id not in self._entries:
                raise KeyError(f"unknown snapshot: {entry_id}")
            self._entries[entry_id].update(name=name, updatedAt=_now())
            self._write()

    def delete(self, entry_id: str) -> None:
        with self._lock:
            if self._entries.pop(entry_id, None) is None:
                raise KeyError(f"unknown snapshot: {entry_id}")
            self._write()

    def import_data(self, data: Any) -> dict[str, Any]:
        """Add the valid snapshots of an exported library. Imported ids are always new."""
        with self._lock:
            result = self._add_entries(data, keep_ids=False)
            if result["added"]:
                self._write()
            return result

    # -- Internals ----------------------------------------------------------

    @staticmethod
    def _clean_name(name: Any) -> str:
        text = " ".join(str(name or "").split())[:MAX_NAME]
        if not text:
            raise ValueError("Enter a snapshot name.")
        return text

    @staticmethod
    def _serialise(entry: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": entry["id"], "name": entry["name"],
            "createdAt": entry["createdAt"], "updatedAt": entry["updatedAt"],
            "parameters": {str(ch): dict(v) for ch, v in entry["parameters"].items()},
        }

    def _add_entries(self, data: Any, keep_ids: bool) -> dict[str, Any]:
        if not isinstance(data, Mapping) or data.get("format") != LIBRARY_FORMAT:
            raise ValueError(f"Not a FLOW 8 snapshot library (format {LIBRARY_FORMAT}).")
        items = data.get("snapshots")
        if not isinstance(items, list):
            raise ValueError("The file has no snapshot list.")
        added, errors = 0, []
        for index, item in enumerate(items):
            try:
                if len(self._entries) >= MAX_ENTRIES:
                    raise ValueError("library full")
                if not isinstance(item, Mapping):
                    raise ValueError("entry is not an object")
                params = normalise_parameters(item.get("parameters", {}))
                if not params:
                    raise ValueError("no values")
                stamp = _now()
                entry_id = str(item.get("id", "")) if keep_ids else ""
                if not entry_id or entry_id in self._entries or len(entry_id) > 32:
                    entry_id = uuid.uuid4().hex[:12]
                self._entries[entry_id] = {
                    "id": entry_id,
                    "name": self._clean_name(item.get("name")),
                    "createdAt": str(item.get("createdAt") or stamp)[:32],
                    "updatedAt": str(item.get("updatedAt") or stamp)[:32],
                    "parameters": params,
                }
                added += 1
            except ValueError as exc:
                errors.append(f"#{index + 1}: {exc}")
        return {"added": added, "skipped": len(errors), "errors": errors[:10]}

    def _write(self) -> None:
        """Atomic write: a crash leaves the old file or the new one, never half."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"format": LIBRARY_FORMAT, "snapshots": [self._serialise(e) for e in self._entries.values()]},
            indent=2, ensure_ascii=False,
        )
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".snapshot_library.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
