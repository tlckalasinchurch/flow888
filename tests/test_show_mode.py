"""Show Mode model: validation, safe-order compile, templates (no I/O, no hardware)."""

from __future__ import annotations

import unittest

from flow8.change_plan import make_plan
from flow8.show_mode import (
    ShowModeError,
    compile_mode,
    default_modes,
    unset_steps,
    validate_mode,
)


def _mode(steps, name="T"):
    return {"id": "t", "name": name, "steps": steps}


class TemplateTests(unittest.TestCase):
    def test_templates_validate_and_are_not_ready(self):
        modes = default_modes()
        self.assertEqual(set(modes), {"mc", "band"})
        for mode in modes.values():
            validate_mode(mode)
        self.assertEqual(unset_steps(modes["mc"]), [3, 4])
        self.assertEqual(unset_steps(modes["band"]), [0, 2])

    def test_compile_refuses_unset_steps(self):
        with self.assertRaises(ShowModeError):
            compile_mode(default_modes()["mc"])


class CompileTests(unittest.TestCase):
    def test_compile_order_cut_down_first(self):
        mode = _mode([
            {"parameter": "fader", "channels": [7], "value": 80},
            {"parameter": "mute", "channels": [1], "value": False},
            {"parameter": "mute", "channels": [2, 3], "value": True},
            {"parameter": "send_fx1", "channels": [1], "value": 0},
        ])
        order = [(c["parameter"], c["channel"]) for c in compile_mode(mode)]
        self.assertEqual(order, [
            ("mute", 2), ("mute", 3), ("send_fx1", 1), ("fader", 7), ("mute", 1),
        ])

    def test_compiled_changes_build_a_plan(self):
        mode = _mode([
            {"parameter": "mute", "channels": [2], "value": True},
            {"parameter": "fader", "channels": ["fx1"], "value": 40},
        ])
        plan = make_plan("MC", compile_mode(mode))
        self.assertEqual(len(plan.changes), 2)


class RefusalTests(unittest.TestCase):
    def test_refused_modes(self):
        ok = {"parameter": "fader", "channels": [1], "value": 50}
        cases = {
            "gain": [{"parameter": "gain", "channels": [1], "value": 10}],
            "phantom": [{"parameter": "phantom", "channels": [1], "value": True}],
            "eq": [{"parameter": "eq_hi", "channels": [1], "value": 64}],
            "main channel": [{"parameter": "fader", "channels": [8], "value": 50}],
            "mute on bus": [{"parameter": "mute", "channels": ["mon1"], "value": True}],
            "send on bus": [{"parameter": "send_fx1", "channels": ["fx1"], "value": 1}],
            "value 128": [{"parameter": "fader", "channels": [1], "value": 128}],
            "value -1": [{"parameter": "fader", "channels": [1], "value": -1}],
            "bool fader": [{"parameter": "fader", "channels": [1], "value": True}],
            "int mute": [{"parameter": "mute", "channels": [1], "value": 1}],
            "duplicate": [ok, dict(ok, value=60)],
            "33 steps": [{"parameter": p, "channels": [ch], "value": True if p == "mute" else 5}
                         for p in ("mute", "fader", "send_fx1", "send_fx2", "send_mon1")
                         for ch in range(1, 8)],
            "no channels": [{"parameter": "fader", "channels": [], "value": 50}],
        }
        for label, steps in cases.items():
            with self.subTest(label):
                with self.assertRaises(ShowModeError):
                    validate_mode(_mode(steps))

    def test_empty_name_is_refused(self):
        with self.assertRaises(ShowModeError):
            validate_mode(_mode([], name=" "))

    def test_bus_fader_is_allowed(self):
        validate_mode(_mode([{"parameter": "fader", "channels": ["mon1", "fx2"], "value": 0}]))


class NonAsciiDigitTests(unittest.TestCase):
    def test_superscript_digit_channel_is_refused_cleanly(self):
        with self.assertRaises(ShowModeError):
            validate_mode(_mode([{"parameter": "fader", "channels": ["²"], "value": 5}]))


if __name__ == "__main__":
    unittest.main()
