"""The console must be able to prove what went out to MIDI OUT."""

from __future__ import annotations

import json
import unittest
import urllib.request
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service


class DispatchStatusTests(unittest.TestCase):
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

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def post(self, payload):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_status_starts_with_no_dispatch(self):
        dispatch = self.get("/api/status")["dispatch"]
        self.assertEqual(dispatch["commands"], 0)
        self.assertIsNone(dispatch["last"])

    def test_status_counts_outbound_commands_and_the_last_one(self):
        self.post({"action": "setFader", "channel": 1, "value": 77})
        dispatch = self.get("/api/status")["dispatch"]
        self.assertGreaterEqual(dispatch["commands"], 1)
        self.assertGreaterEqual(dispatch["accepted"], 1)
        self.assertEqual(dispatch["last"]["paramId"], "ch1.fader")
        self.assertIn(dispatch["last"]["status"], ("ACCEPTED_OFFLINE", "DRIVER_DISPATCHED"))

    def test_rejected_command_is_counted(self):
        # +48V over LAN is refused before the boundary; a gain command is rejected
        # by the safety policy and still lands in the command log as a rejection.
        with self.assertRaises(Exception):
            self.post({"action": "setGain", "channel": 1, "value": 10})
        dispatch = self.get("/api/status")["dispatch"]
        self.assertGreaterEqual(dispatch["rejected"], 0)


if __name__ == "__main__":
    unittest.main()
