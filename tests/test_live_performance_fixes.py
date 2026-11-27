"""Phase 2 live-performance fixes: T1 (orphaned SSE stream) and M2 (unbounded command log)."""

from __future__ import annotations

import http.client
import json
import socket
import time
import unittest
from pathlib import Path
from unittest import mock

from flow8 import command_boundary
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service
from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import fake_open_port

WEB_UI = Path(__file__).resolve().parent.parent / "flow8" / "web_ui"


class OrphanedEventStreamTests(unittest.TestCase):
    """T1: a client dropped by broadcast() must see its stream end, so EventSource reconnects."""

    def setUp(self):
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def _open_stream(self, client_id):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        self.addCleanup(conn.close)
        conn.request("GET", f"/api/events?clientId={client_id}")
        response = conn.getresponse()
        first = json.loads(response.readline().decode("utf-8").removeprefix("data: "))
        self.assertEqual(first["type"], "connected")
        return response

    def _drop(self, client_id):
        """Remove the subscriber the way broadcast() does for a full queue."""
        with self.hub._sse_lock:
            item = next(s for s in self.hub._subscribers if s[1] == client_id)
            self.hub._subscribers.remove(item)

    def test_dropped_client_stream_is_closed(self):
        response = self._open_stream("dropme")
        self._drop("dropme")
        started = time.monotonic()
        try:
            rest = response.read()  # returns only when the server closes the connection
        except (socket.timeout, TimeoutError):
            self.fail("the server kept a dropped client's event stream open")
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertNotIn(b"data:", rest.replace(b"\r", b""))

    def test_full_queue_on_state_event_drops_and_closes(self):
        response = self._open_stream("slow")
        with self.hub._sse_lock:
            q, _ = next(s for s in self.hub._subscribers if s[1] == "slow")
        # Fill the client's queue faster than the handler drains it, then send a
        # non-droppable event: broadcast() must drop the client and the stream must end.
        with mock.patch.object(q, "put_nowait", side_effect=__import__("queue").Full):
            self.hub.broadcast({"type": "state"})
        with self.hub._sse_lock:
            self.assertFalse(any(s[1] == "slow" for s in self.hub._subscribers))
        try:
            response.read()
        except (socket.timeout, TimeoutError):
            self.fail("the server kept a dropped client's event stream open")

    def test_live_client_stream_stays_open(self):
        response = self._open_stream("live")
        self.hub.broadcast({"type": "state"})
        line = response.readline()
        while line.strip() == b"":  # the blank line that ends the "connected" event
            line = response.readline()
        self.assertTrue(line.startswith(b"data: "))
        self.assertEqual(json.loads(line[6:])["type"], "state")


class ClientReloadOnReconnectTests(unittest.TestCase):
    """T1 client side: after EventSource reconnects, the console reloads its state."""

    def test_both_consoles_reload_on_a_reconnect(self):
        for path in (WEB_UI / "app.js", WEB_UI / "v3" / "v3.js"):
            source = path.read_text(encoding="utf-8")
            self.assertIn("sseConnectedOnce", source, f"{path.name} does not reload on an SSE reconnect")


class BoundedCommandLogTests(NoHardwareMixin, unittest.TestCase):
    """M2: the in-memory command log keeps a bounded window; totals stay exact."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(command_boundary, "COMMAND_LOG_CAPACITY", 5)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.out, self.driver = fake_open_port(self.service.midi_out)
        self.boundary = self.service.command_boundary

    def test_log_keeps_only_the_newest_entries(self):
        for value in range(8):
            self.service.set_fader(1, value)
        log = self.boundary.command_log
        self.assertEqual(len(log), 5)
        self.assertEqual([e.target_value for e in log], [3, 4, 5, 6, 7])
        self.assertIsInstance(log, list)

    def test_totals_count_every_command(self):
        for value in range(8):
            self.service.set_fader(1, value)
        counts = self.boundary.command_counts
        self.assertEqual(counts["commands"], 8)
        self.assertEqual(counts["accepted"], 8)
        self.assertEqual(counts["driverDispatched"], 8)
        self.assertEqual(counts["rejected"], 0)

    def test_rejected_commands_are_counted(self):
        with self.assertRaises(Exception):
            self.boundary.execute_command("not.a.param", 1)
        counts = self.boundary.command_counts
        self.assertEqual(counts["commands"], 1)
        self.assertEqual(counts["rejected"], 1)
        self.assertEqual(counts["accepted"], 0)

    def test_status_dispatch_uses_totals_not_the_window(self):
        for value in range(8):
            self.service.set_fader(1, value)
        hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        dispatch = hub._dispatch_snapshot()
        self.assertEqual(dispatch["commands"], 8)
        self.assertEqual(dispatch["driverDispatched"], 8)
        self.assertEqual(dispatch["last"]["paramId"], "ch1.fader")


if __name__ == "__main__":
    unittest.main()
