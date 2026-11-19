"""Backward-compatible launcher: same web console as `python main.py`.

Kept so old shortcuts and documentation keep working. The new default entry
point is `main.py`; the legacy Tkinter window is `python main.py --legacy-tk`.
"""

from flow8.web_console import main

if __name__ == "__main__":
    raise SystemExit(main())
