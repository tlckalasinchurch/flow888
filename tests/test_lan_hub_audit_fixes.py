"""LAN hub behaviour found by the UI audit: offline guard and the muteAll action."""

from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service


class _HubCase(unittest.TestCase):
    connected = True

    def setUp(self):
        patcher = mock.patch.object(
            Flow8Service, "is_connected",
            new_callable=mock.PropertyMock, return_value=self.connected,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def post(self, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            try:
                return err.code, json.loads(err.read().decode("utf-8"))
            finally:
                err.close()

    def mute(self, ch: int):
        return self.service.state_store.get_parameter(f"ch{ch}.mute")


class DisconnectedHubTests(_HubCase):
    connected = False

    def test_commands_are_rejected_and_state_is_unchanged(self):
        for payload in (
            {"action": "setFader", "channel": 1, "value": 90},
            {"action": "setMute", "channel": 1, "value": True},
            {"action": "muteAll", "value": True},
            {"action": "setBusFader", "bus": "mon1", "value": 50},
            {"action": "undo"},
            {"action": "captureScene", "name": "SCENE 1"},
        ):
            with self.subTest(payload=payload):
                code, res = self.post(payload)
                self.assertEqual(code, 503)
                self.assertFalse(res["ok"])
                self.assertEqual(res["code"], "not_connected")
        self.assertIsNone(self.mute(1) and self.mute(1).commanded_raw_midi)

    def test_scribble_stays_allowed_offline(self):
        code, res = self.post({"action": "setScribble", "channel": 2, "label": "Kick", "color": "#FFB45B"})
        self.assertEqual(code, 200)
        self.assertTrue(res["ok"])

    def test_safety_blocks_still_return_403(self):
        code, _ = self.post({"action": "setGain", "channel": 1, "value": 10})
        self.assertEqual(code, 403)


class MuteAllTests(_HubCase):
    def test_mute_all_mutes_every_input_and_undo_restores_in_one_step(self):
        # Undo never restores a value the mixer is not known to hold, so first
        # give every mute a known state (unmuted).
        self.post({"action": "muteAll", "value": False})
        code, res = self.post({"action": "muteAll", "value": True})
        self.assertEqual(code, 200, res)
        for ch in range(1, 8):
            self.assertEqual(self.mute(ch).commanded_raw_midi, 127, f"ch{ch}")

        self.service.undo()
        for ch in range(1, 8):
            self.assertEqual(self.mute(ch).commanded_raw_midi, 0, f"ch{ch} still muted after one undo")

    def test_mute_all_false_unmutes(self):
        self.post({"action": "muteAll", "value": True})
        code, _ = self.post({"action": "muteAll", "value": False})
        self.assertEqual(code, 200)
        for ch in range(1, 8):
            self.assertEqual(self.mute(ch).commanded_raw_midi, 0, f"ch{ch}")

    def test_mute_all_requires_value(self):
        code, res = self.post({"action": "muteAll", "muted": True})
        self.assertEqual(code, 400)
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
