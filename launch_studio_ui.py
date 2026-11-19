"""Backward-compatible launcher: same CueAir Pro web console as `python main.py`."""

from flow8.web_console import main

if __name__ == "__main__":
    raise SystemExit(main())
