"""TASK 05 read-only audit runner: the repo's test suite with every winmm MIDI entry point counted.

Same guard as tools/run_tests_no_hw.py (refuses hardware env vars; midiOutOpen / midiInOpen raise),
plus midiOutShortMsg / midiOutLongMsg raise. Every other winmm midi* function is counted per test
and passed through unchanged (that is what the suite already does today). Verbosity 2 so each test's
name and skip reason are listed. Changes nothing in the repo.
"""
import collections
import ctypes
import json
import os
import sys
import unittest

REPO = r"C:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888"
os.chdir(REPO)
sys.path.insert(0, REPO)
for v in ("FLOW8_HW_TESTS", "FLOW8_HW_TESTS_MUTATE"):
    if os.environ.get(v):
        sys.exit(f"REFUSED: {v} is set")

winmm = ctypes.windll.winmm
current = ["<import>"]
calls = collections.defaultdict(collections.Counter)
BLOCK = {"midiOutOpen", "midiInOpen", "midiOutShortMsg", "midiOutLongMsg"}
PASS = ["midiOutGetNumDevs", "midiOutGetDevCapsW", "midiInGetNumDevs", "midiInGetDevCapsW",
        "midiOutClose", "midiOutReset", "midiInStart", "midiInStop", "midiInReset", "midiInClose"]


def wrap(name, real):
    def f(*a, **k):
        calls[current[0]][name] += 1
        if name in BLOCK:
            raise AssertionError(f"blocked physical MIDI call: {name}")
        return real(*a, **k)
    return f


for n in list(BLOCK) + PASS:
    setattr(winmm, n, wrap(n, getattr(winmm, n)))


class Result(unittest.TextTestResult):
    def startTest(self, test):
        current[0] = test.id()
        super().startTest(test)


suite = unittest.defaultTestLoader.discover("tests")
res = unittest.TextTestRunner(verbosity=2, resultclass=Result, stream=sys.stdout).run(suite)
blocked = {t: dict(c) for t, c in calls.items() if any(k in BLOCK for k in c)}
other = {t: dict(c) for t, c in calls.items() if not any(k in BLOCK for k in c)}
totals = collections.Counter()
for c in calls.values():
    totals.update(c)
print("WINMM_TOTALS", json.dumps(dict(totals)))
print("WINMM_BLOCKED_ATTEMPTS", json.dumps(blocked))
print("WINMM_OTHER_BY_TEST", json.dumps(other))
print("SKIPPED", json.dumps([(t.id(), r) for t, r in res.skipped]))
print("RESULT", res.testsRun, len(res.failures), len(res.errors), len(res.skipped))
