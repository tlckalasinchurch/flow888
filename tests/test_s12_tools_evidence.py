"""S1.2 safety tests: standalone tools and evidence protection (E-xx, D4, G-07).

The harness is exercised only with a MagicMock driver. No physical port is opened and no
repository evidence file is ever opened for writing.
"""
import ast
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests._no_hardware import NoHardwareMixin

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "docs/product/evidence_baseline.sha256"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HarnessTests(NoHardwareMixin, unittest.TestCase):
    def make(self, allow_write):
        from tools.flow8_midi_harness import Flow8MidiHarness
        driver = MagicMock()
        driver.midiOutShortMsg.return_value = 0
        harness = Flow8MidiHarness(winmm=driver, allow_write=allow_write)
        return harness, driver

    def test_e01_forbidden_messages_never_reach_the_driver(self):
        harness, driver = self.make(allow_write=True)
        forbidden = [
            (0xCF, 16, 0),       # mixer reset
            (0xCF, 15, 0), (0xC0, 1, 0),   # any Program Change
            (0x90, 0, 100), (0x80, 0, 0),  # Note On/Off
            (0xF0, 0x7E, 0), (0xF8, 0, 0), # SysEx start, real-time
            (0xB0, 8, 10),                 # gain
            (0xB0, 12, 127), (0xB1, 12, 127),  # phantom ON
            (0xB0, 6, 0),                  # solo: not allowlisted
            (0xB7, 8, 64), (0xB7, 14, 45), # bus limiter, GEQ
            (0xBF, 7, 64),                 # channel 16
        ]
        for status, b1, b2 in forbidden:
            with self.subTest(status=hex(status), b1=b1):
                with self.assertRaises(Exception):
                    harness.send_short_msg(status, b1, b2, "forbidden")
        driver.midiOutShortMsg.assert_not_called()
        harness.send_short_msg(0xB0, 7, 10, "allowed fader at a low level")
        driver.midiOutShortMsg.assert_called_once()

    def test_e02_no_arbitrary_midi_by_default(self):
        harness, driver = self.make(allow_write=False)
        with self.assertRaises(PermissionError):
            harness.send_short_msg(0xB0, 7, 10, "default")
        harness.run_safe_test_suite()          # must be a no-op without the explicit flag
        driver.midiOutShortMsg.assert_not_called()


class OutputTests(NoHardwareMixin, unittest.TestCase):
    def test_e03_cannot_overwrite(self):
        from tools._output import open_exclusive
        with tempfile.TemporaryDirectory() as d:
            existing = Path(d) / "evidence.md"
            existing.write_text("original", encoding="utf-8")
            before = sha(existing)
            with self.assertRaises(FileExistsError):
                open_exclusive(existing)
            self.assertEqual(sha(existing), before)

    def test_e04_unique_outputs(self):
        from tools._output import write_unique
        with tempfile.TemporaryDirectory() as d:
            a = write_unique(d, "run", ".md", "one")
            b = write_unique(d, "run", ".md", "two")
            self.assertNotEqual(a, b)
            self.assertEqual(Path(a).read_text(encoding="utf-8"), "one")
            self.assertEqual(Path(b).read_text(encoding="utf-8"), "two")

    def test_e05_logger_writes_unique_files(self):
        from tools.flow8_midi_in_logger import Flow8MidiInLogger
        with tempfile.TemporaryDirectory() as d:
            paths = set()
            for _ in range(2):
                logger = Flow8MidiInLogger(listener=MagicMock(device_info=(0, "x"), _target_name="x",
                                                              find_device_id=lambda: 0), out_dir=d)
                paths.add(str(logger.write_report({})))
            self.assertEqual(len(paths), 2)
            self.assertEqual(len(list(Path(d).iterdir())), 2)

    def test_e06_evidence_hashes_unchanged(self):
        self.assertTrue(BASELINE.exists())
        for line in BASELINE.read_text(encoding="utf-8").splitlines():
            digest, name = line.split(None, 1)
            self.assertEqual(sha(ROOT / name.strip()), digest, name)

    def test_e07_flow8_and_main_never_import_tools(self):
        for path in list((ROOT / "flow8").rglob("*.py")) + [ROOT / "main.py"]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    self.assertFalse(name == "tools" or name.startswith("tools."), f"{path.name} imports {name}")

    def test_e08_tools_never_open_files_for_writing_except_exclusively(self):
        tools = ROOT / "tools"
        self.assertTrue(tools.is_dir())
        for path in tools.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                    if name in ("write_text", "write_bytes"):
                        self.fail(f"{path.name}: {name}")
                    if name == "open" and not (isinstance(func, ast.Attribute)):
                        mode = None
                        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                            mode = node.args[1].value
                        for kw in node.keywords:
                            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                                mode = kw.value.value
                        if isinstance(mode, str):
                            self.assertFalse(set(mode) & set("wa+"), f"{path.name}: open mode {mode!r}")

    def test_e09_tools_do_not_name_historical_evidence_files(self):
        for path in (ROOT / "tools").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for name in ("FLOW8_PHASE1_RAW_MIDI_LOG", "FLOW8_PHASE2B_RAW_MIDI_LOG", "d01_events.jsonl"):
                self.assertNotIn(name, text, f"{path.name} names {name}")


if __name__ == "__main__":
    unittest.main()
