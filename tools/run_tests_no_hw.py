#!/usr/bin/env python3
"""Run the whole test suite while proving no physical MIDI port is opened (S1.2, H-01).

The real winmm `midiOutOpen` / `midiInOpen` entry points are replaced by functions that count the
attempt and raise. The runner refuses to start when the opt-in hardware environment variables are
set. Prints the result by category and the number of attempted opens (must be 0).

Run from the repository root:  python -m tools.run_tests_no_hw
"""
import ctypes
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HW_VARIABLES = ("FLOW8_HW_TESTS", "FLOW8_HW_TESTS_MUTATE")


def main():
    active = [name for name in HW_VARIABLES if os.environ.get(name)]
    if active:
        print(f"REFUSED: hardware opt-in variables are set ({', '.join(active)}). Unset them and run again.")
        return 2
    attempts = []
    winmm = ctypes.windll.winmm
    originals = {name: getattr(winmm, name) for name in ("midiOutOpen", "midiInOpen")}

    def make_denier(name):
        def deny(*args, **kwargs):
            attempts.append(name)
            raise AssertionError(f"physical port open attempted: {name}")
        return deny

    for name in originals:
        setattr(winmm, name, make_denier(name))
    try:
        suite = unittest.defaultTestLoader.discover("tests")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        for name, fn in originals.items():
            setattr(winmm, name, fn)
    skipped = len(result.skipped)
    failed = len(result.failures)
    errors = len(result.errors)
    passed = result.testsRun - failed - errors - skipped - len(result.expectedFailures) - len(result.unexpectedSuccesses)
    print("\n=== Categories ===")
    print(f"ran {result.testsRun} | passed {passed} | failed {failed} | errors {errors} | skipped {skipped} | "
          f"expected failures {len(result.expectedFailures)} | unexpected successes {len(result.unexpectedSuccesses)}")
    print(f"hardware tests: NOT RUN (skipped {skipped}) | attempted physical port opens: {len(attempts)}")
    return 0 if result.wasSuccessful() and not attempts else 1


if __name__ == "__main__":
    sys.exit(main())
