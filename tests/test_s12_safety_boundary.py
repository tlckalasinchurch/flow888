"""S1.2 safety tests: gain block (D2) and phantom authorization (D1) at every layer.

Spec: docs/product/S1_2_SAFETY_TEST_SPEC.md (B-xx, P-xx). A refusal is proven by a zero
driver-call count, never by a message alone. No physical port is ever opened.
"""
import ast
import re
import threading
import unittest
from pathlib import Path

from flow8.command_boundary import DispatchStatus, Flow8CommandRejectedError
from flow8.ledger import CommandLedger
from flow8.parameter_engine import Flow8ParameterEngine
from flow8.service import Flow8Service
from flow8.state_model import EventSource

from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import (
    EngineAdapter, PhantomPowerSafetyGate, authorize_phantom_on, dword, fake_open_port)

ROOT = Path(__file__).resolve().parent.parent
REFUSED = (Flow8CommandRejectedError,)


class Base(NoHardwareMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service = Flow8Service(auto_connect=False)
        self.out, self.driver = fake_open_port(self.service.midi_out)
        self.engine = self.service.parameter_engine
        self.boundary = self.service.command_boundary

    def sent(self):
        return [c.args[1] for c in self.driver.midiOutShortMsg.call_args_list]

    def phantom_on_sent(self):
        return [m for m in self.sent() if (m >> 8) & 0xFF == 12 and (m >> 16) & 0xFF > 0]

    def cc8_sent(self):
        return [m for m in self.sent() if (m >> 8) & 0xFF == 8]


class GainBlockTests(Base):
    def test_b01_boundary_refuses_gain(self):
        for ch in (1, 2, 3, 4):
            for value, unit in ((0, "raw"), (64, "raw"), (127, "raw"), (-20.0, "dB"), (0.0, "dB"), (60.0, "dB")):
                with self.subTest(ch=ch, value=value, unit=unit):
                    with self.assertRaises(REFUSED):
                        self.boundary.execute_command(f"ch{ch}.gain", value, unit=unit)
                    entry = self.boundary.command_log[-1]
                    self.assertEqual(entry.dispatch_status, DispatchStatus.REJECTED)
                    self.assertFalse(entry.command_accepted)
                    self.assertIsNone(entry.raw_midi_sent)
        self.driver.midiOutShortMsg.assert_not_called()
        self.assertIsNone(self.service.state_store.get_parameter("ch1.gain").commanded_raw_midi)

    def test_b02_service_refuses_gain(self):
        for ch in (1, 2, 3, 4):
            with self.subTest(ch=ch):
                with self.assertRaises(REFUSED):
                    self.service.set_gain(ch, 10, unit="raw")
        self.driver.midiOutShortMsg.assert_not_called()
        self.assertFalse(self.service.ledger.can_undo)
        self.assertIsNone(self.service.state_store.get_parameter("ch1.gain").commanded_raw_midi)

    def test_b03_engine_refuses_gain(self):
        for ch in (1, 2, 3, 4):
            with self.subTest(ch=ch):
                with self.assertRaises(REFUSED):
                    self.engine.channel(ch).set_gain(10, unit="raw")
        self.driver.midiOutShortMsg.assert_not_called()

    def test_b04_undo_and_redo_cannot_replay_gain(self):
        record = CommandLedger.make_record("gain", 1, 10, 20)
        self.assertFalse(self.service.ledger.push(record))   # never recorded
        # White-box: force a record into the stacks, as a corrupted ledger might hold.
        self.service.ledger._undo.append(record)
        with self.assertRaises(Exception):
            self.service.undo()
        self.service.ledger._redo.append(record)
        with self.assertRaises(Exception):
            self.service.redo()
        self.assertEqual(self.cc8_sent(), [])
        self.driver.midiOutShortMsg.assert_not_called()

    def test_b05_mixed_batch_never_emits_gain(self):
        self.service.set_fader(1, 40)
        ledger = self.service.ledger
        ledger.begin_batch()
        ledger.push(CommandLedger.make_record("fader", 1, 40, 80))
        ledger.push(CommandLedger.make_record("gain", 1, 10, 20))
        ledger.end_batch()
        self.driver.midiOutShortMsg.reset_mock()
        try:
            self.service.undo()
        except Exception:
            pass
        self.assertEqual(self.cc8_sent(), [])

    def test_b06_ledger_never_records_gain(self):
        ledger = CommandLedger()
        self.assertFalse(ledger.push(CommandLedger.make_record("gain", 1, 10, 20)))
        self.assertFalse(ledger.can_undo)

    def test_b07_no_override_exists(self):
        files = ["flow8/safety.py", "flow8/command_boundary.py", "flow8/midi_out.py", "flow8/service.py",
                 "flow8/ledger.py", "flow8/parameter_engine.py", "flow8/ui/safety_dialogs.py"]
        bad_words = re.compile(r"environ|getenv|^argv$|unlock|bypass|override|allow_gain|enable_gain", re.I)
        for rel in files:
            path = ROOT / rel
            self.assertTrue(path.exists(), rel)
            text = path.read_text(encoding="utf-8")
            code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
            tree = ast.parse(text)
            docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                          if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))
                          and n.body and isinstance(n.body[0], ast.Expr)
                          and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
            names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)] + \
                    [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)] + \
                    [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            for name in names:
                self.assertIsNone(bad_words.search(name), f"{rel}: suspicious identifier {name}")
        import flow8.safety as safety
        with self.assertRaises(TypeError):
            safety.BLOCKED_PARAMETER_TYPES["gain"] = "x"
        with self.assertRaises(TypeError):
            del safety.BLOCKED_PARAMETER_TYPES["gain"]
        from flow8.ui.safety_dialogs import AnalogGainSafetyGate
        self.assertFalse(AnalogGainSafetyGate.is_verified_mapping_available())

    def test_b08_gain_gate_sends_nothing(self):
        from flow8.ui.safety_dialogs import AnalogGainSafetyGate
        gate = AnalogGainSafetyGate(1, 0.0)
        gate.stage_preview(20.0)
        with self.assertRaises(RuntimeError):
            gate.commit_gain(self.service, confirmed=True)
        self.driver.midiOutShortMsg.assert_not_called()


class PhantomAuthorizationTests(Base):
    def test_p01_on_without_authorization_refused_everywhere(self):
        adapter_calls = (
            lambda ch: self.boundary.execute_command(f"ch{ch}.phantom", True),
            lambda ch: self.engine.channel(ch).set_phantom(True),
            lambda ch: self.service.set_phantom(ch, True),
            lambda ch: self.out.send_cc(ch, 12, 127),
        )
        for ch in (1, 2):
            for call in adapter_calls:
                with self.subTest(ch=ch):
                    with self.assertRaises(Exception) as ctx:
                        call(ch)
                    self.assertNotIsInstance(ctx.exception, AssertionError)
        self.driver.midiOutShortMsg.assert_not_called()
        self.assertIsNot(self.service.state_store.get_parameter("ch1.phantom").commanded_value, True)

    def test_p02_authorised_on_sends_exactly_once(self):
        authorize_phantom_on(self.service, 1)
        self.assertEqual(self.sent(), [dword(1, 12, 127)])
        self.assertIs(self.service.state_store.get_parameter("ch1.phantom").commanded_value, True)
        with self.assertRaises(Exception):
            self.service.set_phantom(1, True)          # the grant was single use
        self.assertEqual(self.sent(), [dword(1, 12, 127)])
        authorize_phantom_on(self.service, 2)
        self.assertEqual(self.sent()[-1], dword(2, 12, 127))

    def test_p03_token_abuse(self):
        gate = PhantomPowerSafetyGate
        token = gate.issue_token(1)
        self.assertFalse(gate.confirm_and_dispatch(self.service, 2, token))      # wrong channel
        self.assertFalse(gate.confirm_and_dispatch(self.service, 1, object()))   # forged
        self.assertFalse(gate.confirm_and_dispatch(self.service, 1, None))
        revoked = gate.issue_token(1)
        gate.revoke_token(revoked)
        self.assertFalse(gate.confirm_and_dispatch(self.service, 1, revoked))
        self.driver.midiOutShortMsg.assert_not_called()
        self.assertTrue(gate.confirm_and_dispatch(self.service, 1, token))       # valid once
        self.assertFalse(gate.confirm_and_dispatch(self.service, 1, token))      # consumed
        self.assertEqual(len(self.phantom_on_sent()), 1)

    def test_p04_off_needs_no_authorization(self):
        self.service.set_phantom(1, False)
        self.engine.channel(2).set_phantom(False)
        self.boundary.execute_command("ch1.phantom", False)
        self.assertEqual(self.sent(), [dword(1, 12, 0), dword(2, 12, 0), dword(1, 12, 0)])
        PhantomPowerSafetyGate.disable_and_dispatch(self.service, 1)
        self.assertEqual(self.sent()[-1], dword(1, 12, 0))

    def test_p05_grant_does_not_leak_after_an_error(self):
        class Boom:
            def set_phantom(self, ch, enabled):
                raise RuntimeError("boom")
        token = PhantomPowerSafetyGate.issue_token(1)
        with self.assertRaises(RuntimeError):
            PhantomPowerSafetyGate.confirm_and_dispatch(Boom(), 1, token)
        with self.assertRaises(Exception):
            self.service.set_phantom(1, True)
        self.assertEqual(self.phantom_on_sent(), [])

    def test_p06_grant_is_thread_bound(self):
        results = {}
        service = self.service

        class Adapter:
            def set_phantom(self_inner, ch, enabled):
                def other():
                    try:
                        service.set_phantom(ch, True)
                        results["thread"] = "accepted"
                    except Exception as error:
                        results["thread"] = type(error).__name__
                t = threading.Thread(target=other)
                t.start()
                t.join()
                service.set_phantom(ch, True)        # same thread as the grant: accepted

        token = PhantomPowerSafetyGate.issue_token(1)
        self.assertTrue(PhantomPowerSafetyGate.confirm_and_dispatch(Adapter(), 1, token))
        self.assertNotEqual(results["thread"], "accepted")
        self.assertEqual(len(self.phantom_on_sent()), 1)

    def test_p07_presets_never_enable_phantom(self):
        from flow8.presets import list_channel_presets
        for start_on in (False, True):
            if start_on:
                authorize_phantom_on(self.service, 1)
            self.driver.midiOutShortMsg.reset_mock()
            for preset in list_channel_presets():
                for ch in range(1, 8):
                    self.service.apply_channel_preset(ch, preset.id)
            self.assertEqual(self.phantom_on_sent(), [])
            self.assertEqual(self.cc8_sent(), [])
            self.assertEqual([m for m in self.sent() if (m >> 8) & 0xFF == 12], [])

    def test_p08_undo_redo_never_enable_phantom(self):
        authorize_phantom_on(self.service, 1)
        self.driver.midiOutShortMsg.reset_mock()
        for v in (30, 50, 70, 90):
            self.service.set_fader(1, v)
        for _ in range(4):
            self.service.undo()
        for _ in range(4):
            self.service.redo()
        self.assertEqual([m for m in self.sent() if (m >> 8) & 0xFF == 12], [])
        self.assertFalse(self.service.ledger.push(CommandLedger.make_record("phantom_power", 1, False, True)))

    def test_p09_scenes_never_enable_phantom(self):
        authorize_phantom_on(self.service, 1)
        self.service.set_fader(1, 60)
        self.service.capture_scene("S1")
        self.driver.midiOutShortMsg.reset_mock()
        self.service.recall_scene("S1")
        self.assertEqual([m for m in self.sent() if (m >> 8) & 0xFF == 12], [])

    def test_p10_no_automation_route(self):
        allowed = {"flow8/safety.py", "flow8/ui/safety_dialogs.py", "flow8/ui/components/channel_detail.py"}
        needles = ("issue_token", "confirm_and_dispatch", "_grant_phantom_on", "_phantom_on_permit",
                   "_consume_phantom_on_grant", "PhantomPowerSafetyGate")
        offenders = []
        for path in (ROOT / "flow8").rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            hits = [n for n in needles if n in text]
            if hits and rel not in allowed and rel != "flow8/command_boundary.py":
                offenders.append((rel, hits))
        self.assertEqual(offenders, [])
        # The boundary may only consume the grant and open the permit, nothing else.
        boundary = (ROOT / "flow8/command_boundary.py").read_text(encoding="utf-8")
        for forbidden in ("issue_token", "confirm_and_dispatch", "_grant_phantom_on"):
            self.assertNotIn(forbidden, boundary)
        # No code path inside the service enables phantom by itself.
        tree = ast.parse((ROOT / "flow8/service.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "set_phantom":
                self.fail("flow8/service.py calls set_phantom internally")

    def test_p11_compatibility_reexport(self):
        import flow8.safety as safety
        import flow8.ui.safety_dialogs as dialogs
        self.assertIs(dialogs.PhantomPowerSafetyGate, safety.PhantomPowerSafetyGate)
        self.assertIs(dialogs.PhantomPowerConfirmationToken, safety.PhantomPowerConfirmationToken)
        tree = ast.parse((ROOT / "flow8/safety.py").read_text(encoding="utf-8"))
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | \
                   {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertNotIn("tkinter", imported)
        self.assertFalse(any(m.startswith("flow8.ui") for m in imported))

    def test_p13_set_phantom_signature_unchanged(self):
        import inspect
        params = list(inspect.signature(Flow8Service.set_phantom).parameters)
        self.assertEqual(params, ["self", "channel_index", "enabled"])


if __name__ == "__main__":
    unittest.main()
