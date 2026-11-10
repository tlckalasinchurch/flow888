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
