from flow8.ledger import CommandLedger, PHANTOM_PARAMETER


def test_ledger_is_bounded_and_batches_drag_updates():
    ledger = CommandLedger(capacity=50)
    for index in range(60):
        ledger.push(ledger.make_record("fader", 1, index, index + 1))
    assert len(ledger.history) == 50
    ledger.begin_batch()
    for value in (10, 20, 30):
        ledger.push(ledger.make_record("fader", 1, value - 10, value))
    assert ledger.end_batch() == 1
    assert ledger.history[-1].previous_value == 0
    assert ledger.history[-1].new_value == 30


def test_phantom_transitions_are_never_undoable():
    ledger = CommandLedger()
    assert not ledger.push(ledger.make_record(PHANTOM_PARAMETER, 1, False, True))
    assert ledger.undo() is None


def test_failed_replay_keeps_the_step_so_it_can_be_retried():
    calls = []

    def executor(parameter, channel, value):
        calls.append(value)
        if len(calls) == 1:
            raise RuntimeError("driver down")

    ledger = CommandLedger(executor=executor)
    ledger.push(ledger.make_record("fader", 1, 10, 20))
    try:
        ledger.undo()
    except RuntimeError:
        pass
    assert ledger.can_undo and not ledger.can_redo
    assert ledger.undo().new_value == 20
    assert calls == [10, 10]


def test_gesture_that_returns_to_start_records_nothing():
    ledger = CommandLedger()
    ledger.begin_batch()
    ledger.push(ledger.make_record("fader", 1, 10, 50))
    ledger.push(ledger.make_record("fader", 1, 50, 10))
    assert ledger.end_batch() == 0
    assert not ledger.can_undo


def test_batched_group_undoes_and_redoes_as_one_step_in_order():
    applied = []
    ledger = CommandLedger(executor=lambda p, c, v: applied.append((p, c, v)))
    ledger.begin_batch()
    ledger.push(ledger.make_record("fader", 1, 1, 2))
    ledger.push(ledger.make_record("pan", 1, 3, 4))
    assert ledger.end_batch() == 2
    ledger.undo()
    assert not ledger.can_undo and len(ledger.redo_history) == 2
    ledger.redo()
    assert applied == [
        ("pan", 1, 3), ("fader", 1, 1),   # undo: newest first
        ("fader", 1, 2), ("pan", 1, 4),   # redo: original order
    ]
    assert len(ledger.history) == 2 and not ledger.can_redo
