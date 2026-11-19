"""Launch the FLOW 8 web console — the default application surface.

```
python main.py                 # web console + meters + browser, no arguments
python main.py --legacy-tk     # the old Tkinter desktop window (regression only)
```

The console is served by `Flow8LanHub` on the LAN, so the same URL works on the
host computer and on an iPad in the same Wi-Fi. The launcher opens an app-mode
window in Edge/Chrome when one is installed, otherwise the default browser tab.

Nothing here opens MIDI by itself: `Flow8Service` owns the ports and the link
watchdog. `--no-meters` skips the USB capture stream for a MIDI-only console.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from typing import Any, Callable, Optional

from flow8.audio_meter import Flow8AudioMeter
from flow8.lan_hub import DEFAULT_LAN_PORT, Flow8LanHub
from flow8.service import Flow8Service
from flow8.snapshot_library import default_library_path

LOOP_INTERVAL_S = 2.5


def console_url(port: int, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{port}"


def existing_console(port: int, timeout: float = 1.0) -> bool:
    """True when this port already serves a FLOW 8 console."""
    if not port or port <= 0:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return isinstance(data, dict) and "midiConnected" in data
    except Exception:
        return False


def find_app_browser() -> Optional[str]:
    """An installed Chromium browser that supports app-mode windows."""
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


def open_console(
    url: str,
    *,
    app_window: bool = True,
    browser: Optional[str] = None,
    opener: Optional[Callable[[str], Any]] = None,
    popen: Optional[Callable[..., Any]] = None,
) -> Optional[Any]:
    """Open the console. Returns the app-mode process, or None for a browser tab."""
    if app_window:
        browser = browser if browser is not None else find_app_browser()
        if browser:
            launch = popen or subprocess.Popen
            try:
                return launch([browser, f"--app={url}", "--window-size=1440,900"])
            except OSError:
                pass  # a broken install must not stop the console
    (opener or webbrowser.open)(url)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flow8",
        description="FLOW 8 Live Console (web).",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_LAN_PORT,
                        help=f"LAN port (default {DEFAULT_LAN_PORT}; 0 picks a free port)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="bind address (default 0.0.0.0, so the iPad can reach it)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument("--no-app-window", action="store_true",
                        help="open a normal browser tab instead of an app-mode window")
    parser.add_argument("--no-meters", action="store_true",
                        help="skip the FLOW 8 USB capture meters")
    return parser


def _print_banner(port: int, lan_urls: list[str], meter_status: Optional[dict[str, Any]]) -> None:
    print("FLOW 8 web console running — FLOW 8 Live Console")
    print(f"  This computer : {console_url(port)}")
    if lan_urls:
        print(f"  iPad / LAN    : {lan_urls[0]}")
        for extra in lan_urls[1:]:
            print(f"                  {extra}")
    else:
        print("  iPad / LAN    : no LAN address found; connect this computer to Wi-Fi")
    if meter_status is not None:
        print(f"  Meters        : {meter_status.get('state')} — {meter_status.get('detail')}")
    else:
        print("  Meters        : off (--no-meters)")
    print("  Keep this window open. Ctrl+C stops the console and the mixer link.")


def run(
    args: argparse.Namespace,
    *,
    service_factory: Callable[..., Flow8Service] = Flow8Service,
    hub_factory: Callable[..., Flow8LanHub] = Flow8LanHub,
    meter_factory: Callable[..., Flow8AudioMeter] = Flow8AudioMeter,
    opener: Optional[Callable[[str], Any]] = None,
    browser_finder: Callable[[], Optional[str]] = find_app_browser,
    popen: Optional[Callable[..., Any]] = None,
    sleep: Callable[[float], Any] = time.sleep,
    loop_limit: Optional[int] = None,
    reuse_existing: bool = True,
) -> int:
    """Serve the console until interrupted. Every collaborator is injectable for tests."""
    port = getattr(args, "port", 0)
    if reuse_existing and existing_console(port):
        url = console_url(port)
        print("FLOW 8 web console is already running — opening the existing one")
        print(f"  This computer : {url}")
        if not getattr(args, "no_browser", False):
            open_console(
                url,
                app_window=not getattr(args, "no_app_window", False),
                browser=browser_finder(),
                opener=opener,
                popen=popen,
            )
        return 0

    service = service_factory(auto_connect=True)
    hub = hub_factory(service, host=getattr(args, "host", "0.0.0.0"),
                      port=args.port, library_path=default_library_path())
    meter: Optional[Flow8AudioMeter] = None
    app_window = None
    try:
        port = hub.start()
        if not getattr(args, "no_meters", False):
            meter = meter_factory(hub.publish_meters, hub.set_meter_status)
            meter.start()
        lan_urls = hub.lan_urls() if hasattr(hub, "lan_urls") else []
        _print_banner(port, lan_urls, meter.status if meter is not None else None)

        if not getattr(args, "no_browser", False):
            app_window = open_console(
                console_url(port),
                app_window=not getattr(args, "no_app_window", False),
                browser=browser_finder(),
                opener=opener,
                popen=popen,
            )

        iterations = 0
        while True:
            if app_window is not None and app_window.poll() is not None:
                break
            if service.is_connected:
                service.check_connection_health()
            else:
                service.connect()
            if meter is not None:
                meter.ensure_running()
            iterations += 1
            if loop_limit is not None and iterations >= loop_limit:
                break
            sleep(LOOP_INTERVAL_S)
    except KeyboardInterrupt:
        pass
    finally:
        if meter is not None:
            try:
                meter.stop()
            except Exception:
                pass
        try:
            hub.stop()
        except Exception:
            pass
        try:
            service.disconnect()
        except Exception:
            pass
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())