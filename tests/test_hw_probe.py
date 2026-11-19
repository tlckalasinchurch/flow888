"""Safe hardware probe: summary math, injected ports, CLI exit codes."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from tools import hw_probe


def cc(channel, controller, value):
    return {"status": 0xB0, "channel": channel, "command": 0xB0,
            "data1": controller, "data2": value}


def pc(channel, program):
    return {"status": 0xC0, "channel": channel, "command": 0xC0,
            "data1": program, "data2": 0}


class SummaryTests(unittest.TestCase):
    def test_counts_mapped_unmapped_and_program_changes(self):
        events = [
            cc(1, 7, 80), cc(1, 7, 81), cc(1, 1, 51),
            cc(1, 99, 3),                      # not on the allowlist
            pc(16, 1), pc(16, 16),             # the second one is the reset
        ]
        summary = hw_probe.summarize_events(events)
        self.assertEqual(summary["totalMessages"], 6)
        self.assertEqual(summary["mappedCount"], 3)
        self.assertEqual(summary["unmappedCc"], 1)
        self.assertEqual(summary["programChanges"], 2)
        self.assertEqual(summary["forbiddenProgramResets"], 1)
        self.assertTrue(summary["telemetryObserved"])
        fader = next(p for p in summary["mappedParameters"] if p["paramId"] == "ch1.fader")
        self.assertEqual((fader["count"], fader["lastValue"]), (2, 81))

    def test_empty_listen_is_honest(self):
        summary = hw_probe.summarize_events([])
        self.assertFalse(summary["telemetryObserved"])
        self.assertEqual(summary["mappedParameters"], [])


class FakePort:
    def __init__(self, events):
        self.events = events
        self.callback = None
        self.opened = False
        self.started = False
        self.closed = False

    def register_callback(self, callback):
        self.callback = callback

    def open(self, device_id=None):
        self.opened = True

    def start(self):
        self.started = True
        for event in self.events:
            self.callback(event)

    def close(self):
        self.closed = True


class ProbeMidiTests(unittest.TestCase):
    def test_listens_on_the_flow8_port_and_summarizes(self):
        port = FakePort([cc(2, 7, 90)])
        report = hw_probe.probe_midi(
            0, devices=[{"index": 4, "name": "FLOW 8 MIDI IN"}], port_factory=lambda: port,
        )
        self.assertTrue(report["available"])
        self.assertTrue(port.opened and port.started and port.closed)
        self.assertEqual(report["summary"]["mappedCount"], 1)
        self.assertEqual(report["summary"]["mappedParameters"][0]["paramId"], "ch2.fader")

    def test_missing_flow8_port_opens_nothing(self):
        def factory():
            raise AssertionError("no port may be opened")

        report = hw_probe.probe_midi(0, devices=[{"index": 0, "name": "Other MIDI"}],
                                     port_factory=factory)
        self.assertFalse(report["available"])
        self.assertEqual(report.get("summary"), None)


class FakeMeter:
    def __init__(self, started=True, publish=None):
        self._started = started
        self._publish = publish
        self.status = {"state": "running" if started else "no_device",
                       "detail": "test", "device": "Multi In 1-10", "mode": "recording"}

    def start(self):
        if self._started and self._publish:
            self._publish({"ch1": {"peak": -20.0, "rms": -30.0}})
            self._publish({"ch1": {"peak": -18.0, "rms": -28.0}})
        return self._started

    def stop(self):
        self.status = {"state": "stopped", "detail": "Meters are off.", "device": None, "mode": None}


class ProbeAudioTests(unittest.TestCase):
    def test_frames_and_levels_are_reported(self):
        report = hw_probe.probe_audio(0, meter_factory=lambda publish, status: FakeMeter(True, publish))
        self.assertTrue(report["metering"])
        self.assertEqual(report["framesReceived"], 2)
        self.assertEqual(report["levels"]["ch1"]["peak"], -18.0)

    def test_failed_start_keeps_the_reason_before_stop(self):
        report = hw_probe.probe_audio(0, meter_factory=lambda publish, status: FakeMeter(False))
        self.assertFalse(report["started"])
        self.assertEqual(report["status"]["state"], "no_device")


class CliTests(unittest.TestCase):
    def _report(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = hw_probe.main(list(args))
        return code, out.getvalue()

    def test_no_flow8_device_exits_with_two(self):
        with mock.patch.object(hw_probe.Flow8MidiOut, "list_devices",
                               return_value=[{"index": 0, "name": "GS Wavetable"}]):
            with mock.patch.object(hw_probe.Flow8MidiIn, "list_devices", return_value=[]):
                code, out = self._report("--json", "--no-midi", "--no-audio")
        self.assertEqual(code, 2)
        report = json.loads(out)
        self.assertFalse(report["ready"]["midiIn"])
        self.assertTrue(report["safe"])
        self.assertFalse(report["sentMidi"])

    def test_json_report_is_machine_readable(self):
        with mock.patch.object(hw_probe.Flow8MidiOut, "list_devices", return_value=[]):
            with mock.patch.object(hw_probe.Flow8MidiIn, "list_devices",
                                   return_value=[{"index": 1, "name": "FLOW 8 MIDI IN"}]):
                code, out = self._report("--safe", "--json", "--no-midi", "--no-audio")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["midiInDevices"][0]["name"], "FLOW 8 MIDI IN")
        self.assertTrue(report["midi"]["available"])
        self.assertTrue(report["midi"]["skipped"])

    def test_probe_can_never_open_or_send_on_midi_out(self):
        with mock.patch.object(hw_probe.Flow8MidiOut, "list_devices", return_value=[]):
            with mock.patch.object(hw_probe.Flow8MidiIn, "list_devices", return_value=[]):
                with mock.patch.object(hw_probe.Flow8MidiOut, "open",
                                       side_effect=AssertionError("MIDI OUT opened")) as opened, \
                     mock.patch.object(hw_probe.Flow8MidiOut, "send_cc",
                                       side_effect=AssertionError("MIDI sent")) as sent:
                    code, _ = self._report("--json", "--no-midi", "--no-audio")
        self.assertEqual(code, 2)
        opened.assert_not_called()
        sent.assert_not_called()

    def test_build_report_defaults_to_safe(self):
        args = argparse.Namespace(no_midi=True, no_audio=True, seconds=0.0)
        with mock.patch.object(hw_probe.Flow8MidiOut, "list_devices", return_value=[]):
            with mock.patch.object(hw_probe.Flow8MidiIn, "list_devices", return_value=[]):
                report = hw_probe.build_report(args)
        self.assertTrue(report["safe"])
        self.assertFalse(report["sentMidi"])
        self.assertFalse(report["ready"]["telemetry"])


if __name__ == "__main__":
    unittest.main()
