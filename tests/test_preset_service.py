"""Unit tests for Flow8Service preset dispatch and level preservation."""

import unittest
from flow8.service import Flow8Service
from flow8.state_model import EventSource


class TestPresetServiceIntegration(unittest.TestCase):
    def setUp(self):
        self.service = Flow8Service(auto_connect=False)

    def test_apply_channel_preset_on_mic_channel(self):
        # Set baseline fader, pan, gain
        self.service.set_fader(1, 80)
        self.service.set_pan(1, 64)
        # S1.2 (D2): gain cannot be sent, so the baseline is written to the state store only (nothing is sent).
        self.service.state_store.set_commanded_value("ch1.gain", 24.0, EventSource.LOCAL_HOST, raw_midi_value=70)

        # Apply preset
        success = self.service.apply_channel_preset(1, "speech-mc-handheld", preserve_levels=True)
        self.assertTrue(success)

        # Verify level preservation: fader, pan, gain are UNTOUCHED
        ch1_fader = self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi
        self.assertEqual(ch1_fader, 80)
        ch1_pan = self.service.state_store.get_parameter("ch1.pan").commanded_raw_midi
        self.assertEqual(ch1_pan, 64)
        ch1_gain = self.service.state_store.get_parameter("ch1.gain").commanded_raw_midi
        self.assertEqual(ch1_gain, 70)  # the preset left gain exactly as it was

        # Verify DSP was applied
        eq_low = self.service.state_store.get_parameter("ch1.eq_low").commanded_value
        self.assertEqual(eq_low, -3.0)
        low_cut = self.service.state_store.get_parameter("ch1.low_cut").commanded_value
        self.assertEqual(low_cut, 120.0)
        comp = self.service.state_store.get_parameter("ch1.compressor").commanded_value
        self.assertEqual(comp, 30.0)

    def test_apply_channel_preset_on_stereo_channel(self):
        # Channel 5 (Line 5/6 stereo pair) has EQ, but no low cut or compressor
        success = self.service.apply_channel_preset(5, "acoustic-guitar-strum", preserve_levels=True)
        self.assertTrue(success)

        eq_low = self.service.state_store.get_parameter("ch5.eq_low").commanded_value
        self.assertEqual(eq_low, -3.5)

    def test_invalid_preset_or_channel(self):
        # Channel 8 is Main L/R bus, not an input channel strip
        self.assertFalse(self.service.apply_channel_preset(8, "speech-mc-handheld"))
        self.assertFalse(self.service.apply_channel_preset(1, "non-existent-preset"))

    def test_set_eq_and_sends_directly(self):
        self.service.set_eq_band(2, "hi", 3.0, unit="dB")
        val = self.service.state_store.get_parameter("ch2.eq_hi").commanded_value
        self.assertEqual(val, 3.0)

        self.service.set_send(1, "mon1", -6.0, unit="dB")
        send_val = self.service.state_store.get_parameter("ch1.send_mon1").commanded_value
        self.assertEqual(send_val, -6.0)

    def test_preset_undo_and_redo(self):
        # 1. Establish known baseline on Channel 1
        self.service.set_eq_band(1, "low", 0.0, unit="dB")
        self.service.set_eq_band(1, "low_mid", 0.0, unit="dB")
        self.service.set_eq_band(1, "hi_mid", 0.0, unit="dB")
        self.service.set_eq_band(1, "hi", 0.0, unit="dB")
        self.service.set_low_cut(1, 20.0, unit="Hz")
        self.service.set_compressor(1, 0.0, unit="%")
        self.service.set_fader(1, 95)
        self.service.set_pan(1, 64)
        # S1.2 (D2): baseline written to the state store only (nothing is sent).
        self.service.state_store.set_commanded_value("ch1.gain", 30.0, EventSource.LOCAL_HOST, raw_midi_value=79)

        # 2. Apply preset "speech-mc-handheld"
        self.service.apply_channel_preset(1, "speech-mc-handheld", preserve_levels=True)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_value, -3.0)
        self.assertEqual(self.service.state_store.get_parameter("ch1.compressor").commanded_value, 30.0)

        # 3. Undo preset application
        undone = self.service.undo()
        self.assertGreater(len(undone), 0)

        # 4. Verify restored state: EQ back to 0 dB, Comp back to 0%
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 64)
        self.assertEqual(self.service.state_store.get_parameter("ch1.compressor").commanded_raw_midi, 0)
        # Fader, Pan, Gain still completely untouched
        self.assertEqual(self.service.state_store.get_parameter("ch1.fader").commanded_raw_midi, 95)
        self.assertEqual(self.service.state_store.get_parameter("ch1.pan").commanded_raw_midi, 64)

        # 5. Redo preset application
        redone = self.service.redo()
        self.assertGreater(len(redone), 0)
        self.assertEqual(self.service.state_store.get_parameter("ch1.eq_low").commanded_raw_midi, 51)
        self.assertEqual(self.service.state_store.get_parameter("ch1.compressor").commanded_raw_midi, 30)

    def test_audit_requested_presets_parameter_validity(self):
        """Audit all presets requested by the critical audit."""
        audit_presets = [
            "speech-mc-handheld",
            "vocal-male-lead",
            "vocal-female-lead",
            "vocal-worship-ballad",
            "acoustic-guitar-strum",
            "bass-guitar-di",
            "electric-guitar-clean",
        ]
        for pid in audit_presets:
            preset = self.service.get_channel_preset(pid)
            self.assertIsNotNone(preset, f"Preset {pid} must exist in catalog")
            self.assertTrue(preset.preserve_levels, f"Preset {pid} must enforce preserve_levels")
            # Apply to Ch 1
            success = self.service.apply_channel_preset(1, pid, preserve_levels=True)
            self.assertTrue(success, f"Applying {pid} to channel 1 failed")
            # Verify EQ parameters within valid range
            self.assertGreaterEqual(preset.eq_low_db, -15.0)
            self.assertLessEqual(preset.eq_low_db, 15.0)
            self.assertGreaterEqual(preset.eq_hi_db, -15.0)
            self.assertLessEqual(preset.eq_hi_db, 15.0)


if __name__ == "__main__":
    unittest.main()
