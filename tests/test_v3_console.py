"""FLOW 888 v3 console: served by the hub, and every command it sends is one the hub accepts.

The payloads below are copied from flow8/web_ui/v3/v3.js. If v3 changes a payload shape, the
matching test here must change with it.
"""

from __future__ import annotations

import json
import re
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from flow8 import web_console
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service

V3 = Path(web_console.__file__).parent / "web_ui" / "v3"


class V3StaticTests(unittest.TestCase):
    def setUp(self):
        self.js = (V3 / "v3.js").read_text(encoding="utf-8")

    def test_no_gain_or_phantom_sender(self):
        for forbidden in ("setGain", "setPhantom", "set48V", "includePhantom"):
            self.assertNotIn(forbidden, self.js, forbidden)

    def test_only_hub_api_is_used(self):
        urls = set(re.findall(r"['`](/api/[a-z/]+)", self.js))
        self.assertTrue(urls <= {"/api/action", "/api/session", "/api/events", "/api/presets"}, urls)
        self.assertNotIn("http://", self.js)
        self.assertNotIn("https://", self.js)

    def test_mix_workspace_adds_no_unsupported_control(self):
        # The console layout shows Solo, gate and EQ frequency/Q in its reference image; the FLOW 8
        # path supports none of them, so v3 must not send them.
        for forbidden in ("setSolo", "setGate", "eqFreq", "setEqFreq", "setEqQ", "setStereoLink"):
            self.assertNotIn(forbidden, self.js, forbidden)

    def test_unknown_values_render_as_unknown(self):
        self.assertIn("const known = (p) => p === 'OBSERVED' || p === 'COMMANDED';", self.js)


class _Hub(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return r.status, r.headers, r.read()

    def post(self, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            try:
                return err.code, json.loads(err.read().decode("utf-8"))
            finally:
                err.close()


class V3ServedTests(_Hub):
    def test_v3_assets_are_served_and_never_cached(self):
        for path, needle in (("/v3/", b"/v3/v3.js"), ("/v3/v3.css", b"--sel"), ("/v3/v3.js", b"/api/action")):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertIn("no-store", headers.get("Cache-Control", ""))
                self.assertIn(needle, body)

    def test_v2_console_still_served(self):
        status, _, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"app.js", body)


class V3ActionTests(_Hub):
    ACCEPTED = [
        {"action": "setFader", "channel": 1, "value": 96},
        {"action": "setFader", "channel": 8, "value": 101},
        {"action": "setSend", "channel": 1, "target": "mon1", "value": 80, "unit": "raw"},
        {"action": "setBusFader", "bus": "mon1", "value": 90},
        {"action": "setMute", "channel": 2, "value": True},
        {"action": "muteAll", "value": False},
        {"action": "setEqBand", "channel": 1, "band": "low_mid", "value": 58, "unit": "raw"},
        {"action": "resetEqFlat", "channel": 1},
        {"action": "setLowCut", "channel": 1, "value": 23, "unit": "raw"},
        {"action": "setCompressor", "channel": 1, "value": 40, "unit": "raw"},
        {"action": "setBusGeq", "bus": "main", "band": 1, "value": 70},
        {"action": "setBusLimiter", "bus": "main", "value": 110},
        {"action": "setFxPreset", "engine": "fx1", "value": 9},
        {"action": "setFxParam", "engine": "fx1", "param": 1, "value": 50},
        {"action": "setFxParam", "engine": "fx1", "param": 2, "value": True},
        {"action": "setActiveBus", "bus": "mon1"},
        {"action": "undo"},
    ]

    def test_every_v3_command_is_accepted(self):
        for payload in self.ACCEPTED:
            with self.subTest(action=payload["action"]):
                code, res = self.post(payload)
                self.assertEqual(code, 200, res)

    def test_a_drag_is_one_undo_step(self):
        self.post({"action": "setFader", "channel": 3, "value": 50})
        self.post({"action": "beginGesture"})
        for v in (60, 70, 80):
            self.post({"action": "setFader", "channel": 3, "value": v})
        code, res = self.post({"action": "endGesture"})
        self.assertEqual(code, 200, res)
        self.post({"action": "undo"})
        self.assertEqual(self.service.state_store.get_parameter("ch3.fader").commanded_value, 50)

    def test_redo_button_reapplies_an_undone_drag(self):
        self.post({"action": "setFader", "channel": 2, "value": 40})
        self.post({"action": "setFader", "channel": 2, "value": 90})
        self.post({"action": "undo"})
        code, res = self.post({"action": "redo"})
        self.assertEqual(code, 200, res)
        self.assertEqual(self.service.state_store.get_parameter("ch2.fader").commanded_value, 90)

    def test_preset_cue_and_show_mode_paths(self):
        presets = json.loads(self.get("/api/presets")[2])["presets"]
        code, res = self.post({"action": "applyPreset", "channel": 1, "presetId": presets[0]["id"]})
        self.assertEqual(code, 200, res)
        code, saved = self.post({"action": "librarySave", "name": "Worship set"})
        self.assertEqual(code, 200, saved)
        code, res = self.post({"action": "libraryLoad", "id": saved["id"]})
        self.assertEqual(code, 200, res)
        # The default show modes have steps NOT SET: the hub refuses to run them.
        code, res = self.post({"action": "runShowMode", "id": "mc"})
        self.assertEqual(code, 409)
        self.assertEqual(res["code"], "show_mode_unset")


if __name__ == "__main__":
    unittest.main()
