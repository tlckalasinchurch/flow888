"""Link watchdog, auto-reconnect and USB meter loss detection."""

from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from flow8.audio_meter import Flow8AudioMeter
from flow8.service import Flow8Service
from flow8.state_model import ParameterProvenance


class FakeMidiOut:
    def __init__(self):
        self.is_connected = False
        self.present = True
        self.opened = 0
        self.sent = []

    def open(self, device_id=None):
        self.opened += 1
        self.is_connected = True

    def close(self):
        self.is_connected = False

    def find_device_id(self):
        return 0 if self.present else None

    def send_cc(self, channel, cc, value):
        self.sent.append((channel, cc, value))
        if not self.is_connected:
            raise RuntimeError("port closed")

    @property
    def device_info(self):
        return (0 if self.present else None, "FLOW 8 MIDI OUT")


class FakeMidiIn:
    def __init__(self):
        self.is_connected = False
        self.is_listening = False
        self.present = True
        self.opened = 0
        self.callbacks = []

    def open(self, device_id=None):
        self.opened += 1
        self.is_connected = True

    def close(self):
        self.is_connected = False
        self.is_listening = False

    def start(self):
        self.is_listening = True

    def stop(self):
        self.is_listening = False

    def register_callback(self, callback):
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def unregister_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def find_device_id(self):
        return 0 if self.present else None

    @property
    def device_info(self):
        return (0 if self.present else None, "FLOW 8 MIDI IN")


def wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.out = FakeMidiOut()
        self.inp = FakeMidiIn()
        patchers = [
            mock.patch("flow8.service.Flow8MidiOut", return_value=self.out),
            mock.patch("flow8.service.Flow8MidiIn", return_value=self.inp),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.service = Flow8Service(
            auto_connect=False, watchdog_interval=0.03, reconnect_interval=0.03,
        )
        self.events = []
        self.service.add_listener(lambda pid, value: self.events.append(pid))
        self.addCleanup(self.service.stop_watchdog)

    def test_connect_starts_listening(self):
        self.assertTrue(self.service.connect())
        self.assertTrue(self.service.is_connected)
        self.assertTrue(self.inp.is_listening)
        self.assertEqual(self.inp.callbacks, [self.service._on_midi_in_event])
        self.assertFalse(self.service.watchdog_running)

    def test_unplug_is_detected_and_state_becomes_unsynced(self):
        self.service.connect()
        self.service.set_fader(1, 80)
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").provenance,
                         ParameterProvenance.COMMANDED)
        self.service.start_watchdog(auto_reconnect=True)
        self.assertTrue(self.service.watchdog_running)

        self.inp.present = False   # the mixer is pulled out
        self.assertTrue(wait_until(lambda: not self.service.is_connected))
        self.assertEqual(self.service.connection_error, "FLOW 8 USB disconnected")
        self.assertIn("__reconcile__", self.events)
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").provenance,
                         ParameterProvenance.UNSYNCED)
        self.assertFalse(self.out.is_connected)

    def test_reconnect_happens_without_restarting_anything(self):
        self.service.connect()
        self.service.start_watchdog(auto_reconnect=True)
        self.inp.present = False
        self.out.present = False
        self.assertTrue(wait_until(lambda: not self.service.is_connected))

        self.inp.present = True
        self.out.present = True
        self.assertTrue(wait_until(lambda: self.service.is_connected), "watchdog did not reconnect")
        self.assertGreaterEqual(self.inp.opened, 2)
        self.assertTrue(self.inp.is_listening)
        self.assertIsNone(self.service.connection_error)

    def test_watchdog_never_sends_midi(self):
        self.service.connect()
        self.service.start_watchdog(auto_reconnect=True)
        self.inp.present = False
        self.assertTrue(wait_until(lambda: not self.service.is_connected))
        self.inp.present = True
        self.assertTrue(wait_until(lambda: self.service.is_connected))
        self.assertEqual(self.out.sent, [])

    def test_manual_disconnect_stays_disconnected(self):
        self.service.connect()
        self.service.start_watchdog(auto_reconnect=True)
        self.service.disconnect()
        time.sleep(0.25)
        self.assertFalse(self.service.is_connected)
        self.assertFalse(self.service.auto_reconnect)

    def test_start_watchdog_is_idempotent(self):
        self.service.start_watchdog()
        first = self.service._watchdog_thread
        self.service.start_watchdog()
        self.assertIs(self.service._watchdog_thread, first)


class FakeStream:
    def __init__(self):
        self.active = True

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.active = False


class FakeSoundDevice:
    """An endpoint that stays 'active' but never delivers a frame."""

    def __init__(self):
        self.stream = FakeStream()

    def query_devices(self):
        return [{"name": "FLOW 8 Multi In 1-10", "hostapi": 0,
                 "max_input_channels": 10, "default_samplerate": 48000.0}]

    def query_hostapis(self):
        return [{"name": "Windows WASAPI"}]

    def InputStream(self, **kwargs):
        return self.stream


class MeterLossTests(unittest.TestCase):
    def test_silent_stream_is_reported_as_a_lost_device(self):
        statuses = []
        meter = Flow8AudioMeter(
            lambda levels: None, statuses.append,
            backend=FakeSoundDevice(), publish_hz=50.0, frame_timeout_s=0.1,
        )
        self.addCleanup(meter.stop)
        self.assertTrue(meter.start())
        self.assertTrue(wait_until(lambda: meter.status["state"] == "error", timeout=3.0))
        self.assertIn("no frames", meter.status["detail"])
        self.assertFalse(meter.is_running)
        self.assertTrue(any("no frames" in s.get("detail", "") for s in statuses))

    def test_meter_stop_reports_stopped(self):
        meter = Flow8AudioMeter(lambda levels: None, None, backend=FakeSoundDevice())
        self.assertTrue(meter.start())
        meter.stop()
        self.assertEqual(meter.status["state"], "stopped")
        self.assertFalse(meter.is_running)


if __name__ == "__main__":
    unittest.main()
