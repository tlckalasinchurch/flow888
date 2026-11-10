"""Desktop entry point for the FLOW 8 Cyber Neon workstation shell.

UI.2-T1: launches the application shell only. No MIDI port is opened and no
parameter is dispatched at start-up or shutdown.
"""

from flow8.ui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
