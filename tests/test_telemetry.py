"""Inbound telemetry: decode, provenance, no echo, thread safety."""

from __future__ import annotations

import threading
import unittest

from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance, SyncStatus
from flow8.telemetry import (
    decode,
    inbound_parameter_map,
    is_forbidden_program_reset,
    observed_value,
)


def cc(channel: int, controller: int, value: int) -> dict:
    return {"status": 0xB0, "channel": channel, "command": 0xB0,
            "data1": controller, "data2": value}


class MappingTests(unittest.TestCase):
    def test_allowlist_is_the_map(self):
        mapping = inbound_parameter_map()
        self.assertEqual(mapping[(1, 7)]["paramId"], "ch1.fader")
        self.assertEqual(mapping[(1, 1)]["paramId"], "ch1.eq_low")
        self.assertEqual(mapping[(1, 9)]["paramId"], "ch1.low_cut")
        self.assertEqual(mapping[(1, 11)]["paramId"], "ch1.compressor")
        self.assertEqual(mapping[(1, 14)]["paramId"], "ch1.send_mon1")
        self.assertEqual(mapping[(8, 7)]["paramId"], "main.fader")
        self.assertEqual(mapping[(8, 10)]["paramId"], "main.balance")
        self.assertEqual(mapping[(9, 7)]["paramId"], "mon1.fader")
        # MIDI channel 6 is the 7/8 stereo strip, never input 6.
        self.assertEqual(mapping[(6, 7)]["paramId"], "ch6.fader")
        self.assertTrue(mapping[(1, 12)]["boolean"])       # +48V is a switch

    def test_decode_cc_and_program_change(self):
        event = decode(cc(1, 7, 84))
        self.assertEqual((event.kind, event.param_id, event.value), ("cc", "ch1.fader", 84))
        self.assertTrue(event.mapped)

        pc = decode({"status": 0xC0, "channel": 16, "command": 0xC0, "data1": 16, "data2": 0})
        self.assertEqual(pc.kind, "program_change")
        self.assertTrue(is_forbidden_program_reset(pc))
        self.assertFalse(is_forbidden_program_reset(
            decode({"status": 0xC0, "channel": 16, "command": 0xC0, "data1": 1, "data2": 0})))

    def test_unmapped_cc_is_reported_but_not_mapped(self):
        event = decode(cc(1, 99, 5))
        self.assertFalse(event.mapped)
        self.assertEqual(event.controller, 99)

    def test_observed_value_is_boolean_only_for_switches(self):
        self.assertTrue(observed_value(decode(cc(2, 5, 127))))
        self.assertEqual(observed_value(decode(cc(2, 10, 30))), 30)


class InboundServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)
        self.seen = []
        self.service.add_listener(lambda pid, value: self.seen.append((pid, value)))

    def state(self, param_id):
        return self.service.state_store.get_parameter(param_id)

    def test_cc_becomes_observed_without_sending_anything(self):
        self.service._on_midi_in_event(cc(1, 7, 84))
        state = self.state("ch1.fader")
        self.assertEqual(state.provenance, ParameterProvenance.OBSERVED)
        self.assertEqual(state.observed_raw_midi, 84)
        self.assertEqual(self.seen, [("ch1.fader", 84)])
        self.assertEqual(self.service.command_boundary.command_log, [])
        status = self.service.telemetry_status()
        self.assertEqual((status["ccReceived"], status["mapped"]), (1, 1))
        self.assertEqual(status["lastParamId"], "ch1.fader")

    def test_eq_low_cut_comp_and_sends_are_observed(self):
        self.service._on_midi_in_event(cc(1, 1, 51))
        self.service._on_midi_in_event(cc(1, 9, 20))
        self.service._on_midi_in_event(cc(1, 11, 40))
        self.service._on_midi_in_event(cc(1, 16, 76))
        self.assertEqual(self.state("ch1.eq_low").observed_raw_midi, 51)
        self.assertEqual(self.state("ch1.low_cut").observed_raw_midi, 20)
        self.assertEqual(self.state("ch1.compressor").observed_raw_midi, 40)
        self.assertEqual(self.state("ch1.send_fx1").observed_raw_midi, 76)
        for param_id in ("ch1.eq_low", "ch1.low_cut", "ch1.compressor", "ch1.send_fx1"):
            self.assertEqual(self.state(param_id).provenance, ParameterProvenance.OBSERVED)

    def test_mute_and_phantom_are_booleans(self):
        self.service._on_midi_in_event(cc(2, 5, 127))
        self.service._on_midi_in_event(cc(2, 12, 0))
        self.assertIs(self.state("ch2.mute").observed_value, True)
        self.assertIs(self.state("ch2.phantom").observed_value, False)

    def test_echo_never_commands_anything_back(self):
        self.service.set_fader(1, 80)
        log_before = len(self.service.command_boundary.command_log)
        self.service._on_midi_in_event(cc(1, 7, 80))
        state = self.state("ch1.fader")
        self.assertEqual(state.provenance, ParameterProvenance.OBSERVED)
        self.assertEqual(state.sync_status, SyncStatus.SYNCED)
        self.assertEqual(len(self.service.command_boundary.command_log), log_before,
                         "inbound telemetry must never produce an outbound command")

    def test_unmapped_and_program_change_are_counted_not_applied(self):
        self.service._on_midi_in_event(cc(1, 99, 10))
        self.service._on_midi_in_event({"status": 0xC0, "channel": 16, "command": 0xC0,
                                        "data1": 16, "data2": 0})
        status = self.service.telemetry_status()
        self.assertEqual(status["ignored"], 1)
        self.assertEqual(status["programChanges"], 1)
        self.assertEqual(status["forbiddenResets"], 1)
        self.assertEqual(self.seen, [])

    def test_concurrent_events_are_thread_safe(self):
        def worker(channel, base):
            for i in range(50):
                self.service._on_midi_in_event(cc(channel, 7, (base + i) % 128))

        threads = [threading.Thread(target=worker, args=(ch, ch * 10)) for ch in (1, 2, 3, 4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        status = self.service.telemetry_status()
        self.assertEqual(status["ccReceived"], 200)
        self.assertEqual(status["mapped"], 200)
        for ch in (1, 2, 3, 4):
            self.assertEqual(self.state(f"ch{ch}.fader").provenance, ParameterProvenance.OBSERVED)


if __name__ == "__main__":
    unittest.main()
