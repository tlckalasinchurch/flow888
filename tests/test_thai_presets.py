"""Clean-room Thai preset catalog: content, scope rules and plan integration."""

from __future__ import annotations

import json
import unittest
import urllib.request

from flow8.change_plan import make_plan
from flow8.lan_hub import Flow8LanHub
from flow8.parameter_mapping import (
    compressor_percent_to_midi,
    eq_db_to_midi,
    low_cut_hz_to_midi,
)
from flow8.presets_th import (
    CATALOG_ID,
    CATEGORIES,
    THAI_PRESETS,
    get_thai_preset,
    list_thai_presets,
)
from flow8.service import Flow8Service

THAI = "\u0e00-\u0e7f"


def has_thai(text: str) -> bool:
    return any("\u0e00" <= ch <= "\u0e7f" for ch in str(text))


class CatalogTests(unittest.TestCase):
    def test_catalog_is_original_thai_content(self):
        self.assertGreaterEqual(len(THAI_PRESETS), 10)
        self.assertTrue(CATALOG_ID.startswith("thai-clean-room"))
        for preset in list_thai_presets():
            with self.subTest(preset=preset.id):
                self.assertTrue(preset.id.startswith("th-"))
                self.assertTrue(has_thai(preset.name), preset.name)
                self.assertTrue(has_thai(preset.summary), preset.summary)
                self.assertTrue(preset.why and all(has_thai(line) for line in preset.why))
                self.assertIn(preset.category, CATEGORIES)

    def test_safe_tonal_ranges(self):
        for preset in list_thai_presets():
            with self.subTest(preset=preset.id):
                for band, db in preset.eq_db.items():
                    self.assertGreaterEqual(db, -6.0, f"{preset.id} {band}")
                    self.assertLessEqual(db, 6.0, f"{preset.id} {band}")
                if preset.low_cut_hz is not None:
                    self.assertGreaterEqual(preset.low_cut_hz, 20.0)
                    self.assertLessEqual(preset.low_cut_hz, 600.0)
                if preset.compressor_percent is not None:
                    self.assertGreaterEqual(preset.compressor_percent, 0.0)
                    self.assertLessEqual(preset.compressor_percent, 100.0)

    def test_reset_preset_returns_the_channel_to_flat(self):
        preset = get_thai_preset("th-flat-reset")
        self.assertIsNotNone(preset)
        self.assertEqual(set(preset.eq_raw.values()), {64})
        self.assertEqual(preset.low_cut_raw, 0)      # raw 0 = no low cut
        self.assertEqual(preset.compressor_raw, 0)


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.preset = get_thai_preset("th-pa-mc")
        self.assertIsNotNone(self.preset)

    def test_mic_channel_gets_eq_low_cut_and_compressor(self):
        changes = self.preset.changes(1)
        params = [c["parameter"] for c in changes]
        self.assertEqual(params, [
            "eq_low", "eq_low_mid", "eq_hi_mid", "eq_hi", "low_cut", "compressor",
        ])
        self.assertEqual(changes[4]["value"], low_cut_hz_to_midi(110.0))
        self.assertEqual(changes[5]["value"], compressor_percent_to_midi(25.0))

    def test_line_channel_only_gets_eq(self):
        changes = self.preset.changes(5)
        self.assertEqual([c["parameter"] for c in changes],
                         ["eq_low", "eq_low_mid", "eq_hi_mid", "eq_hi"])

    def test_scope_toggles_select_sections(self):
        params = [c["parameter"] for c in self.preset.changes(1, scopes=["compressor"])]
        self.assertEqual(params, ["compressor"])
        params = [c["parameter"] for c in self.preset.changes(1, scopes=["eq", "low_cut"])]
        self.assertNotIn("compressor", params)
        with self.assertRaises(ValueError):
            self.preset.changes(1, scopes=["gain"])
        with self.assertRaises(ValueError):
            self.preset.changes(8)

    def test_no_preset_ever_proposes_gain_or_phantom(self):
        for preset in list_thai_presets():
            for channel in range(1, 8):
                with self.subTest(preset=preset.id, channel=channel):
                    params = [c["parameter"] for c in preset.changes(channel)]
                    self.assertNotIn("gain", params)
                    self.assertNotIn("phantom", params)

    def test_every_plan_is_accepted_by_the_change_plan_validator(self):
        for preset in list_thai_presets():
            for channel in (1, 4, 7):
                with self.subTest(preset=preset.id, channel=channel):
                    plan = make_plan(preset.name, preset.changes(channel))
                    self.assertEqual(len(plan.changes), len(preset.changes(channel)))


class PresetPlanIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def test_commit_preset_as_one_undo_step(self):
        preset = get_thai_preset("th-vocal-female")
        for band in ("low", "low_mid", "hi_mid", "hi"):
            self.service.set_eq_band(1, band, 64, unit="raw")   # known 0 dB on every band
        self.service.set_low_cut(1, 0, unit="raw")      # raw 0 differs from the preset's 20
        self.service.set_compressor(1, 0, unit="raw")
        self.service.ledger.clear()

        plan = make_plan(preset.name, preset.changes(1))
        result = self.service.commit_change_plan(plan)
        self.assertEqual(result.applied, 6)
        self.assertFalse(result.rolled_back)

        state = self.service.state_store
        for band, raw in preset.eq_raw.items():
            self.assertEqual(state.get_parameter(f"ch1.eq_{band}").commanded_raw_midi, raw, band)
        self.assertEqual(state.get_parameter("ch1.low_cut").commanded_raw_midi, preset.low_cut_raw)
        self.assertEqual(state.get_parameter("ch1.compressor").commanded_raw_midi, preset.compressor_raw)

        undone = self.service.undo()
        self.assertEqual(len(undone), 6, "a preset must undo as one step")
        self.assertEqual(state.get_parameter("ch1.eq_low").commanded_raw_midi, 64)
        self.assertEqual(state.get_parameter("ch1.low_cut").commanded_raw_midi, 0)
        self.assertEqual(state.get_parameter("ch1.compressor").commanded_raw_midi, 0)
        self.assertFalse(self.service.ledger.can_undo)

    def test_preset_leaves_fader_pan_mute_and_sends_alone(self):
        preset = get_thai_preset("th-acoustic-di")
        self.service.set_fader(2, 77)
        self.service.set_pan(2, 50)
        self.service.set_send(2, "fx1", 40)
        self.service.ledger.clear()
        plan = make_plan(preset.name, preset.changes(2))
        params = {c.parameter for c in plan.changes}
        self.assertFalse(params & {"fader", "pan", "mute", "send_fx1"})
        self.service.commit_change_plan(plan)
        state = self.service.state_store
        self.assertEqual(state.get_parameter("ch2.fader").commanded_raw_midi, 77)
        self.assertEqual(state.get_parameter("ch2.pan").commanded_raw_midi, 50)
        self.assertEqual(state.get_parameter("ch2.send_fx1").commanded_raw_midi, 40)


class PresetApiTests(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_api_exposes_exact_raw_values_and_categories(self):
        body = self.get("/api/presets/thai")
        self.assertEqual(body["catalog"], CATALOG_ID)
        self.assertEqual(body["categories"], list(CATEGORIES))
        self.assertEqual(len(body["presets"]), len(THAI_PRESETS))
        mc = next(p for p in body["presets"] if p["id"] == "th-pa-mc")
        preset = get_thai_preset("th-pa-mc")
        self.assertEqual(mc["eqRaw"], {band: eq_db_to_midi(db) for band, db in preset.eq_db.items()})
        self.assertEqual(mc["lowCutRaw"], low_cut_hz_to_midi(110.0))
        self.assertEqual(mc["compressorRaw"], compressor_percent_to_midi(25.0))
        self.assertTrue(has_thai(mc["name"]))

    def test_legacy_endpoint_still_answers(self):
        body = self.get("/api/presets")
        self.assertTrue(body["presets"], "the original adapted catalog stays available")


if __name__ == "__main__":
    unittest.main()
