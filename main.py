"""FLOW 8 entry point: the FLOW 8 Live Console (web).

    python main.py               # FLOW 8 Live Console + meters + browser window

The console is served on the LAN, so the same URL opens on the host computer and
on an iPad in the same Wi-Fi.
"""

from flow8.web_console import main

if __name__ == "__main__":
    raise SystemExit(main())
