"""Phase 2 §7 instrumentation: read-only counters for the live-performance hardware soak.

None of these change what is sent to the mixer. They only measure.
"""

from __future__ import annotations

import logging
import queue
import time
import unittest
from unittest import mock

from flow8 import lan_hub, web_console
from flow8.audio_meter import Flow8AudioMeter
from flow8.lan_hub import Flow8LanHub
from flow8.midi_constants import MIM_DATA
from flow8.midi_in import Flow8MidiIn
from flow8.service import Flow8Service
from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import fake_open_port
from tests.test_audio_meter import FLOW8, FakeBackend, block, sine


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class MeterStatsTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend(FLOW8)
        self.published = []
        self.meter = Flow8AudioMeter(self.published.append, backend=self.backend, publish_hz=100)
        self.addCleanup(self.meter.stop)

    def test_stats_before_start_are_zero(self):
        stats = self.meter.stats()
        self.assertEqual(stats["frames"], 0)
        self.assertEqual(stats["overflows"], 0)
        self.assertEqual(stats["publishCount"], 0)

    def test_callbacks_overflows_and_publish_interval_are_measured(self):
        self.assertTrue(self.meter.start())
        stream = self.backend.streams[0]
        data = block({0: sine(0.5)})
        stream.feed(data)
        stream.feed(data)
        stream.callback(data, data.shape[0], None, "input overflow")  # PortAudio status flag set
        self.assertTrue(wait_for(lambda: self.meter.stats()["publishCount"] >= 3))
        stats = self.meter.stats()
        self.assertEqual(stats["frames"], 3)
        self.assertEqual(stats["overflows"], 1)
        self.assertGreater(stats["callbackMaxMs"], 0.0)
        self.assertGreater(stats["callbackMeanMs"], 0.0)
        self.assertLessEqual(stats["callbackMeanMs"], stats["callbackMaxMs"])
        # 100 Hz publish: intervals near 10 ms, never zero.
        self.assertGreater(stats["publishIntervalMeanMs"], 5.0)
        self.assertGreaterEqual(stats["publishIntervalMaxMs"], stats["publishIntervalMeanMs"])

    def test_restart_resets_stats(self):
        self.assertTrue(self.meter.start())
        self.backend.streams[0].feed(block({0: sine(0.5)}))
        self.meter.stop()
        self.assertTrue(self.meter.start())
        self.assertEqual(self.meter.stats()["frames"], 0)


class HubMeterStatsTests(unittest.TestCase):
    def setUp(self):
        self.hub = Flow8LanHub(Flow8Service(auto_connect=False), host="127.0.0.1", port=0)

    def test_no_source_reports_none(self):
        self.assertIsNone(self.hub.status_snapshot()["meterStats"])

    def test_source_is_reported(self):
        self.hub.meter_stats_source = lambda: {"frames": 7}
        self.assertEqual(self.hub.status_snapshot()["meterStats"], {"frames": 7})

    def test_launcher_wires_the_meter_stats_into_the_hub(self):
        from tests.test_web_console import FakeHub, FakeMeter, FakeService, args

        class StatsMeter(FakeMeter):
            def stats(self):
                return {"frames": 1}

        hubs = []

        def hub_factory(*a, **kw):
            hubs.append(FakeHub(*a, **kw))
            return hubs[-1]

        with mock.patch("builtins.print"):
            web_console.run(args(), service_factory=FakeService, hub_factory=hub_factory,
                            meter_factory=StatsMeter, sleep=lambda _s: None, loop_limit=1,
                            reuse_existing=False)
        self.assertEqual(hubs[0].meter_stats_source(), {"frames": 1})


class SseStatsTests(unittest.TestCase):
    def setUp(self):
        self.hub = Flow8LanHub(Flow8Service(auto_connect=False), host="127.0.0.1", port=0)

    def add(self, client_id, maxsize):
        q: queue.Queue[bytes] = queue.Queue(maxsize=maxsize)
        with self.hub._sse_lock:
            self.hub._subscribers.append((q, client_id))
        return q

    def test_queue_depths_drops_and_removals(self):
        busy = self.add("busy", 1)
        idle = self.add("idle", 10)
        self.hub.publish_meters({"ch1": {"peak": -6, "rms": -18}})  # fills busy, 1 in idle
        self.hub._last_meter_sent = 0.0
        self.hub.publish_meters({"ch1": {"peak": -6, "rms": -18}})  # busy full: meter dropped
        self.assertEqual(idle.qsize(), 2)
        sse = self.hub.status_snapshot()["sse"]
        self.assertEqual(sse["clients"], 2)
        self.assertEqual(sse["maxQueueDepth"], 2)
        self.assertEqual(sse["droppedMeterFrames"], 1)
        self.assertEqual(sse["removedClients"], 0)
        self.assertEqual(busy.qsize(), 1)

        self.hub.broadcast({"type": "state"})  # busy full on a state event: removed
        sse = self.hub.status_snapshot()["sse"]
        self.assertEqual(sse["clients"], 1)
        self.assertEqual(sse["removedClients"], 1)


class LatencyPercentileTests(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        p = lan_hub.latency_percentiles([float(v) for v in range(100, 0, -1)])
        self.assertEqual(p, {"n": 100, "p50": 50.0, "p95": 95.0, "p99": 99.0, "max": 100.0})

    def test_empty(self):
        self.assertEqual(lan_hub.latency_percentiles([]),
                         {"n": 0, "p50": None, "p95": None, "p99": None, "max": None})


class DispatchLatencyTests(NoHardwareMixin, unittest.TestCase):
    def test_status_reports_latency_and_log_length(self):
        service = Flow8Service(auto_connect=False)
        fake_open_port(service.midi_out)
        for value in range(10):
            service.set_fader(1, value)
        with self.assertRaises(Exception):
            service.command_boundary.execute_command("not.a.param", 1)  # rejected: not timed
        dispatch = Flow8LanHub(service, host="127.0.0.1", port=0)._dispatch_snapshot()
        self.assertEqual(dispatch["logLength"], 11)
        self.assertEqual(dispatch["latencyUs"]["n"], 10)
        self.assertGreater(dispatch["latencyUs"]["max"], 0.0)


class InboundCallbackStatsTests(NoHardwareMixin, unittest.TestCase):
    def test_callback_time_is_measured_even_when_a_listener_fails(self):
        midi_in = Flow8MidiIn()
        midi_in.register_callback(lambda _e: time.sleep(0.002))
        midi_in.register_callback(lambda _e: 1 / 0)
        for _ in range(3):
            midi_in._internal_c_callback(None, MIM_DATA, 0, 0x7F01B0, 0)
        midi_in._internal_c_callback(None, 0x3C1, 0, 0, 0)  # not MIM_DATA: not counted
        stats = midi_in.callback_stats()
        self.assertEqual(stats["events"], 3)
        self.assertGreaterEqual(stats["callbackMaxUs"], 1500.0)
        self.assertLessEqual(stats["callbackMeanUs"], stats["callbackMaxUs"])

    def test_service_telemetry_includes_inbound_callback_stats(self):
        service = Flow8Service(auto_connect=False)
        self.assertEqual(service.telemetry_status()["inboundCallback"]["events"], 0)


class HealthCheckTimingTests(NoHardwareMixin, unittest.TestCase):
    def test_lock_held_enumeration_is_timed(self):
        service = Flow8Service(auto_connect=False)
        service._connected = True

        def slow_find():
            time.sleep(0.02)
            return 1

        with mock.patch.object(service.midi_out, "find_device_id", side_effect=slow_find), \
                mock.patch.object(service.midi_in, "find_device_id", return_value=1):
            self.assertTrue(service.check_connection_health())
        health = service.telemetry_status()["healthCheck"]
        self.assertEqual(health["count"], 1)
        self.assertGreaterEqual(health["lastMs"], 15.0)
        self.assertGreaterEqual(health["maxMs"], health["lastMs"])

    def test_no_check_yet(self):
        health = Flow8Service(auto_connect=False).telemetry_status()["healthCheck"]
        self.assertEqual(health, {"count": 0, "lastMs": None, "maxMs": None})


class LoggingSetupTests(unittest.TestCase):
    def test_main_configures_timestamped_info_logging(self):
        with mock.patch.object(web_console, "run", return_value=0), \
                mock.patch.object(web_console.logging, "basicConfig") as basic:
            web_console.main(["--no-browser"])
        basic.assert_called_once()
        kwargs = basic.call_args.kwargs
        self.assertEqual(kwargs["level"], logging.INFO)
        self.assertIn("%(asctime)s", kwargs["format"])

    def test_run_alone_does_not_touch_logging(self):
        from tests.test_web_console import FakeHub, FakeMeter, FakeService, args
        with mock.patch.object(web_console.logging, "basicConfig") as basic, mock.patch("builtins.print"):
            web_console.run(args(), service_factory=FakeService, hub_factory=FakeHub,
                            meter_factory=FakeMeter, sleep=lambda _s: None, loop_limit=1,
                            reuse_existing=False)
        basic.assert_not_called()


if __name__ == "__main__":
    unittest.main()
