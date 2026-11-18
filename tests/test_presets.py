"""Unit tests for FLOW 8 Curated Audio Presets (adapted from CueAir)."""

import unittest
from flow8.presets import (
    CHANNEL_PRESETS,
    FX_PRESETS,
    ChannelPreset,
    FxPreset,
    list_channel_presets,
    get_channel_preset,
    list_fx_presets,
    get_fx_preset,
)


class TestPresetsCatalog(unittest.TestCase):
    def test_presets_exist_and_non_empty(self):
        self.assertGreater(len(CHANNEL_PRESETS), 8)
        self.assertGreater(len(FX_PRESETS), 3)

    def test_all_presets_have_level_preservation(self):
        for pid, preset in CHANNEL_PRESETS.items():
            self.assertTrue(
                preset.preserve_levels,
                f"Preset {pid} must guarantee level preservation to prevent audio spikes."
            )

    def test_eq_values_within_bounds(self):
        for pid, preset in CHANNEL_PRESETS.items():
            for eq_val in (preset.eq_low_db, preset.eq_low_mid_db, preset.eq_hi_mid_db, preset.eq_hi_db):
                self.assertGreaterEqual(eq_val, -15.0, f"Preset {pid} EQ below -15 dB")
                self.assertLessEqual(eq_val, 15.0, f"Preset {pid} EQ above +15 dB")

    def test_low_cut_values_within_bounds(self):
        for pid, preset in CHANNEL_PRESETS.items():
            if preset.low_cut_hz is not None:
                self.assertGreaterEqual(preset.low_cut_hz, 20.0, f"Preset {pid} low cut below 20 Hz")
                self.assertLessEqual(preset.low_cut_hz, 600.0, f"Preset {pid} low cut above 600 Hz")

    def test_compressor_values_within_bounds(self):
        for pid, preset in CHANNEL_PRESETS.items():
            if preset.compressor_percent is not None:
                self.assertGreaterEqual(preset.compressor_percent, 0.0, f"Preset {pid} comp below 0%")
                self.assertLessEqual(preset.compressor_percent, 100.0, f"Preset {pid} comp above 100%")

    def test_category_filtering(self):
        all_presets = list_channel_presets("all")
        self.assertEqual(len(all_presets), len(CHANNEL_PRESETS))

        speech_presets = list_channel_presets("speech")
        self.assertTrue(len(speech_presets) >= 2)
        for p in speech_presets:
            self.assertEqual(p.category.lower(), "speech")

        vocal_presets = list_channel_presets("vocal")
        self.assertTrue(len(vocal_presets) >= 2)
        for p in vocal_presets:
            self.assertEqual(p.category.lower(), "vocal")

    def test_get_preset_by_id(self):
        mc = get_channel_preset("speech-mc-handheld")
        self.assertIsNotNone(mc)
        self.assertEqual(mc.name, "MC Wireless Handheld")

        non_existent = get_channel_preset("unknown-preset-xyz")
        self.assertIsNone(non_existent)

    def test_fx_presets(self):
        plate = get_fx_preset("fx1-plate-vocal")
        self.assertIsNotNone(plate)
        self.assertEqual(plate.target_slot, 1)
        self.assertEqual(plate.group, "Reverb")


if __name__ == "__main__":
    unittest.main()
