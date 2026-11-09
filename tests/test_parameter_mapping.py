"""
Unit tests for FLOW 8 Parameter Mapping.
Validates boundaries, curve behaviors, center points, and conversions.
"""

import unittest
import math
from flow8.parameter_mapping import (
    mute_bool_to_midi,
    mute_midi_to_bool,
    pan_percent_to_midi,
    pan_midi_to_percent,
    fader_midi_to_db,
    fader_db_to_midi,
)

class TestParameterMapping(unittest.TestCase):

    # -----------------------------------------------------------------------
    # Mute Mapping Tests (VERIFIED)
    # -----------------------------------------------------------------------
    def test_mute_bool_to_midi(self):
        self.assertEqual(mute_bool_to_midi(True), 127)
        self.assertEqual(mute_bool_to_midi(False), 0)

    def test_mute_midi_to_bool(self):
        self.assertFalse(mute_midi_to_bool(0))
        self.assertTrue(mute_midi_to_bool(127))
        self.assertTrue(mute_midi_to_bool(1))
        self.assertTrue(mute_midi_to_bool(64))

    def test_mute_out_of_bounds(self):
        with self.assertRaises(ValueError):
            mute_midi_to_bool(-1)
        with self.assertRaises(ValueError):
            mute_midi_to_bool(128)

    # -----------------------------------------------------------------------
    # Pan Mapping Tests (VERIFIED)
    # -----------------------------------------------------------------------
    def test_pan_center(self):
        self.assertEqual(pan_percent_to_midi(0.0), 64)
        self.assertEqual(pan_midi_to_percent(64), 0.0)

    def test_pan_extremes(self):
        self.assertEqual(pan_percent_to_midi(-100.0), 0)
        self.assertEqual(pan_midi_to_percent(0), -100.0)
        self.assertEqual(pan_percent_to_midi(100.0), 127)
        self.assertEqual(pan_midi_to_percent(127), 100.0)

    def test_pan_clamping(self):
        # Exceeding +/- 100% should clamp safely
        self.assertEqual(pan_percent_to_midi(-150.0), 0)
        self.assertEqual(pan_percent_to_midi(150.0), 127)

    def test_pan_out_of_bounds_midi(self):
        with self.assertRaises(ValueError):
            pan_midi_to_percent(-1)
        with self.assertRaises(ValueError):
            pan_midi_to_percent(128)

    def test_pan_monotonicity(self):
        prev_pct = -101.0
        for midi_val in range(128):
            pct = pan_midi_to_percent(midi_val)
            self.assertGreater(pct, prev_pct)
            prev_pct = pct

    # -----------------------------------------------------------------------
    # Fader Mapping Tests (UNVERIFIED APPROXIMATION)
    # -----------------------------------------------------------------------
    def test_fader_off_handling(self):
        self.assertEqual(fader_midi_to_db(0), float('-inf'))
        self.assertEqual(fader_db_to_midi(float('-inf')), 0)
        self.assertEqual(fader_db_to_midi(-100.0), 0)
        self.assertEqual(fader_db_to_midi(-75.0), 0)

    def test_fader_cardinal_points(self):
        # Value 1 = -70.0 dB
        self.assertEqual(fader_midi_to_db(1), -70.0)
        self.assertEqual(fader_db_to_midi(-70.0), 1)

        # Value 101 = Unity (0.0 dB)
        self.assertEqual(fader_midi_to_db(101), 0.0)
        self.assertEqual(fader_db_to_midi(0.0), 101)

        # Value 127 = Max (+10.0 dB)
        self.assertEqual(fader_midi_to_db(127), 10.0)
        self.assertEqual(fader_db_to_midi(10.0), 127)

    def test_fader_clamping(self):
        self.assertEqual(fader_db_to_midi(20.0), 127)
        self.assertEqual(fader_db_to_midi(-200.0), 0)

    def test_fader_out_of_bounds_midi(self):
        with self.assertRaises(ValueError):
            fader_midi_to_db(-1)
        with self.assertRaises(ValueError):
            fader_midi_to_db(128)

    def test_fader_monotonicity(self):
        prev_db = -100.0
        for midi_val in range(1, 128):
            db = fader_midi_to_db(midi_val)
            self.assertGreater(db, prev_db)
            prev_db = db

if __name__ == '__main__':
    unittest.main()
