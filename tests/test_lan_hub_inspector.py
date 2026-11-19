"""Session data for the Inspector: read-only gain and +48V, and the locked-feature map."""

from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request
from unittest import mock

from flow8.command_boundary import Flow8CommandBoundary
from flow8.lan_hub import LAN_LOCKED_FEATURES, LAN_POLICY, Flow8LanHub
from flow8.service import Flow8Service


class InspectorSessionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            Flow8Service, "is_connected",
            new_callable=mock.PropertyMock, return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def get(self, path: str) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))

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

    def channel(self, snap: dict, idx: int) -> dict:
        return next(c for c in snap["channels"] if c["index"] == idx)

    def test_policy_and_locked_map_are_in_the_session(self):
        snap = self.get("/api/session")
        self.assertEqual(snap["lanPolicy"], {"gain": False, "phantom": False})
        self.assertEqual(set(snap["locked"]), {
            "gain", "phantom", "solo", "limiter", "geq", "fx", "tap", "eqParametric",
            "stereoLink", "routing", "outputPad", "footswitch", "hwSnapshots",
        })

    def test_locked_features_have_no_allowlist_entry_except_host_only_ones(self):
        # A feature in the locked map must not be sendable. Gain and +48V are on the
        # allowlist for the host app, so the LAN policy must keep them closed.
        allow = Flow8CommandBoundary.ACTIVE_ALLOWLIST
        self.assertFalse(any(k.endswith(".solo") for k in allow))
        self.assertFalse(any(k.split(".")[0] in ("main", "mon1", "mon2") and k.split(".")[1] not in ("fader", "balance") for k in allow))
        self.assertFalse(any(k.startswith(("fx1.", "fx2.")) and not k.endswith(".fader") for k in allow))
        self.assertIn("gain", LAN_LOCKED_FEATURES)
        self.assertFalse(LAN_POLICY["gain"])
        self.assertFalse(LAN_POLICY["phantom"])

    def test_gain_and_phantom_unknown_until_the_mixer_reports_them(self):
        snap = self.get("/api/session")
        ch1 = self.channel(snap, 1)
        self.assertIsNone(ch1["gain"])
        self.assertIsNone(ch1["phantom"])
        self.assertEqual(ch1["gainProvenance"], "UNSYNCED")
        ch5 = self.channel(snap, 5)
        self.assertEqual(ch5["gainProvenance"], "UNSUPPORTED")
        self.assertEqual(ch5["phantomProvenance"], "UNSUPPORTED")
        self.assertEqual(self.channel(snap, 3)["phantomProvenance"], "UNSUPPORTED")

    def test_gain_and_phantom_show_hardware_values(self):
        self.service._on_midi_in_event({"status": 0xB0, "channel": 1, "data1": 8, "data2": 90})
        self.service._on_midi_in_event({"status": 0xB0, "channel": 1, "data1": 12, "data2": 127})
        ch1 = self.channel(self.get("/api/session"), 1)
        self.assertEqual(ch1["gain"], 90)
        self.assertEqual(ch1["gainProvenance"], "OBSERVED")
        self.assertIs(ch1["phantom"], True)

    def test_low_cut_and_compressor_carry_provenance(self):
        self.assertEqual(self.post({"action": "setLowCut", "channel": 2, "value": 30}), 200)
        ch2 = self.channel(self.get("/api/session"), 2)
        self.assertEqual(ch2["lowCut"], 30)
        self.assertEqual(ch2["lowCutProvenance"], "COMMANDED")
        self.assertEqual(ch2["compressorProvenance"], "UNSYNCED")
        self.assertEqual(self.channel(self.get("/api/session"), 6)["compressorProvenance"], "UNSUPPORTED")

    def test_gain_and_phantom_stay_blocked_over_lan(self):
        self.assertEqual(self.post({"action": "setPhantom", "channel": 1, "value": True}), 403)
        self.assertEqual(self.post({"action": "setGain", "channel": 1, "value": 100}), 403)
        self.assertIsNone(self.channel(self.get("/api/session"), 1)["phantom"])


if __name__ == "__main__":
    unittest.main()
