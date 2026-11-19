"""FLOW 8 entry point: the CueAir-style web console by default.

    python main.py               # web console + meters + browser window
    python main.py --legacy-tk   # legacy Tkinter desktop window (regression only)

The console is served on the LAN, so the same URL opens on the host computer and
on an iPad in the same Wi-Fi.
"""

from flow8.web_console import main

if __name__ == "__main__":
    raise SystemExit(main())
