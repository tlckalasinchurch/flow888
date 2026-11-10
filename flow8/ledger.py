"""Bounded, safety-aware command undo/redo ledger."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Callable, Deque, Hashable, Optional


PHANTOM_PARAMETER = "phantom_power"


@dataclass(frozen=True)
class CommandRecord:
    """One reversible mixer parameter transition.

    A record may represent a coalesced drag gesture: ``previous_value`` is
    the value before the gesture and ``new_value`` is its final value.
    """

    parameter_type: str
    channel_index: Hashable
    previous_value: Any
    new_value: Any
    timestamp: datetime
    transaction_id: Optional[str] = None

    @property
    def undoable(self) -> bool:
        return self.parameter_type != PHANTOM_PARAMETER


class CommandLedger:
    """A bounded undo/redo ledger with optional gesture batching."""

    def __init__(self, capacity: int = 50, executor: Optional[Callable[..., Any]] = None):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._undo: Deque[CommandRecord] = deque(maxlen=capacity)
        self._redo: Deque[CommandRecord] = deque(maxlen=capacity)
        self._executor = executor
        self._batch: Optional[dict[tuple[str, Hashable], CommandRecord]] = None
        #: Records replayed by the most recent undo/redo (a whole transaction).
        self.last_applied: tuple[CommandRecord, ...] = ()

    @property
    def history(self) -> tuple[CommandRecord, ...]:
        return tuple(self._undo)

    @property
    def redo_history(self) -> tuple[CommandRecord, ...]:
        return tuple(self._redo)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def push(self, record: CommandRecord) -> bool:
        """Add a record, ignoring phantom transitions by design."""
        if not record.undoable or record.previous_value == record.new_value:
            return False
        if self._batch is not None:
            key = (record.parameter_type, record.channel_index)
            existing = self._batch.get(key)
            if existing is None:
                self._batch[key] = record
            else:
                self._batch[key] = replace(existing, new_value=record.new_value)
            return True
        self._undo.append(record)
        self._redo.clear()
        return True

    def begin_batch(self) -> None:
        if self._batch is not None:
            raise RuntimeError("a ledger batch is already active")
        self._batch = {}

    def end_batch(self) -> int:
        """Commit a gesture as one transaction and return records committed.

        A gesture that ends where it began changes nothing and records nothing.
        Several records from one batch share a ``transaction_id`` and undo/redo
        together as one step.
        """
        if self._batch is None:
            return 0
        pending = [r for r in self._batch.values() if r.previous_value != r.new_value]
        self._batch = None
        if len(pending) > 1:
            transaction_id = uuid4().hex
            pending = [replace(r, transaction_id=transaction_id) for r in pending]
        for record in pending:
            self._undo.append(record)
        if pending:
            self._redo.clear()
        return len(pending)

    def cancel_batch(self) -> None:
        self._batch = None

    def _apply(self, record: CommandRecord, value: Any) -> None:
        if self._executor is not None:
            self._executor(record.parameter_type, record.channel_index, value)

    @staticmethod
    def _tail_group(stack: Deque[CommandRecord]) -> list[CommandRecord]:
        """The newest record plus the records sharing its transaction, newest first."""
        if not stack:
            return []
        top = stack[-1]
        if top.transaction_id is None:
            return [top]
        group = []
        for record in reversed(stack):
            if record.transaction_id != top.transaction_id:
                break
            group.append(record)
        return group

    def undo(self) -> Optional[CommandRecord]:
        """Revert the newest step (a whole transaction when it has one).

        The ledger changes only after every replay succeeded: if the executor
        raises, nothing is popped, so the step is still available to retry.
        """
        if self._batch is not None:
            self.end_batch()
        group = self._tail_group(self._undo)
        self.last_applied = ()
        if not group:
            return None
        for record in group:
            self._apply(record, record.previous_value)
        for record in group:
            self._undo.pop()
            self._redo.append(record)
        self.last_applied = tuple(group)
        return group[0]

    def redo(self) -> Optional[CommandRecord]:
        group = self._tail_group(self._redo)
        self.last_applied = ()
        if not group:
            return None
        for record in group:
            self._apply(record, record.new_value)
        for record in group:
            self._redo.pop()
            self._undo.append(record)
        self.last_applied = tuple(group)
        return group[-1]

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._batch = None

    @staticmethod
    def make_record(parameter_type: str, channel_index: Hashable, previous_value: Any, new_value: Any) -> CommandRecord:
        return CommandRecord(
            parameter_type=parameter_type,
            channel_index=channel_index,
            previous_value=previous_value,
            new_value=new_value,
            timestamp=datetime.now(timezone.utc),
        )
