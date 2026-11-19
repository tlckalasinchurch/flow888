"""Host-side storage for the two Show Modes (MC and BAND).

One JSON file on the host computer, so the PC and the iPad see the same modes.
A missing, damaged or hand-edited file never stops the hub: the affected mode
falls back to its template and `load_error` says why. The file is only
rewritten by `save`, never by loading.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from flow8.show_mode import ShowModeError, default_modes, unset_steps, validate_mode

SHOW_MODES_FORMAT = "flow8-show-modes-v1"
MODE_IDS = ("mc", "band")


def default_show_modes_path() -> Path:
    return Path.home() / ".flow8" / "show_modes.json"


class ShowModeStore:
    """Thread-safe store of the two modes, saved to a JSON file when a path is set."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else None
        self._lock = threading.Lock()
        self._modes: dict[str, dict[str, Any]] = default_modes()
        self.load_error: Optional[str] = None
        if self.path is not None and self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != SHOW_MODES_FORMAT:
                raise ValueError(f"not a FLOW 8 show-modes file (format {SHOW_MODES_FORMAT})")
            stored = data.get("modes")
            if not isinstance(stored, dict):
                raise ValueError("the file has no modes object")
        except Exception as exc:  # a damaged file must not stop the hub
            self.load_error = f"Show modes not loaded, using templates: {exc}"
            return
        problems = []
        for mode_id in MODE_IDS:
            if mode_id not in stored:
                continue
            try:
                # The slot decides id and name; the file cannot swap or rename modes.
                mode = validate_mode({**stored[mode_id], "id": mode_id, "name": self._modes[mode_id]["name"]})
                self._modes[mode_id] = mode
            except (ShowModeError, TypeError, ValueError) as exc:
                problems.append(f"{mode_id}: {exc}")
        if problems:
            self.load_error = "Show modes reset to template for " + "; ".join(problems)

    def summaries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._summary(self._modes[mode_id]) for mode_id in MODE_IDS]

    def get(self, mode_id: str) -> dict[str, Any]:
        with self._lock:
            if mode_id not in self._modes:
                raise KeyError(f"unknown show mode: {mode_id}")
            return deepcopy(self._modes[mode_id])

    def save(self, mode_id: str, steps: Any) -> dict[str, Any]:
        """Replace a mode's steps. The name stays; invalid steps raise ShowModeError."""
        with self._lock:
            if mode_id not in self._modes:
                raise KeyError(f"unknown show mode: {mode_id}")
            mode = validate_mode({"id": mode_id, "name": self._modes[mode_id]["name"], "steps": steps})
            previous = self._modes[mode_id]
            self._modes[mode_id] = mode
            try:
                self._write()
            except BaseException:
                self._modes[mode_id] = previous  # memory must not run ahead of the file
                raise
            return self._summary(mode)

    @staticmethod
    def _summary(mode: dict[str, Any]) -> dict[str, Any]:
        unset = unset_steps(mode)
        return {"id": mode["id"], "name": mode["name"], "steps": deepcopy(mode["steps"]),
                "unsetCount": len(unset), "ready": not unset}

    def _write(self) -> None:
        """Atomic write: a crash leaves the old file or the new one, never half."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"format": SHOW_MODES_FORMAT,
             "modes": {i: {"name": m["name"], "steps": m["steps"]} for i, m in self._modes.items()}},
            indent=2, ensure_ascii=False,
        )
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".show_modes.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
