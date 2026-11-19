"""USB capture meters: level maths, device choice, stream lifecycle, hub wiring.

The audio backend is a fake with the sounddevice interface, so these tests run
without PortAudio or a FLOW 8. Test signals have known levels.
"""

from __future__ import annotations

import json
import math
import threading
import time
import unittest
import urllib.request
from unittest import mock

import numpy as np

from flow8.audio_meter import (
    CAPTURE_MAP_RECORDING,
    FLOOR_DB,
    Flow8AudioMeter,
    LevelMeter,
    pick_capture_device,
    to_dbfs,
)
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service

RATE = 48000


def sine(amplitude: float, frames: int = 4800, freq: float = 1000.0) -> np.ndarray:
    t = np.arange(frames) / RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def block(columns: dict[int, np.ndarray], frames: int = 4800, channels: int = 10) -> np.ndarray:
    b = np.zeros((frames, channels), dtype=np.float32)
    for c, data in columns.items():
        b[:, c] = data
    return b


class LevelMathTests(unittest.TestCase):
    def test_to_dbfs(self):
        self.assertEqual(to_dbfs(1.0), 0.0)
        self.assertAlmostEqual(to_dbfs(0.5), -6.02, places=2)
        self.assertEqual(to_dbfs(0.0), FLOOR_DB)

    def test_full_scale_sine_reads_0_peak_and_minus_3_rms(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        for _ in range(20):  # 2 s, far beyond the 300 ms RMS window
            m.process(block({0: sine(1.0)}))
        lv = m.read()["ch1"]
        self.assertAlmostEqual(lv["peak"], 0.0, delta=0.1)
        self.assertAlmostEqual(lv["rms"], -3.0, delta=0.2)

    def test_minus_20_dbfs_sine(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        for _ in range(20):
            m.process(block({3: sine(0.1)}))
        lv = m.read()["ch4"]
        self.assertAlmostEqual(lv["peak"], -20.0, delta=0.1)
        self.assertAlmostEqual(lv["rms"], -23.0, delta=0.2)

    def test_silent_strips_read_the_floor(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        m.process(block({0: sine(0.5)}))
        out = m.read()
        self.assertEqual(out["ch2"], {"peak": FLOOR_DB, "rms": FLOOR_DB})

    def test_stereo_pair_uses_the_louder_side(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        for _ in range(20):
            m.process(block({4: sine(0.1), 5: sine(0.5), 8: sine(0.25), 9: sine(0.05)}))
        out = m.read()
        self.assertAlmostEqual(out["ch5"]["peak"], -6.0, delta=0.1)   # Line 5/6 -> right side
        self.assertAlmostEqual(out["main"]["peak"], -12.0, delta=0.1)  # Main L/R -> left side

    def test_peak_holds_a_short_transient_until_read(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        spike = np.zeros(512, dtype=np.float32)
        spike[100] = 0.9
        m.process(block({1: spike}, frames=512))
        for _ in range(5):
            m.process(block({}, frames=512))
        self.assertAlmostEqual(m.read()["ch2"]["peak"], to_dbfs(0.9), delta=0.1)
        self.assertEqual(m.read()["ch2"]["peak"], FLOOR_DB)  # window restarts after read

    def test_rms_rises_with_300ms_time_constant(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        m.process(block({0: sine(1.0, frames=int(RATE * 0.3))}, frames=int(RATE * 0.3)))
        # After one time constant the mean square reaches 1 - 1/e of its target.
        expected = to_dbfs(math.sqrt(0.5 * (1 - math.exp(-1))))
        self.assertAlmostEqual(m.read()["ch1"]["rms"], expected, delta=0.2)

    def test_ch7_and_buses_have_no_meter(self):
        self.assertEqual(set(LevelMeter(CAPTURE_MAP_RECORDING, RATE).strips),
                         {"ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "main",
                          "in5", "in6", "in7", "in8"})

    def test_short_block_does_not_crash(self):
        m = LevelMeter(CAPTURE_MAP_RECORDING, RATE)
        m.process(np.zeros((64, 2), dtype=np.float32))  # fewer channels than mapped
        m.process(np.zeros((0, 10), dtype=np.float32))
        self.assertEqual(m.read()["ch1"]["peak"], FLOOR_DB)


HOSTAPIS = [{"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"}]


def dev(name: str, ins: int, api: int, rate: float = 48000.0) -> dict:
    return {"name": name, "max_input_channels": ins, "hostapi": api, "default_samplerate": rate}


class DevicePickTests(unittest.TestCase):
    def test_prefers_wasapi_multi_in_1_10(self):
        devices = [
            dev("Microphone (Realtek)", 2, 0),
            dev("Multi In 1-10 (BEHRINGER FLOW 8)", 10, 0),
            dev("Mic 1 (BEHRINGER FLOW 8)", 1, 2),
            dev("Main L/R (BEHRINGER FLOW 8)", 2, 2),
            dev("Multi In 1-10 (BEHRINGER FLOW 8)", 10, 2),
        ]
        d = pick_capture_device(devices, HOSTAPIS)
        self.assertEqual((d.index, d.host_api, d.channels, d.mode), (4, "Windows WASAPI", 10, "recording"))

    def test_streaming_mode_falls_back_to_main_only(self):
        d = pick_capture_device([dev("Main L/R (BEHRINGER FLOW 8)", 2, 2, 44100.0)], HOSTAPIS)
        self.assertEqual((d.mode, d.channels, d.sample_rate), ("streaming", 2, 44100.0))
        self.assertEqual(set(d.capture_map), {"main"})

    def test_no_flow8_returns_none(self):
        self.assertIsNone(pick_capture_device([dev("Microphone (Realtek)", 2, 2)], HOSTAPIS))

    def test_single_input_endpoints_are_ignored(self):
        self.assertIsNone(pick_capture_device([dev("Mic 1 (BEHRINGER FLOW 8)", 1, 2)], HOSTAPIS))


class FakeStream:
    def __init__(self, callback, channels, **kw):
        self.callback, self.channels, self.kw = callback, channels, kw
        self.active = False
        self.closed = False

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True

    def feed(self, data: np.ndarray):
        self.callback(data, data.shape[0], None, None)


class FakeBackend:
    def __init__(self, devices, fail_open=False):
        self.devices = devices
        self.fail_open = fail_open
        self.streams: list[FakeStream] = []

    def query_devices(self):
        return self.devices

    def query_hostapis(self):
        return HOSTAPIS

    def InputStream(self, *, device, channels, samplerate, blocksize, dtype, callback):  # noqa: N802
        if self.fail_open:
            raise RuntimeError("Invalid sample rate")
        s = FakeStream(callback, channels, device=device, samplerate=samplerate, blocksize=blocksize, dtype=dtype)
        self.streams.append(s)
        return s


FLOW8 = [dev("Multi In 1-10 (BEHRINGER FLOW 8)", 10, 2)]


class StreamLifecycleTests(unittest.TestCase):
    def make(self, backend):
        frames, statuses = [], []
        got = threading.Event()

        def publish(levels):
            frames.append(levels)
            got.set()

        m = Flow8AudioMeter(publish, statuses.append, backend=backend, publish_hz=100)
        self.addCleanup(m.stop)
        return m, frames, statuses, got

    def test_opens_10_channel_float_stream_and_publishes_levels(self):
        backend = FakeBackend(FLOW8)
        m, frames, statuses, got = self.make(backend)
        self.assertTrue(m.start())
        s = backend.streams[0]
        self.assertEqual((s.channels, s.kw["device"], s.kw["dtype"], s.kw["samplerate"]), (10, 0, "float32", 48000.0))
        self.assertEqual(statuses[-1]["state"], "running")
        s.feed(block({2: sine(0.5)}))
        self.assertTrue(got.wait(1.0))
        deadline = time.time() + 1
        while time.time() < deadline and not any(f["ch3"]["peak"] > -7 for f in frames):
            time.sleep(0.01)
        self.assertTrue(any(abs(f["ch3"]["peak"] + 6.0) < 0.2 for f in frames))

    def test_no_device_reports_why(self):
        m, _, statuses, _ = self.make(FakeBackend([dev("Microphone (Realtek)", 2, 2)]))
        self.assertFalse(m.start())
        self.assertEqual(statuses[-1]["state"], "no_device")
        self.assertIn("Recording Mode", statuses[-1]["detail"])

    def test_open_failure_reports_error(self):
        m, _, statuses, _ = self.make(FakeBackend(FLOW8, fail_open=True))
        self.assertFalse(m.start())
        self.assertEqual(statuses[-1]["state"], "error")
        self.assertIn("Invalid sample rate", statuses[-1]["detail"])

    def test_missing_library_reports_unavailable(self):
        m, _, statuses, _ = self.make(None)
        with mock.patch.dict("sys.modules", {"sounddevice": None}):
            self.assertFalse(m.start())
        self.assertEqual(statuses[-1]["state"], "unavailable")
        self.assertIn("sounddevice", statuses[-1]["detail"])

    def test_retry_waits_5_s_then_finds_a_device_plugged_in_later(self):
        backend = FakeBackend([])
        m, _, statuses, _ = self.make(backend)
        self.assertFalse(m.start())
        backend.devices = FLOW8
        self.assertFalse(m.ensure_running())  # within 5 s: no new attempt
        m._last_attempt -= 10
        self.assertTrue(m.ensure_running())
        self.assertEqual(statuses[-1]["state"], "running")

    def test_lost_stream_is_closed_and_reported(self):
        backend = FakeBackend(FLOW8)
        m, _, statuses, _ = self.make(backend)
        m.start()
        backend.streams[0].active = False  # driver stopped (cable pulled)
        deadline = time.time() + 1
        while time.time() < deadline and m.is_running:
            time.sleep(0.01)
        self.assertFalse(m.is_running)
        self.assertTrue(backend.streams[0].closed)
        self.assertEqual(statuses[-1]["state"], "error")

    def test_stop_closes_stream(self):
        backend = FakeBackend(FLOW8)
        m, _, statuses, _ = self.make(backend)
        m.start()
        m.stop()
        self.assertTrue(backend.streams[0].closed)
        self.assertEqual(statuses[-1]["state"], "stopped")


class HubWiringTests(unittest.TestCase):
    def test_meter_levels_and_status_reach_the_hub(self):
        service = Flow8Service(auto_connect=False)
        hub = Flow8LanHub(service, host="127.0.0.1", port=0)
        port = hub.start()
        self.addCleanup(hub.stop)
        backend = FakeBackend(FLOW8)
        m = Flow8AudioMeter(hub.publish_meters, hub.set_meter_status, backend=backend, publish_hz=20)
        self.addCleanup(m.stop)
        self.assertTrue(m.start())
        backend.streams[0].feed(block({8: sine(0.5), 9: sine(0.5)}))
        deadline = time.time() + 2
        while time.time() < deadline and not hub.meter_feed_live:
            time.sleep(0.02)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/session", timeout=3) as r:
            s = json.loads(r.read())
        self.assertTrue(s["meterFeed"])
        self.assertEqual(s["meterStatus"]["state"], "running")
        self.assertEqual(s["meterStatus"]["mode"], "recording")


if __name__ == "__main__":
    unittest.main()
