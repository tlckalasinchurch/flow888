"""15 snapshot slots, recall scope (WHAT TO LOAD) and the named snapshot library."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.service import SCENE_CAPACITY, Flow8Service, recall_scope_of
from flow8.snapshot_library import LIBRARY_FORMAT, SnapshotLibrary, normalise_parameters


class ScopeTests(unittest.TestCase):
    def test_scope_of_each_value(self):
        self.assertEqual(recall_scope_of(1, "fader"), "CH")
        self.assertEqual(recall_scope_of(3, "eq_hi"), "CH")
        self.assertEqual(recall_scope_of(2, "send_mon1"), "MON")
        self.assertEqual(recall_scope_of("mon2", "fader"), "MON")
        self.assertEqual(recall_scope_of(4, "send_fx2"), "FX")
        self.assertEqual(recall_scope_of("fx1", "fader"), "FX")
        self.assertEqual(recall_scope_of(8, "fader"), "MAIN")
        self.assertEqual(SCENE_CAPACITY, 15)


class LibraryValidationTests(unittest.TestCase):
    def test_gain_phantom_and_bad_values_are_refused(self):
        for bad in ({"1": {"gain": 10}}, {"1": {"phantom": True}}, {"1": {"fader": 128}},
                    {"1": {"fader": True}}, {"1": {"mute": 1}}, {"9": {"fader": 1}},
                    {"mon1": {"pan": 64}}, {"8": {"mute": True}}):
            with self.assertRaises(ValueError, msg=bad):
                normalise_parameters(bad)
        self.assertEqual(normalise_parameters({"1": {"fader": 90, "mute": False}, "fx2": {"fader": 3}}),
                         {1: {"fader": 90, "mute": False}, "fx2": {"fader": 3}})

    def test_file_round_trip_and_damaged_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "lib.json"
            lib = SnapshotLibrary(path)
            entry = lib.save("  Vocal   A ", {1: {"fader": 80}})
            self.assertEqual(entry["name"], "Vocal A")
            again = SnapshotLibrary(path)
            self.assertEqual([s["name"] for s in again.summaries()], ["Vocal A"])
            self.assertEqual(again.parameters(entry["id"]), {1: {"fader": 80}})
            path.write_text("{not json", encoding="utf-8")
            broken = SnapshotLibrary(path)
            self.assertEqual(broken.summaries(), [])
            self.assertIn("not loaded", broken.load_error)

    def test_import_skips_invalid_entries(self):
        lib = SnapshotLibrary()
        res = lib.import_data({"format": LIBRARY_FORMAT, "snapshots": [
            {"name": "ok", "parameters": {"2": {"pan": 10}}},
            {"name": "bad", "parameters": {"1": {"phantom": True}}},
            {"name": "", "parameters": {"1": {"fader": 1}}},
        ]})
        self.assertEqual((res["added"], res["skipped"]), (1, 2))
        with self.assertRaises(ValueError):
            lib.import_data({"format": "other", "snapshots": []})


class HubSnapshotTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0, library_path=Path(self.tmp.name) / "lib.json")
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def post(self, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/action",
                                     data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as err:
            try:
                return err.code, json.loads(err.read() or b"{}")
            finally:
                err.close()

    def get(self, path: str):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as r:
            return r.headers, json.loads(r.read())

    def raw(self, pid: str):
        return self.service.state_store.get_parameter(pid).commanded_raw_midi

    def test_slot_15_and_scope_filtered_recall(self):
        for p in ({"action": "setFader", "channel": 1, "value": 50}, {"action": "setSend", "channel": 1, "target": "mon1", "value": 40},
                  {"action": "setBusFader", "bus": "fx1", "value": 30}, {"action": "setFader", "channel": 8, "value": 100}):
            self.assertEqual(self.post(p)[0], 200)
        self.assertEqual(self.post({"action": "captureScene", "name": "SCENE 15"})[0], 200)
        for p in ({"action": "setFader", "channel": 1, "value": 1}, {"action": "setSend", "channel": 1, "target": "mon1", "value": 2},
                  {"action": "setBusFader", "bus": "fx1", "value": 3}, {"action": "setFader", "channel": 8, "value": 4}):
            self.post(p)
        code, body = self.post({"action": "recallScene", "name": "SCENE 15", "scope": ["MON", "FX"]})
        self.assertEqual((code, body["applied"]), (200, 2))
        self.assertEqual((self.raw("ch1.send_mon1"), self.raw("fx1.fader")), (40, 30))
        self.assertEqual((self.raw("ch1.fader"), self.raw("main.fader")), (1, 4))
        _, snap = self.get("/api/session")
        self.assertEqual((snap["currentScene"], snap["sceneEdited"], snap["sceneSlots"]), ("SCENE 15", True, 15))
        self.assertEqual(snap["sceneInfo"][0]["scopes"], {"CH": 1, "FX": 1, "MAIN": 1, "MON": 1})
        self.assertEqual(self.post({"action": "recallScene", "name": "SCENE 15", "scope": ["ROUT"]})[0], 400)
        self.post({"action": "recallScene", "name": "SCENE 15"})
        self.assertEqual(self.raw("ch1.fader"), 50)
        self.assertFalse(self.get("/api/session")[1]["sceneEdited"])

    def test_library_save_load_rename_delete_export_import(self):
        self.post({"action": "setFader", "channel": 2, "value": 77})
        code, body = self.post({"action": "librarySave", "name": "Pastor"})
        self.assertEqual(code, 200)
        entry_id = body["id"]
        self.post({"action": "setFader", "channel": 2, "value": 5})
        code, body = self.post({"action": "libraryLoad", "id": entry_id, "scope": ["CH"]})
        self.assertEqual((code, body["applied"]), (200, 1))
        self.assertEqual(self.raw("ch2.fader"), 77)
        self.assertEqual(self.post({"action": "libraryRename", "id": entry_id, "name": "Pastor 2"})[0], 200)
        headers, exported = self.get("/api/library/export")
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(exported["snapshots"][0]["name"], "Pastor 2")
        self.assertEqual(self.post({"action": "libraryDelete", "id": entry_id})[0], 200)
        code, body = self.post({"action": "libraryImport", "data": exported})
        self.assertEqual((code, body["added"]), (200, 1))
        _, snap = self.get("/api/session")
        self.assertEqual([e["name"] for e in snap["library"]], ["Pastor 2"])
        self.assertTrue((Path(self.tmp.name) / "lib.json").exists())

    def test_library_edits_work_offline_but_load_does_not(self):
        self.post({"action": "setFader", "channel": 2, "value": 77})
        _, body = self.post({"action": "librarySave", "name": "A"})
        with mock.patch.object(Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=False):
            self.assertEqual(self.post({"action": "libraryRename", "id": body["id"], "name": "B"})[0], 200)
            self.assertEqual(self.post({"action": "libraryLoad", "id": body["id"]})[0], 503)

    def test_large_body_refused(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/action", data=b"x" * 1_000_001, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 413)
        ctx.exception.close()


if __name__ == "__main__":
    unittest.main()
