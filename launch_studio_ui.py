"""Launch FLOW 8 Tactile Studio Console in Desktop App-Mode + Wi-Fi LAN Hub."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser

from flow8.audio_meter import Flow8AudioMeter
from flow8.lan_hub import DEFAULT_LAN_PORT, Flow8LanHub
from flow8.service import Flow8Service
from flow8.snapshot_library import default_library_path


def _find_app_browser() -> str | None:
    candidates = [
        shutil.which("msedge"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def main() -> int:
    service = Flow8Service(auto_connect=True)
    hub = Flow8LanHub(service, port=DEFAULT_LAN_PORT, library_path=default_library_path())
    port = hub.start()
    # Input meters from the FLOW 8 USB audio stream. --no-meters turns them off.
    meter = None if "--no-meters" in sys.argv[1:] else Flow8AudioMeter(hub.publish_meters, hub.set_meter_status)
    if meter is not None:
        meter.start()
        print(f"  Meters     : {meter.status['detail']}")
    local_url = f"http://127.0.0.1:{port}"
    print("FLOW 8 Tactile Studio Console active")
    print(f"  Desktop URL: {local_url}")
    for url in hub.lan_urls():
        print(f"  Mobile URL : {url}")

    browser = _find_app_browser()
    proc = None
    if browser:
        proc = subprocess.Popen([browser, f"--app={local_url}", "--window-size=1440,900"])
    else:
        webbrowser.open(local_url)

    try:
        while True:
            if proc is not None and proc.poll() is not None:
                break
            if service.is_connected:
                service.check_connection_health()
            else:
                service.connect()
            if meter is not None:
                meter.ensure_running()
            time.sleep(2.5)
    except KeyboardInterrupt:
        pass
    finally:
        if meter is not None:
            meter.stop()
        hub.stop()
        service.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
