#!/usr/bin/env python3
"""List all test ids and compare with the baseline taken before S1.2 (N-01: no silent deletion).

  python -m tools.test_inventory            writes a NEW uniquely named inventory file and compares
The baseline `docs/product/test_inventory_before.txt` is never modified.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools._output import write_unique  # noqa: E402

BASELINE = Path(__file__).resolve().parent.parent / "docs/product/test_inventory_before.txt"


def ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from ids(test)
        else:
            yield test.id()


def main():
    now = sorted(set(ids(unittest.defaultTestLoader.discover("tests"))))
    before = set(BASELINE.read_text(encoding="utf-8").split())
    missing = sorted(before - set(now))
    added = sorted(set(now) - before)
    path = write_unique(Path(__file__).resolve().parent / "output", "test_inventory_after", ".txt", "\n".join(now) + "\n")
    print(f"baseline {len(before)} | now {len(now)} | missing {len(missing)} | added {len(added)} | written {path}")
    for name in missing:
        print("MISSING:", name)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
