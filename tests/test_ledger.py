from flow8.ledger import CommandLedger, PHANTOM_PARAMETER
from flow8.service import Flow8Service


def test_ledger_bounding():
    ledger = CommandLedger(capacity=50)
    for index in range(60):
        ledger.push(ledger.make_record("fader", 0, index, index + 1))
    assert len(ledger.history) == 50
    assert ledger.history[0].previous_value == 10
    assert ledger.history[-1].new_value == 60


def test_undo_and_redo_execute_through_service_boundary():
    service = Flow8Service()
    service.set_parameter(0, "fader", 85)
    assert service.state[0]["fader"] == 85
    service.undo()
    assert service.state[0]["fader"] == 0
    assert service.midi_commands[-1] == ("fader", 0, 0)
    assert service.provenance[(0, "fader")] == "COMMANDED"
    service.redo()
    assert service.state[0]["fader"] == 85
    assert service.midi_commands[-1] == ("fader", 0, 85)


def test_drag_updates_coalesce_to_one_transaction():
    service = Flow8Service()
    service.begin_drag()
    for value in (10, 20, 30, 40, 50):
        service.set_parameter(1, "fader", value)
    assert len(service.ledger.history) == 0
    assert service.end_drag() == 1
    assert len(service.ledger.history) == 1
    record = service.ledger.history[0]
    assert (record.previous_value, record.new_value) == (0, 50)
    service.undo()
    assert service.state[1]["fader"] == 0


def test_phantom_power_is_excluded_and_undo_does_not_touch_it():
    service = Flow8Service()
    service.set_parameter(0, "phantom_power", True)
    assert service.phantom_power[0] is True
    assert len(service.ledger.history) == 0
    service.set_parameter(0, "fader", 72)
    service.undo()
    assert service.state[0]["fader"] == 0
    assert service.phantom_power[0] is True
    assert all(record.parameter_type != PHANTOM_PARAMETER for record in service.ledger.history)
