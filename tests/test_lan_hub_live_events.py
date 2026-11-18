"""LAN hub live data: RX/TX events, scene-edited tracking, meter feed, fonts."""

from __future__ import annotations

import json
import queue
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

from flow8 import lan_hub
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service


class _Hub(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)
        # Listen to the event stream the same way the hub feeds browsers.
        self.events: queue.Queue[bytes] = queue.Queue(maxsize=256)
        with self.hub._sse_lock:
            self.hub._subscribers.append((self.events, "test"))

    def drain(self) -> list[dict]:
        out = []
        while True:
            try:
                raw = self.events.get_nowait().decode("utf-8")
            except queue.Empty:
                return out
            out.append(json.loads(raw[len("data: "):].strip()))

    def post(self, payload: dict) -> int:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status
        except urllib.error.HTTPError as err:
            err.close()
            return err.code

    def session(self) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/session", timeout=3) as r:
            return json.loads(r.read())


class RxTxEventTests(_Hub):
    def test_hardware_move_is_reported_as_rx_with_param_id(self):
        # MIDI channel 3, CC 7 = strip 3 fader moved on the mixer.
        self.service._on_midi_in_event({"status": 0xB0, "channel": 3, "data1": 7, "data2": 90})
        rx = [e for e in self.drain() if e.get("type") == "rx"]
        self.assertEqual(len(rx), 1)
        self.assertEqual(rx[0]["paramId"], "ch3.fader")
        self.assertEqual(rx[0]["value"], 90)

    def test_command_is_reported_as_tx_with_target(self):
        self.drain()
        self.assertEqual(self.post({"action": "setMute", "channel": 2, "value": True}), 200)
        tx = [e for e in self.drain() if e.get("type") == "tx"]
        self.assertEqual(len(tx), 1)
        self.assertEqual((tx[0]["action"], tx[0]["channel"]), ("setMute", 2))

        self.assertEqual(self.post({"action": "setBusFader", "bus": "fx1", "value": 40}), 200)
        tx = [e for e in self.drain() if e.get("type") == "tx"]
        self.assertEqual(tx[0]["bus"], "fx1")

    def test_rejected_command_sends_no_tx(self):
        self.drain()
        self.assertEqual(self.post({"action": "setGain", "channel": 1, "value": 5}), 403)
        self.assertFalse([e for e in self.drain() if e.get("type") == "tx"])

    def test_internal_events_are_not_rx(self):
        self.service._notify_listeners("__changed__", None)
        self.service._notify_listeners("__reconcile__", None)
        kinds = [e["type"] for e in self.drain()]
        self.assertEqual(kinds, ["state", "link"])


class SceneTrackingTests(_Hub):
    def test_no_scene_at_start(self):
        s = self.session()
        self.assertIsNone(s["currentScene"])
        self.assertFalse(s["sceneEdited"])

    def test_change_after_save_marks_edited_and_recall_clears_it(self):
        self.post({"action": "setFader", "channel": 1, "value": 80})
        self.assertEqual(self.post({"action": "captureScene", "name": "SCENE 2"}), 200)
        self.assertEqual((self.session()["currentScene"], self.session()["sceneEdited"]), ("SCENE 2", False))

        self.post({"action": "setFader", "channel": 1, "value": 70})
        self.assertTrue(self.session()["sceneEdited"])

        self.assertEqual(self.post({"action": "recallScene", "name": "SCENE 2"}), 200)
        self.assertFalse(self.session()["sceneEdited"])

    def test_hardware_move_marks_edited(self):
        self.post({"action": "setFader", "channel": 1, "value": 80})
        self.post({"action": "captureScene", "name": "SCENE 1"})
        self.service._on_midi_in_event({"status": 0xB0, "channel": 1, "data1": 7, "data2": 10})
        self.assertTrue(self.session()["sceneEdited"])

    def test_rename_does_not_mark_edited(self):
        self.post({"action": "setFader", "channel": 1, "value": 80})
        self.post({"action": "captureScene", "name": "SCENE 1"})
        self.post({"action": "setScribble", "channel": 1, "label": "Kick"})
        self.assertFalse(self.session()["sceneEdited"])


class MeterFeedTests(_Hub):
    def test_no_feed_until_frames_arrive(self):
        self.assertFalse(self.session()["meterFeed"])
        self.assertFalse(self.hub.meter_feed_live)

    def test_frame_is_broadcast_and_marks_feed_live(self):
        self.drain()
        self.assertTrue(self.hub.publish_meters({"ch1": {"peak": -6.04, "rms": -18.0}}))
        frames = [e for e in self.drain() if e.get("type") == "meters"]
        self.assertEqual(frames[0]["levels"]["ch1"], {"peak": -6.0, "rms": -18.0})
        self.assertTrue(self.session()["meterFeed"])

    def test_rate_limit_drops_fast_frames(self):
        self.drain()
        self.assertTrue(self.hub.publish_meters({"ch1": {"peak": -6, "rms": -18}}))
        self.assertFalse(self.hub.publish_meters({"ch1": {"peak": -5, "rms": -17}}))
        self.assertEqual(len([e for e in self.drain() if e.get("type") == "meters"]), 1)

    def test_feed_goes_stale(self):
        self.hub.publish_meters({"ch1": {"peak": -6, "rms": -18}})
        with mock.patch.object(lan_hub.time, "monotonic", return_value=time.monotonic() + 5):
            self.assertFalse(self.hub.meter_feed_live)

    def test_full_client_queue_drops_meter_frames_but_keeps_the_client(self):
        slow: queue.Queue[bytes] = queue.Queue(maxsize=1)
        slow.put_nowait(b"data: {}\n\n")
        with self.hub._sse_lock:
            self.hub._subscribers.append((slow, "slow"))
        self.hub.publish_meters({"ch1": {"peak": -6, "rms": -18}})
        with self.hub._sse_lock:
            self.assertIn((slow, "slow"), self.hub._subscribers)


class FontRouteTests(_Hub):
    def test_bundled_font_is_served(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/fonts/barlow-condensed-600.woff2", timeout=3
        ) as r:
            self.assertEqual(r.headers["Content-Type"], "font/woff2")
            self.assertEqual(r.read(4), b"wOF2")

    def test_path_outside_fonts_is_refused(self):
        for path in ("/fonts/../lan_hub.py", "/fonts/x.ttf", "/fonts/%2e%2e/app.js"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3)
                self.assertEqual(ctx.exception.code, 404)
                ctx.exception.close()


if __name__ == "__main__":
    unittest.main()
