"""S1.2 safety tests: message types, reset, and the low-level pairs (M-xx).

No physical port is opened; byte-level checks use a MagicMock driver.

2026-11-20 (owner approval): the bus limiter / 9-band GEQ (MAIN, MON1, MON2), FX engine
parameters 1-2 and FX preset select joined the allowlist. FX preset select is the only
Program Change allowed: presets 1-16 on channels 13 and 14. Channel 16 stays closed.
"""
import ast
import unittest
from pathlib import Path

from flow8.command_boundary import Flow8CommandBoundary, Flow8CommandRejectedError
from flow8.midi_out import Flow8MidiOut, Flow8ValidationError, Flow8NotConnectedError
from flow8.service import Flow8Service

from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import dword, fake_open_port

ROOT = Path(__file__).resolve().parent.parent
ALLOW = Flow8CommandBoundary.ACTIVE_ALLOWLIST
CC_ALLOW = {pid: s for pid, s in ALLOW.items() if s.get("message") is None}
PC_ALLOW = {pid: s for pid, s in ALLOW.items() if s.get("message") == "program_change"}
ALLOW_PAIRS = {(s["channel"], s["cc"]) for s in CC_ALLOW.values()}
GAIN_PAIRS = {(s["channel"], s["cc"]) for s in CC_ALLOW.values() if s["type"] == "gain"}
PHANTOM_PAIRS = {(s["channel"], s["cc"]) for pid, s in CC_ALLOW.items() if pid.endswith(".phantom")}

# Pairs accepted by send_cc before S1.2 but never authorised by the boundary (S1.1 dry-run), written out.
# Solo stays refused. The 30 bus limiter/GEQ pairs were opened by the owner on 2026-11-20.
SOLO = {(ch, 6) for ch in range(1, 8)}
BUS = {(ch, cc) for ch in (8, 9, 10) for cc in (8, 11, 12, 13, 14, 15, 16, 17, 18, 19)}
FX_ENGINE = {(ch, cc) for ch in (13, 14) for cc in (1, 2)}


def accepted_pairs(value):
    """(channel, CC) pairs that pass send_cc validation on an unopened port (it then stops at 'not connected')."""
    out = Flow8MidiOut()
    assert not out.is_connected
    accepted = set()
    for ch in range(1, 17):
        for cc in range(128):
            try:
                out.send_cc(ch, cc, value)
            except Flow8ValidationError:
                pass
            except Flow8NotConnectedError:
                accepted.add((ch, cc))
    return accepted


class MessageTypeTests(NoHardwareMixin, unittest.TestCase):
    def test_m01_exhaustive_validator(self):
        from flow8.safety import validate_outbound, SafetyPolicyError
        blocked = GAIN_PAIRS
        for status in range(0x80, 0x100):
            for d1 in range(128):
                for d2 in (0, 1, 15, 16, 17, 64, 127):
                    try:
                        validate_outbound(status, d1, d2)
                        ok = True
                    except SafetyPolicyError:
                        ok = False
                    if ok and status & 0xF0 == 0xC0:
                        # The one Program Change exception: FX presets 1-16 on channels 13 / 14.
                        self.assertIn((status & 0x0F) + 1, (13, 14), hex(status))
                        self.assertTrue(1 <= d1 <= 16 and d2 == 0, (hex(status), d1, d2))
                        continue
                    if ok:
                        self.assertEqual(status & 0xF0, 0xB0, hex(status))
                        pair = ((status & 0x0F) + 1, d1)
                        self.assertIn(pair, ALLOW_PAIRS)
                        self.assertNotIn(pair, blocked)
                        self.assertFalse(pair in PHANTOM_PAIRS and d2 > 0, "phantom ON without permit")
        for bad in (-1, 0x7F, 0x100, 0x1B0):
            with self.assertRaises(SafetyPolicyError):
                validate_outbound(bad, 7, 64)
        with self.assertRaises(SafetyPolicyError):
            validate_outbound(0xB0, 128, 0)
        with self.assertRaises(SafetyPolicyError):
            validate_outbound(0xB0, 7, 128)

    def test_m02_send_cc_accepted_set_equals_policy(self):
        self.assertEqual(accepted_pairs(0), ALLOW_PAIRS - GAIN_PAIRS)
        self.assertEqual(accepted_pairs(127), ALLOW_PAIRS - GAIN_PAIRS - PHANTOM_PAIRS)
        self.assertEqual((len(ALLOW_PAIRS), len(ALLOW_PAIRS - GAIN_PAIRS)), (131, 127))

    def test_m03_solo_is_refused_and_bus_dsp_is_open(self):
        from flow8.safety import validate_outbound, SafetyPolicyError
        self.assertEqual(len(SOLO), 7)
        self.assertFalse(SOLO & ALLOW_PAIRS)
        self.assertEqual(BUS & ALLOW_PAIRS, BUS)          # opened 2026-11-20
        self.assertEqual(FX_ENGINE & ALLOW_PAIRS, FX_ENGINE)
        out, driver = fake_open_port()
        for ch, cc in sorted(SOLO):
            with self.subTest(ch=ch, cc=cc):
                with self.assertRaises(Flow8ValidationError):
                    out.send_cc(ch, cc, 64)
                with self.assertRaises(SafetyPolicyError) as ctx:
                    validate_outbound(0xB0 | (ch - 1), cc, 64)
                self.assertTrue(getattr(ctx.exception, "rule", ""))
        driver.midiOutShortMsg.assert_not_called()
        boundary = Flow8CommandBoundary(out, Flow8Service(auto_connect=False).state_store)
        for pid in ("ch1.solo", "ch7.solo", "fx1.limiter", "fx2.geq1", "fxe1.mute", "global.fx_mute"):
            with self.assertRaises(Flow8CommandRejectedError):
                boundary.execute_command(pid, 64)
        driver.midiOutShortMsg.assert_not_called()

    def test_m04_only_control_change_leaves_the_app(self):
        out, driver = fake_open_port()
        for ch, cc in sorted(ALLOW_PAIRS - GAIN_PAIRS - PHANTOM_PAIRS):
            for v in (0, 64, 127):
                out.send_cc(ch, cc, v)
        for call in driver.midiOutShortMsg.call_args_list:
            msg = call.args[1]
            self.assertEqual(msg & 0xF0, 0xB0)
            self.assertLess((msg >> 8) & 0xFF, 128)
            self.assertLess((msg >> 16) & 0xFF, 128)
            self.assertEqual(msg >> 24, 0)

    def test_m05_no_program_change_note_or_sysex_api(self):
        import inspect
        from flow8.parameter_engine import Flow8ParameterEngine
        for cls in (Flow8MidiOut, Flow8CommandBoundary, Flow8ParameterEngine, Flow8Service):
            for name, fn in inspect.getmembers(cls, inspect.isfunction):
                if name.startswith("_"):
                    continue
                self.assertNotIn("status", inspect.signature(fn).parameters, f"{cls.__name__}.{name}")
        offenders = []
        for path in (ROOT / "flow8").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} |                    {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            if used & {"midiOutShortMsg", "midiOutLongMsg"} and path.name != "midi_out.py":
                offenders.append(path.name)
        self.assertEqual(offenders, [])
        # No outbound module builds a Program Change, Note or system status byte, except the single
        # FX preset sender Flow8MidiOut.send_program_change (0xC0, validated by validate_outbound).
        # (service.py is excluded: its inbound handler legitimately masks with 0xF0; it sends only through the boundary.)
        for rel in ("flow8/midi_out.py", "flow8/command_boundary.py", "flow8/parameter_engine.py"):
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
            sanctioned = {
                id(n)
                for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and fn.name == "send_program_change"
                for n in ast.walk(fn) if isinstance(n, ast.Constant) and n.value == 0xC0
            }
            if rel == "flow8/midi_out.py":
                self.assertEqual(len(sanctioned), 1, "exactly one Program Change status literal")
            for node in ast.walk(tree):
                if id(node) in sanctioned:
                    continue
                if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
                    self.assertFalse(0x80 <= node.value <= 0xAF or 0xC0 <= node.value <= 0xEF or 0xF0 <= node.value <= 0xFE,
                                     f"{rel}: status-like literal {hex(node.value)}")

    def test_m06_reset_cannot_be_constructed_or_sent(self):
        from flow8.safety import validate_outbound, SafetyPolicyError
        out, driver = fake_open_port()
        for status in (0xCF, 0xCE, 0xC0):
            for d1 in (15, 16, 17, 0):
                with self.assertRaises(SafetyPolicyError):
                    validate_outbound(status, d1, 0)
        with self.assertRaises(SafetyPolicyError) as ctx:
            validate_outbound(0xCF, 16, 0)
        self.assertEqual(ctx.exception.rule, "SR-02")
        for cc in range(128):
            for v in (0, 1, 127):
                with self.assertRaises(Flow8ValidationError):
                    out.send_cc(16, cc, v)
        driver.midiOutShortMsg.assert_not_called()

    def test_m07_every_permitted_parameter_still_dispatches_the_same_bytes(self):
        out, driver = fake_open_port()
        service = Flow8Service(auto_connect=False)
        service.midi_out = out
        boundary = Flow8CommandBoundary(out, service.state_store)
        for pid, spec in sorted(CC_ALLOW.items()):
            if spec["type"] == "gain" or pid.endswith(".phantom"):
                continue
            for raw in (0, 64, 127):
                value = bool(raw) if spec.get("boolean") else raw
                driver.midiOutShortMsg.reset_mock()
                boundary.execute_command(pid, value)
                expected = 127 if spec.get("boolean") and value else (0 if spec.get("boolean") else raw)
                driver.midiOutShortMsg.assert_called_once_with(
                    out._handle, dword(spec["channel"], spec["cc"], expected))

    def test_m08_allowlist_unchanged(self):
        # 97 (S1.2) + 3 limiters + 27 GEQ bands + 4 FX engine parameters + 2 FX preset selects.
        self.assertEqual(len(ALLOW), 133)
        self.assertEqual(len(ALLOW_PAIRS), 131)
        self.assertEqual(sorted(PC_ALLOW), ["fxe1.preset", "fxe2.preset"])

    def test_m09_fx_preset_program_change_bytes_and_limits(self):
        out, driver = fake_open_port()
        service = Flow8Service(auto_connect=False)
        boundary = Flow8CommandBoundary(out, service.state_store)
        for pid, ch in (("fxe1.preset", 13), ("fxe2.preset", 14)):
            for preset in (1, 9, 16):
                driver.midiOutShortMsg.reset_mock()
                boundary.execute_command(pid, preset)
                driver.midiOutShortMsg.assert_called_once_with(out._handle, (0xC0 | (ch - 1)) | (preset << 8))
            for bad in (0, 17, 127):
                with self.assertRaises(Flow8ValidationError):
                    boundary.execute_command(pid, bad)
        # The low-level sender refuses every Program Change outside the exception, reset included.
        driver.midiOutShortMsg.reset_mock()
        for ch, program in ((16, 16), (16, 1), (15, 1), (1, 1), (12, 1), (13, 0), (14, 17)):
            with self.assertRaises(Flow8ValidationError):
                out.send_program_change(ch, program)
        driver.midiOutShortMsg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
