# Launching FLOW 8 and cache behaviour

**Date:** 2026-11-19.
**Scope:** one default entry point for the CueAir-style web console, the legacy Tk window behind a
flag, and no-store delivery so a browser never shows a stale console.

## 1. The single command

```text
python main.py
```

or double-click **`start_studio.bat`** (same thing).

It starts, in this order:

1. `Flow8Service(auto_connect=True)` — MIDI ports + the link watchdog;
2. `Flow8LanHub` bound to `0.0.0.0:8844` (the port is printed);
3. `Flow8AudioMeter` (USB capture meters; skipped with `--no-meters`);
4. an app-mode window in Edge/Chrome (`--app=http://127.0.0.1:8844`), or a normal tab when
   no Chromium browser is installed, or nothing with `--no-browser`.

Useful flags:

| Flag | Effect |
|---|---|
| `--legacy-tk` | the old Tkinter desktop window (tests/regression only) |
| `--port N` | LAN port (default 8844; `0` picks a free port) |
| `--host ADDR` | bind address (default `0.0.0.0` so the iPad can connect) |
| `--no-browser` | serve only; print the URLs |
| `--no-app-window` | open a normal browser tab instead of an app window |
| `--no-meters` | MIDI-only console |

`start_legacy_tk.bat` runs `python main.py --legacy-tk`.

## 2. Addresses

The launcher prints both:

```
This computer : http://127.0.0.1:8844
iPad / LAN    : http://192.168.1.187:8844
```

- **PC:** `http://127.0.0.1:8844`
- **iPad (same Wi-Fi):** the printed LAN URL, e.g. `http://192.168.1.187:8844`.
- If Windows Firewall asks, allow **Private networks** for Python once; the console binds all
  interfaces deliberately for the iPad.

## 3. Launcher audit

| File | Before | Now |
|---|---|---|
| `main.py` | started the Tkinter shell | starts the web console (`flow8.web_console`) |
| `launch_studio_ui.py` | started hub + meters + browser (duplicated logic) | alias of the same entry point |
| `start_studio.bat` | `python launch_studio_ui.py` | `python main.py` |
| `start_legacy_tk.bat` | — | `python main.py --legacy-tk` |
| `FLOW8-CyberNeon.spec` | packaged `main.py` with no web assets | also bundles `flow8/web_ui` and imports `flow8.web_console` |

The old Tk interface is untouched under `flow8/ui/`; it is reachable only with the explicit
flag, so the existing Tk regression tests keep passing.

## 4. Cache behaviour

- `index.html`, `app.js`, `styles.css` and fonts are read from disk on every request and sent
  with `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`, `Pragma: no-cache`,
  `Expires: 0`; JSON APIs use the same no-store policy and SSE uses `no-store, no-cache`.
- Routing ignores a query string, so a cache-busting URL such as `/app.js?v=20261119` serves
  the same asset instead of a 404.
- `index.html` also carries `<meta http-equiv="Cache-Control" content="no-store">` and
  `Pragma: no-cache` as a belt-and-braces measure for Safari.
- Consequence: after an update, a refresh (or reopening the app window) always shows the new
  console. No hard-refresh or cache clearing is needed.

**Python changes still need a restart.** Static files are re-read per request, but the hub and
service modules are imported once when the process starts. If a window has been open since
before a code change, close it and run `python main.py` again (or press Ctrl+C in the launcher
window and start it once more).

## 5. Verification

```text
python -m unittest tests.test_web_console tests.test_web_cache
Ran 16 tests ... OK

python -m tools.run_tests_no_hw
ran 571 | passed 566 | failed 0 | errors 0 | skipped 5 | ...
hardware tests: NOT RUN (skipped 5) | attempted physical port opens: 0
```

Launcher smoke on this workstation (real process, port 8130, browser disabled):

```
STATUS 200
CACHE no-store, no-cache, must-revalidate, max-age=0
PRAGMA no-cache
EXPIRES 0
CONSOLE_TITLE True
TELEMETRY True WATCHDOG True CONNECTED True
LAN_URLS ['http://192.168.1.187:8130', 'http://169.254.83.107:8130']
```

## 6. Known limits

- The launcher needs a free port; if 8844 is taken it exits with a clear socket error. Use
  `--port` or stop the other instance.
- The app-mode window depends on Edge or Chrome; otherwise the default browser opens a tab.
- USB meters require `sounddevice` + PortAudio; without them the banner reports
  "Meters need the 'sounddevice' package" while the console keeps working.
- This stage changes launching and delivery only; it does not add hardware verification.

## 7. Shortcut and "old UI" troubleshooting

A stale desktop shortcut was found pointing at an **old project copy**
(`...\Desktop\mixing-station-pc-windows-3-2-2-789`, whose `main.py` still launches the Tk
window), and that folder had been moved, so the shortcut could only fail or open the legacy
UI. It is now repointed to
`...\00 - Projects\Flow888\flow888\start_studio.bat`, so double-clicking it always starts the
CueAir web console.

If several copies of the project exist on disk, only the one above is updated. Open the
console from that folder (or the repointed shortcut); do not use `FLOW8-CyberNeon.exe` from an
old `dist/` folder, which was built before the web console existed.

The launcher also detects an already-running console on the port and simply opens it instead
of failing to bind, so double-clicking twice is safe.
