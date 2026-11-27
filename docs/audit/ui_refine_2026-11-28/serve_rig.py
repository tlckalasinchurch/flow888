"""Serve the v3 console from the no-hardware rig until killed, for external inspectors.

Same guard and seed as ui_harness.py (winmm open/send raise; fake MIDI OUT). Port 8855, never 8844.
    python -I serve_rig.py [--offline]
"""
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_harness as H  # noqa: E402  (installs the winmm guard first)

s = H.Flow8Service(auto_connect=False)
H.fake_open_port(s.midi_out)
mi = s.midi_in
mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
s._connected = True
hub = H.Flow8LanHub(s, host="127.0.0.1", port=8855, library_path=None, show_modes_path=None)
print("serving", hub.start(), flush=True)
H.seed(hub, s)
try:
    while True:
        time.sleep(1)
        assert not H.PHYSICAL, H.PHYSICAL
finally:
    hub.stop()
