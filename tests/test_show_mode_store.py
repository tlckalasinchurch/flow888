"""Show Mode persistence: round trip, refusals, damaged and hand-edited files."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flow8.show_mode import ShowModeError, default_modes
from flow8.show_mode_store import SHOW_MODES_FORMAT, ShowModeStore

FULL_MC = [
    {"parameter": "send_fx1", "channels": [1], "value": 0},
    {"parameter": "mute", "channels": [2, 3, 4, 5, 6], "value": True},
    {"parameter": "mute", "channels": [1], "value": False},
    {"parameter": "fader", "channels": [1], "value": 95},
    {"parameter": "fader", "channels": [7], "value": 30},
]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "show_modes.json"

    def test_fresh_store_returns_templates_not_ready(self):
        store = ShowModeStore(self.path)
        rows = store.summaries()
        self.assertEqual([r["id"] for r in rows], ["mc", "band"])
        self.assertTrue(all(not r["ready"] for r in rows))
        self.assertEqual(rows[0]["unsetCount"], 2)
        self.assertIsNone(store.load_error)
        self.assertFalse(self.path.exists())

    def test_save_round_trip_survives_reload(self):
        store = ShowModeStore(self.path)
        summary = store.save("mc", FULL_MC)
        self.assertTrue(summary["ready"])
        again = ShowModeStore(self.path)
        self.assertTrue(again.summaries()[0]["ready"])
        self.assertEqual(again.get("mc")["steps"], FULL_MC)
        self.assertEqual(json.loads(self.path.read_text("utf-8"))["format"], SHOW_MODES_FORMAT)

    def test_save_refuses_gain_phantom_and_channel_8_and_writes_nothing(self):
        store = ShowModeStore(self.path)
        for bad in (
            [{"parameter": "gain", "channels": [1], "value": 10}],
            [{"parameter": "phantom", "channels": [1], "value": True}],
            [{"parameter": "fader", "channels": [8], "value": 50}],
        ):
            with self.subTest(bad), self.assertRaises(ShowModeError):
                store.save("mc", bad)
        self.assertFalse(self.path.exists())
        self.assertEqual(store.get("mc"), default_modes()["mc"])

    def test_hand_edited_file_with_phantom_falls_back_to_template(self):
        evil = {"format": SHOW_MODES_FORMAT, "modes": {
            "mc": {"name": "MC", "steps": [{"parameter": "phantom", "channels": [1], "value": True}]},
            "band": {"name": "BAND", "steps": FULL_MC},
        }}
        text = json.dumps(evil)
        self.path.write_text(text, encoding="utf-8")
        store = ShowModeStore(self.path)
        self.assertEqual(store.get("mc"), default_modes()["mc"])
        self.assertIn("mc", store.load_error)
        self.assertEqual(store.get("band")["steps"], FULL_MC)  # the good mode survives
        self.assertEqual(self.path.read_text("utf-8"), text)

    def test_damaged_json_uses_templates_and_keeps_file(self):
        self.path.write_text("{not json", encoding="utf-8")
        store = ShowModeStore(self.path)
        self.assertIsNotNone(store.load_error)
        self.assertEqual(store.get("band"), default_modes()["band"])
        self.assertEqual(self.path.read_text("utf-8"), "{not json")

    def test_unknown_mode_id_is_keyerror(self):
        store = ShowModeStore(self.path)
        with self.assertRaises(KeyError):
            store.get("nope")
        with self.assertRaises(KeyError):
            store.save("nope", FULL_MC)

    def test_no_path_keeps_modes_in_memory(self):
        store = ShowModeStore(None)
        store.save("mc", FULL_MC)
        self.assertTrue(store.summaries()[0]["ready"])


class StoreHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "show_modes.json"

    def _write(self, modes):
        self.path.write_text(json.dumps({"format": SHOW_MODES_FORMAT, "modes": modes}), encoding="utf-8")

    def test_superscript_digit_in_file_does_not_crash_the_store(self):
        self._write({"mc": {"name": "MC", "steps": [
            {"parameter": "fader", "channels": ["²"], "value": 5}]}})
        store = ShowModeStore(self.path)
        self.assertEqual(store.get("mc"), default_modes()["mc"])
        self.assertIn("mc", store.load_error)

    def test_file_cannot_swap_mode_ids_or_names(self):
        self._write({"mc": {"id": "band", "name": "BAND", "steps": FULL_MC}})
        store = ShowModeStore(self.path)
        self.assertEqual([(r["id"], r["name"]) for r in store.summaries()], [("mc", "MC"), ("band", "BAND")])

    def test_failed_write_keeps_memory_unchanged(self):
        store = ShowModeStore(self.path)
        with mock.patch("flow8.show_mode_store.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                store.save("mc", FULL_MC)
        self.assertEqual(store.get("mc"), default_modes()["mc"])


if __name__ == "__main__":
    unittest.main()
