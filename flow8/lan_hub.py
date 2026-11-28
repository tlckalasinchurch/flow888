"""Wi-Fi / LAN Remote Hub (HTTP + SSE) for Behringer FLOW 8 Workstation.

Adapted from Flow8-Remote-Pro's multi-screen SSE architecture, but strictly
enforces flow888's command boundary and safety policy:
- Every control action routes through Flow8Service (and so Flow8CommandBoundary).
- Preamp gain (CC 8) and +48V Phantom Power ON (CC 12) are blocked over LAN.
- Reported state always includes explicit provenance (never fakes hardware sync).
"""

from __future__ import annotations

import gzip
import http.server
import json
import logging
import math
import queue
import re
import socket
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.presets import list_channel_presets
from flow8.safety import BLOCKED_PARAMETER_TYPES
from flow8.service import MAIN_CHANNEL, RECALL_SCOPES, SCENE_CAPACITY, Flow8Service
from flow8.show_mode import compile_mode, unset_steps
from flow8.show_mode_store import ShowModeStore
from flow8.snapshot_library import SnapshotLibrary, default_library_path
from flow8.state_model import ParameterProvenance, EventSource

logger = logging.getLogger(__name__)

DEFAULT_LAN_PORT = 8844
WEB_UI_DIR = Path(__file__).resolve().parent / "web_ui"
FONT_PATH = re.compile(r"^/fonts/([a-z0-9-]+\.woff2)$")
# Largest accepted POST body (a library import is the biggest request).
MAX_BODY_BYTES = 1_000_000

# Meter frames: at most one SSE frame per interval; the feed counts as live
# while frames arrive within METER_STALE_S.
METER_MIN_INTERVAL_S = 1.0 / 30.0
METER_STALE_S = 2.0

#: A drag gesture older than this is closed before the next command, so an
#: abandoned pointer cannot turn unrelated commands into one undo step.
GESTURE_MAX_S = 20.0

# Actions that change the mix. After a scene recall, any of these marks the
# current scene as edited. Scene, scribble and preset-list actions do not.
_MIX_ACTIONS = frozenset({
    "setFader", "setPan", "setMute", "muteAll", "setBusFader", "setEqBand",
    "setLowCut", "setCompressor", "setSend", "undo", "redo", "applyPreset",
    "resetEqFlat", "libraryLoad", "pasteChannelDsp", "commitChangePlan", "runShowMode",
    "setBusLimiter", "setBusGeq", "setFxParam", "setFxPreset",
})


UNSUPPORTED = ParameterProvenance.UNSUPPORTED.value

# What the LAN remote may send for the two host-only safety parameters.
# Both stay False: dispatch_action() rejects gain and +48V with 403 regardless.
# The UI reads this map to show the controls as read-only.
LAN_POLICY = {"gain": False, "phantom": False}

# FLOW 8 functions that the Inspector shows but cannot send, with the reason.
# A feature leaves this map only when its MIDI address is on the verified
# allowlist (command_boundary.ACTIVE_ALLOWLIST) and the hub has an action for it.
LAN_LOCKED_FEATURES = {
    "gain": "Preamp gain is host-only (safety rule SR-05). Set it on the mixer.",
    "phantom": "+48V is host-only. Use the 48V key on the mixer.",
    "solo": "Solo (CC 6) is not on the verified MIDI allowlist.",
    "fxMute": "FX mute uses MIDI channel 16, which also carries the forbidden mixer reset. Use the mixer or a foot switch.",
    "tap": "Tap tempo uses MIDI channel 16, which also carries the forbidden mixer reset. Use the mixer or a foot switch.",
    "eqParametric": "EQ frequency and Q have no verified MIDI address. Gain only.",
    "stereoLink": "Stereo/mono link has no verified MIDI address. Set it on the mixer.",
    "routing": "Routing has no verified MIDI address. Set it in the FLOW 8 app or on the mixer.",
    "outputPad": "The -10 dBV output pads have no verified MIDI address.",
    "footswitch": "Foot switch mode has no verified MIDI address.",
    "hwSnapshots": "Mixer memory snapshots use Program Change on MIDI channel 16 (16 = reset, forbidden). The slots here are hub snapshots.",
}

# Actions that change no mixer value: allowed while MIDI is closed.
_OFFLINE_ACTIONS = frozenset({
    "setScribble", "librarySave", "libraryRename", "libraryDelete", "libraryImport",
    "setActiveBus", "setActiveView", "previewChangePlan", "beginGesture", "endGesture",
    "setTransportMode", "bleDumpTrigger", "saveShowMode",
})


def latency_percentiles(values: list[float]) -> dict[str, Any]:
    """Nearest-rank p50/p95/p99 and max of *values*; None for each when empty."""
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None}

    def rank(p: float) -> float:
        return ordered[max(math.ceil(p * n) - 1, 0)]

    return {"n": n, "p50": rank(0.50), "p95": rank(0.95), "p99": rank(0.99), "max": ordered[-1]}


def get_lan_ips() -> list[str]:
    """Return non-loopback IPv4 addresses for LAN clients."""
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


class _ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class Flow8LanHub:
    """Thread-safe HTTP + SSE remote hub backed by Flow8Service."""

    def __init__(
        self,
        service: Flow8Service,
        host: str = "0.0.0.0",
        port: int = DEFAULT_LAN_PORT,
        library_path: Optional[Path] = None,
        show_modes_path: Optional[Path] = None,
    ) -> None:
        self.service = service
        # library_path None: the library lives in memory only (tests, embedded use).
        self.library = SnapshotLibrary(library_path)
        # show_modes_path None: the two Show Modes live in memory only (tests, embedded use).
        self.show_modes = ShowModeStore(show_modes_path)
        self.host = host
        self._requested_port = port
        self._server: Optional[_ThreadedHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._sse_lock = threading.Lock()
        self._subscribers: list[tuple[queue.Queue[bytes], Optional[str]]] = []
        self._sse_dropped_meter_frames = 0
        self._sse_removed_clients = 0
        # Set by the launcher to Flow8AudioMeter.stats; None when meters are off.
        self.meter_stats_source: Optional[Callable[[], dict[str, Any]]] = None
        self._listening = False
        self._scribbles: dict[int, dict[str, str]] = {}
        self._scene_lock = threading.Lock()
        self._current_scene: Optional[str] = None
        self._scene_edited = False
        self._last_meter_frame = 0.0
        self._last_meter_sent = 0.0
        self._local = threading.local()
        # One open batch gesture at a time; a stale one is closed before the next command.
        self._gesture_client: Optional[str] = None
        self._gesture_started = 0.0
        self._meter_status: dict[str, Any] = {
            "state": "stopped", "detail": "Meters are off.", "device": None, "mode": None,
        }

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._listening

    @property
    def port(self) -> int:
        if self._server is not None:
            return int(self._server.server_address[1])
        return self._requested_port

    def lan_urls(self) -> list[str]:
        p = self.port
        ips = get_lan_ips() or ["127.0.0.1"]
        return [f"http://{ip}:{p}" for ip in ips]

    def start(self) -> int:
        """Start the HTTP/SSE server in a background daemon thread. Returns bound port."""
        if self._server is not None:
            return self.port
        hub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

            def _send_json(self, code: int, obj: Any) -> None:
                data = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_asset(self, filename: str, content_type: str) -> None:
                asset_path = WEB_UI_DIR / filename
                if not asset_path.is_file():
                    self._send_json(404, {"error": f"missing asset: {filename}"})
                    return
                body = asset_path.read_bytes()
                # Text assets compress about 4x; that matters for an iPad on venue Wi-Fi. Fonts are already compressed.
                gzipped = content_type.startswith(("text/", "application/javascript")) and "gzip" in (self.headers.get("Accept-Encoding") or "")
                if gzipped:
                    body = gzip.compress(body, compresslevel=6)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Vary", "Accept-Encoding")
                if gzipped:
                    self.send_header("Content-Encoding", "gzip")
                # The console is served from disk on every request: never let a
                # browser (desktop or iPad Safari) reuse a cached copy after an update.
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                # A cache-busting query (?v=...) must not change which asset is served.
                route = self.path.split("?", 1)[0]
                if route == "/" or route.startswith("/index.html"):
                    self._send_asset("index.html", "text/html; charset=utf-8")
                    return
                if route == "/styles.css":
                    self._send_asset("styles.css", "text/css; charset=utf-8")
                    return
                if route == "/app.js":
                    self._send_asset("app.js", "application/javascript; charset=utf-8")
                    return
                # FLOW 888 v3 console: same API and safety path, new surface.
                if route in ("/v3", "/v3/", "/v3/index.html"):
                    self._send_asset("v3/index.html", "text/html; charset=utf-8")
                    return
                if route == "/v3/v3.css":
                    self._send_asset("v3/v3.css", "text/css; charset=utf-8")
                    return
                if route == "/v3/v3.js":
                    self._send_asset("v3/v3.js", "application/javascript; charset=utf-8")
                    return
                font = FONT_PATH.match(route)
                if font:
                    self._send_asset(f"fonts/{font.group(1)}", "font/woff2")
                    return

                if self.path.startswith("/api/status"):
                    self._send_json(200, hub.status_snapshot())
                    return

                if self.path.startswith("/api/presets/thai"):
                    from flow8.presets_th import CATALOG_ID, CATEGORIES, list_thai_presets

                    self._send_json(200, {
                        "catalog": CATALOG_ID,
                        "categories": list(CATEGORIES),
                        "presets": [p.as_payload() for p in list_thai_presets()],
                    })
                    return

                if self.path.startswith("/api/presets"):
                    self._send_json(200, {
                        "presets": [
                            {
                                "id": p.id,
                                "name": p.name,
                                "category": p.category,
                                "summary": p.summary,
                            }
                            for p in list_channel_presets()
                        ]
                    })
                    return

                if self.path.startswith("/api/library/export"):
                    body = json.dumps(hub.library.export(), indent=2, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="flow8-snapshot-library.json"')
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if self.path.startswith("/api/session"):
                    self._send_json(200, hub.session_snapshot())
                    return

                if self.path.startswith("/api/events"):
                    client_id = None
                    if "clientId=" in self.path:
                        client_id = self.path.split("clientId=")[1].split("&")[0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store, no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    q: queue.Queue[bytes] = queue.Queue(maxsize=128)
                    with hub._sse_lock:
                        hub._subscribers.append((q, client_id))
                    try:
                        init = f"data: {json.dumps({'type': 'connected', 'clientId': client_id})}\n\n".encode("utf-8")
                        self.wfile.write(init)
                        self.wfile.flush()
                        last_ping = time.time()
                        while hub.is_running:
                            try:
                                msg = q.get(timeout=0.5)
                                self.wfile.write(msg)
                                self.wfile.flush()
                            except queue.Empty:
                                # broadcast() dropped this client (queue full on a state
                                # event): end the stream so EventSource reconnects and reloads.
                                with hub._sse_lock:
                                    if (q, client_id) not in hub._subscribers:
                                        break
                            if time.time() - last_ping > 15.0:
                                self.wfile.write(b": ping\n\n")
                                self.wfile.flush()
                                last_ping = time.time()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        pass
                    finally:
                        with hub._sse_lock:
                            if (q, client_id) in hub._subscribers:
                                hub._subscribers.remove((q, client_id))
                        # The "Connection: keep-alive" header above would keep the socket open
                        # waiting for another request; close it so the client sees the end.
                        self.close_connection = True
                    return

                self._send_json(404, {"error": "not found"})

            def do_POST(self) -> None:
                if self.path != "/api/action":
                    self._send_json(404, {"error": "not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0") or 0)
                except ValueError:
                    length = -1
                if not 0 <= length <= MAX_BODY_BYTES:
                    # Answer first, then drain what the client is still writing (bounded),
                    # so it reads the 413 instead of seeing the upload connection aborted.
                    self._send_json(413, {"ok": False, "error": "Request too large (limit 1 MB)."})
                    try:
                        if length > 0:
                            self.rfile.read(min(length, 8 * MAX_BODY_BYTES))
                    except Exception:
                        pass
                    self.close_connection = True
                    return
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as exc:
                    self._send_json(400, {"ok": False, "error": f"invalid json: {exc}"})
                    return
                code, result = hub.dispatch_action(payload)
                self._send_json(code, result)

        self._server = _ThreadedHTTPServer((self.host, self._requested_port), Handler)
        self._listening = True
        self.service.add_listener(self._on_service_event)
        self.service.add_command_log_listener(self._on_command_log)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="flow8-lan-hub",
            daemon=True,
        )
        self._thread.start()
        return self.port

    def stop(self) -> None:
        self._listening = False
        try:
            self.service.remove_listener(self._on_service_event)
        except Exception:
            pass
        try:
            self.service.remove_command_log_listener(self._on_command_log)
        except Exception:
            pass
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _on_command_log(self, _entries: list) -> None:
        """Broadcast desktop-originated commands to SSE browser clients."""
        if getattr(self._local, "in_dispatch", False):
            return
        self.broadcast({"type": "state"})

    def _on_service_event(self, param_id: str, value: Any, source: Any = None) -> None:
        # The service reports a real parameter id only for values the mixer sent
        # over MIDI IN (hardware moves). "__name__" ids are internal state events.
        if param_id.startswith("__"):
            if param_id == "__changed__" and getattr(self._local, "in_dispatch", False):
                return
            kind = "link" if param_id == "__reconcile__" else "state"
            self.broadcast({"type": kind})
            return
        with self._scene_lock:
            if self._current_scene is not None:
                self._scene_edited = True
        # Attach a minimal source tag so the UI can tell hardware-observed from
        # software-commanded when it builds its RX-update map (see app.js RX_UPDATE_MAP).
        tag = "hw" if source is EventSource.PHYSICAL_HARDWARE else "sw"
        self.broadcast({"type": "rx", "paramId": param_id, "value": value, "_source": tag})

    def publish_meters(self, levels: dict[str, dict[str, float]]) -> bool:
        """Publish one meter frame from a measured audio source.

        ``levels`` maps a strip id ("ch1".."ch7", "main", "mon1".."fx2") to
        ``{"peak": dBFS, "rms": dBFS}``. Call this only with levels measured
        from audio (for example the FLOW 8 USB capture stream). The FLOW 8 does
        not send meter data over MIDI, so the hub never creates levels itself.
        Returns False when the frame was dropped by the rate limit.
        """
        now = time.monotonic()
        self._last_meter_frame = now
        if now - self._last_meter_sent < METER_MIN_INTERVAL_S:
            return False
        self._last_meter_sent = now
        clean = {
            str(k): {
                "peak": round(float(v.get("peak", -120.0)), 1),
                "rms": round(float(v.get("rms", -120.0)), 1),
            }
            for k, v in levels.items()
        }
        self.broadcast({"type": "meters", "levels": clean}, droppable=True)
        pub = getattr(self.service, "publish_meters", None)
        if callable(pub):
            try:
                pub(clean)
            except Exception:
                pass
        return True

    def set_meter_status(self, status: dict[str, Any]) -> None:
        """Store the meter source state (see Flow8AudioMeter) and tell clients."""
        self._meter_status = {
            "state": str(status.get("state", "stopped")),
            "detail": str(status.get("detail", "")),
            "device": status.get("device"),
            "mode": status.get("mode"),
        }
        self.broadcast({"type": "state"})

    @property
    def meter_status(self) -> dict[str, Any]:
        return dict(self._meter_status)

    @property
    def meter_feed_live(self) -> bool:
        return self._last_meter_frame > 0 and time.monotonic() - self._last_meter_frame < METER_STALE_S

    def broadcast(self, event: dict[str, Any], droppable: bool = False) -> None:
        """Send one SSE event to every client.

        A full client queue drops a ``droppable`` event (meter frames) but
        disconnects the client for any other event, so it reloads its state.
        """
        payload = f"data: {json.dumps(event, default=str)}\n\n".encode("utf-8")
        dead: list[tuple[queue.Queue[bytes], Optional[str]]] = []
        with self._sse_lock:
            for item in self._subscribers:
                try:
                    item[0].put_nowait(payload)
                except queue.Full:
                    if not droppable:
                        dead.append(item)
                    else:
                        self._sse_dropped_meter_frames += 1
                except Exception:
                    dead.append(item)
            for item in dead:
                if item in self._subscribers:
                    self._subscribers.remove(item)
                    self._sse_removed_clients += 1

    def sse_stats(self) -> dict[str, Any]:
        """Event-stream health: client count, queue depths, dropped frames, removed clients."""
        with self._sse_lock:
            depths = [q.qsize() for q, _ in self._subscribers]
            return {
                "clients": len(depths),
                "maxQueueDepth": max(depths, default=0),
                "queueDepths": depths,
                "droppedMeterFrames": self._sse_dropped_meter_frames,
                "removedClients": self._sse_removed_clients,
            }

    def _dispatch_snapshot(self) -> dict[str, Any]:
        """Counts of outbound commands and the last dispatch outcome.

        driverDispatched only means WinMM accepted the short message; it is not
        proof the mixer applied it (docs/product/FLOW8_EVIDENCE_REGISTER.md).
        """
        boundary = self.service.command_boundary
        log = boundary.command_log
        last = log[-1] if log else None
        return {
            **boundary.command_counts,
            "logLength": len(log),
            # Time to the driver return (not to the mixer), over the bounded log window.
            "latencyUs": latency_percentiles([e.latency_us for e in log if e.driver_dispatched]),
            "last": None if last is None else {
                "paramId": last.param_id,
                "status": last.dispatch_status,
                "driverDispatched": bool(last.driver_dispatched),
                "error": last.error_message,
            },
        }

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "meterStats": self.meter_stats_source() if self.meter_stats_source else None,
            "sse": self.sse_stats(),
            "midiConnected": self.service.is_connected,
            "midiOutOpen": self.service.midi_out_open,
            "midiInOpen": self.service.midi_in_open,
            "meterFeed": self.meter_feed_live,
            "meterStatus": self.meter_status,
            "transportMode": self.service.transport_mode,
            "ble": self.service.ble_status_snapshot(),
            "transport": self.service.transport_status(),
            "stateSync": self.service.state_sync_snapshot(),
            "telemetry": self.service.telemetry_status(),
            "dispatch": self._dispatch_snapshot(),
            "lanUrls": self.lan_urls(),
            "port": self.port,
        }

    def _param_raw(self, param_id: str, default: Any) -> tuple[Any, str]:
        st = self.service.state_store.get_parameter(param_id)
        if st is None:
            return default, ParameterProvenance.UNSYNCED.value
        if st.provenance == ParameterProvenance.OBSERVED and st.observed_raw_midi is not None:
            raw = st.observed_raw_midi
        else:
            raw = st.commanded_raw_midi if st.commanded_raw_midi is not None else st.observed_raw_midi
        if raw is None:
            raw = default
        return raw, st.provenance.value

    def session_snapshot(self) -> dict[str, Any]:
        channels = []
        for idx in range(1, 8):
            spec = LOGICAL_CHANNELS[idx]
            fader, f_prov = self._param_raw(f"ch{idx}.fader", 0)
            pan, p_prov = self._param_raw(f"ch{idx}.pan", 64)
            mute, m_prov = self._param_raw(f"ch{idx}.mute", 0)
            eq = {
                band: int(self._param_raw(f"ch{idx}.eq_{band}", 64)[0])
                for band in ("low", "low_mid", "hi_mid", "hi")
            }
            eq_prov = self._param_raw(f"ch{idx}.eq_low", 64)[1]
            send_raw = {
                target: self._param_raw(f"ch{idx}.send_{target}", 0)
                for target in ("mon1", "mon2", "fx1", "fx2")
            }
            sends = {target: int(raw) for target, (raw, _) in send_raw.items()}
            sends_prov = {target: prov for target, (_, prov) in send_raw.items()}
            low_cut, lc_prov = self._param_raw(f"ch{idx}.low_cut", 0) if idx <= 4 else (0, UNSUPPORTED)
            comp, comp_prov = self._param_raw(f"ch{idx}.compressor", 0) if idx <= 4 else (0, UNSUPPORTED)
            # Gain and +48V are shown read-only: the LAN remote never sends them.
            gain, gain_prov = self._param_raw(f"ch{idx}.gain", None) if idx <= 4 else (None, UNSUPPORTED)
            phantom, ph_prov = self._param_raw(f"ch{idx}.phantom", None) if idx <= 2 else (None, UNSUPPORTED)
            scribble = self._scribbles.get(idx, {})
            channels.append({
                "index": idx,
                "name": spec.name,
                "label": scribble.get("label", spec.name),
                "color": scribble.get("color", "#38bdf8"),
                "fader": int(fader),
                "faderProvenance": f_prov,
                "pan": int(pan),
                "panProvenance": p_prov,
                "mute": bool(mute),
                "muteProvenance": m_prov,
                "eq": eq,
                "eqProvenance": eq_prov,
                "lowCut": int(low_cut),
                "lowCutProvenance": lc_prov,
                "compressor": int(comp),
                "compressorProvenance": comp_prov,
                "gain": None if gain is None else int(gain),
                "gainProvenance": gain_prov,
                "phantom": None if phantom is None else bool(phantom),
                "phantomProvenance": ph_prov,
                "sends": sends,
                "sendsProvenance": sends_prov,
            })
        main_f, main_f_prov = self._param_raw("main.fader", 101)
        main_b, main_b_prov = self._param_raw("main.balance", 64)
        channels.append({
            "index": MAIN_CHANNEL,
            "name": "Main L/R",
            "fader": int(main_f),
            "faderProvenance": main_f_prov,
            "pan": int(main_b),
            "panProvenance": main_b_prov,
            "mute": False,
            "muteProvenance": ParameterProvenance.UNSUPPORTED.value,
        })
        buses = []
        for bus_id in ("mon1", "mon2", "fx1", "fx2"):
            bf, bf_prov = self._param_raw(f"{bus_id}.fader", 0)
            buses.append({
                "id": bus_id,
                "fader": int(bf),
                "faderProvenance": bf_prov,
            })
        # Limiter + GEQ (MAIN/MON1/MON2) and FX engines: commanded values only, the
        # mixer reports none of them, so provenance is UNSYNCED or COMMANDED.
        bus_dsp = {}
        for bus_id in ("main", "mon1", "mon2"):
            lim, lim_prov = self._param_raw(f"{bus_id}.limiter", 127)
            geq = [self._param_raw(f"{bus_id}.geq{band}", 64) for band in range(1, 10)]
            bus_dsp[bus_id] = {
                "limiter": int(lim), "limiterProvenance": lim_prov,
                "geq": [int(raw) for raw, _ in geq], "geqProvenance": [prov for _, prov in geq],
            }
        fx_engines = {}
        for fx_id, prefix in (("fx1", "fxe1"), ("fx2", "fxe2")):
            preset, preset_prov = self._param_raw(f"{prefix}.preset", 1)
            p1, p1_prov = self._param_raw(f"{prefix}.param1", 0)
            p2, p2_prov = self._param_raw(f"{prefix}.param2", 0)
            fx_engines[fx_id] = {
                "preset": int(preset), "presetProvenance": preset_prov,
                "param1": int(p1), "param1Provenance": p1_prov,
                "param2": bool(p2), "param2Provenance": p2_prov,
            }
        with self._scene_lock:
            current_scene, scene_edited = self._current_scene, self._scene_edited
        return {
            "midiConnected": self.service.is_connected,
            "midiOutOpen": self.service.midi_out_open,
            "midiInOpen": self.service.midi_in_open,
            "meterFeed": self.meter_feed_live,
            "meterStatus": self.meter_status,
            "transportMode": self.service.transport_mode,
            "ble": self.service.ble_status_snapshot(),
            "telemetry": self.service.telemetry_status(),
            "dispatch": self._dispatch_snapshot(),
            "currentScene": current_scene,
            "sceneEdited": scene_edited,
            "activeBus": self.service.active_bus,
            "activeView": self.service.active_view,
            "transportMode": self.service.transport_mode,
            "ble": self.service.ble_status_snapshot(),
            "transport": self.service.transport_status(),
            "stateSync": self.service.state_sync_snapshot(),
            "channels": channels,
            "buses": buses,
            "busDsp": bus_dsp,
            "fxEngines": fx_engines,
            "scenes": list(self.service.scenes.names()),
            "sceneSlots": SCENE_CAPACITY,
            "sceneInfo": self._scene_info(),
            "recallScopes": list(RECALL_SCOPES),
            "library": self.library.summaries(),
            "libraryError": self.library.load_error,
            "showModes": self.show_modes.summaries(),
            "showModesError": self.show_modes.load_error,
            "lanPolicy": dict(LAN_POLICY),
            "locked": dict(LAN_LOCKED_FEATURES),
        }

    def _scene_info(self) -> list[dict[str, Any]]:
        from flow8.snapshot_library import scope_counts
        return [
            {"name": snap.name, "capturedAt": snap.captured_at.isoformat(timespec="seconds"),
             "scopes": scope_counts(snap.parameters)}
            for snap in self.service.scenes.list_snapshots()
        ]

    def dispatch_action(self, msg: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Execute a LAN action strictly through Flow8Service and safety rules."""
        action = str(msg.get("action", ""))

        # A gesture the client never closed must not swallow later commands into
        # one undo step, so close it after a bounded time.
        if self._gesture_client is not None and time.monotonic() - self._gesture_started > GESTURE_MAX_S:
            self.service.end_batch()
            self._gesture_client = None

        # Safety blocks: never allow gain or +48V ON over LAN
        if action == "setGain" or "gain" in BLOCKED_PARAMETER_TYPES and action == "gain":
            return 403, {"ok": False, "error": "Preamp gain is blocked by safety policy (SR-05)."}
        if action in ("set48V", "setPhantom", "phantom"):
            return 403, {"ok": False, "error": "+48V phantom power requires explicit host confirmation dialog."}

        # A change plan is reviewed data: no level automation, no +48V, ever.
        if action in ("previewChangePlan", "commitChangePlan"):
            changes = msg.get("changes")
            if not isinstance(changes, list):
                return 400, {"ok": False, "error": "changes must be a list"}
            for raw in changes:
                entry = raw if isinstance(raw, dict) else {}
                parameter = str(entry.get("parameter", "")).lower()
                if parameter in ("gain", "phantom", "phantom_power") or entry.get("includePhantom"):
                    return 403, {
                        "ok": False,
                        "error": "Preamp gain and +48V are never part of a change plan (SR-05 / SR-06).",
                    }

        # A command sent while the active control transport is closed would be
        # recorded as "commanded" but never reach the mixer. In USB mode keep
        # the historical requirement (both endpoints + listening); in BLE /
        # hybrid mode require an authenticated BLE session instead.
        if action not in _OFFLINE_ACTIONS:
            if self.service.transport_mode == "usb_midi":
                control_ready = self.service.is_connected
            else:
                control_ready = self.service.control_connected
            if not control_ready:
                return 503, {
                    "ok": False,
                    "code": "not_connected",
                    "error": "Mixer control transport is not connected/authenticated. The command was not sent.",
                }

        extra: dict[str, Any] = {}
        self._local.in_dispatch = True
        try:
            if action == "setFader":
                self.service.set_fader(int(msg["channel"]), int(msg["value"]))
            elif action == "setPan":
                self.service.set_pan(int(msg["channel"]), int(msg["value"]))
            elif action == "setMute":
                self.service.set_mute(int(msg["channel"]), bool(msg["value"]))
            elif action == "muteAll":
                muted = bool(msg["value"])
                with self.service._ledger_lock:
                    self.service.begin_batch()
                    try:
                        for ch in range(1, 8):
                            self.service.set_mute(ch, muted)
                    finally:
                        self.service.end_batch()
            elif action == "setBusFader":
                self.service.set_bus_fader(str(msg["bus"]), int(msg["value"]))
            elif action == "setBusLimiter":
                self.service.set_bus_limiter(str(msg["bus"]), int(msg["value"]))
            elif action == "setBusGeq":
                self.service.set_bus_geq(str(msg["bus"]), int(msg["band"]), int(msg["value"]))
            elif action == "setFxParam":
                self.service.set_fx_param(str(msg["engine"]), int(msg["param"]), msg["value"])
            elif action == "setFxPreset":
                self.service.set_fx_preset(str(msg["engine"]), int(msg["value"]))
            elif action == "setEqBand":
                self.service.set_eq_band(
                    int(msg["channel"]), str(msg["band"]), msg["value"],
                    unit=str(msg.get("unit", "raw")),
                )
            elif action == "setLowCut":
                self.service.set_low_cut(
                    int(msg["channel"]), msg["value"],
                    unit=str(msg.get("unit", "raw")),
                )
            elif action == "setCompressor":
                self.service.set_compressor(
                    int(msg["channel"]), msg["value"],
                    unit=str(msg.get("unit", "raw")),
                )
            elif action == "setSend":
                self.service.set_send(
                    int(msg["channel"]), str(msg["target"]), msg["value"],
                    unit=str(msg.get("unit", "raw")),
                )
            elif action == "undo":
                self.service.undo()
            elif action == "redo":
                self.service.redo()
            elif action == "captureScene":
                self.service.capture_scene(str(msg["name"]))
            elif action == "recallScene":
                result = self.service.recall_scene(str(msg["name"]), msg.get("scope"))
                extra = {"applied": result.applied, "failed": len(result.failed)}
            elif action == "libraryLoad":
                entry = self.library.get(str(msg["id"]))
                result = self.service.apply_mix_state(
                    entry["name"], self.library.parameters(entry["id"]), msg.get("scope"))
                extra = {"applied": result.applied, "failed": len(result.failed), "name": entry["name"]}
            elif action == "librarySave":
                extra = self.library.save(
                    str(msg.get("name", "")), self.service.known_mix_state(),
                    entry_id=(str(msg["id"]) if msg.get("id") else None))
            elif action == "libraryRename":
                self.library.rename(str(msg["id"]), str(msg.get("name", "")))
            elif action == "libraryDelete":
                self.library.delete(str(msg["id"]))
            elif action == "libraryImport":
                extra = self.library.import_data(msg.get("data"))
            elif action == "applyPreset":
                if msg.get("includePhantom"):
                    return 403, {"ok": False, "error": "+48V phantom power requires explicit host confirmation dialog."}
                raw_scopes = msg.get("scopes")
                scopes = [str(s) for s in raw_scopes] if isinstance(raw_scopes, list) else None
                ok = self.service.apply_channel_preset(
                    int(msg["channel"]), str(msg["presetId"]), preserve_levels=True, scopes=scopes
                )
                if not ok:
                    return 400, {"ok": False, "error": "invalid channel or preset"}
            elif action == "pasteChannelDsp":
                ch = int(msg["channel"])
                if not (1 <= ch <= 7):
                    return 400, {"ok": False, "error": "invalid channel"}
                if "gain" in msg or "phantom" in msg or "includePhantom" in msg:
                    return 403, {"ok": False, "error": "Preamp gain and +48V are blocked by safety policy over LAN."}
                unit = str(msg.get("unit", "raw"))
                with self.service._ledger_lock:
                    self.service.begin_batch()
                    try:
                        eq_map = msg.get("eq")
                        if isinstance(eq_map, dict):
                            for band in ("low", "low_mid", "hi_mid", "hi"):
                                if band in eq_map and eq_map[band] is not None:
                                    self.service.set_eq_band(ch, band, eq_map[band], unit=unit)
                        if ch <= 4 and msg.get("lowCut") is not None:
                            self.service.set_low_cut(ch, msg["lowCut"], unit=str(msg.get("lowCutUnit", unit)))
                        if ch <= 4 and msg.get("compressor") is not None:
                            self.service.set_compressor(ch, msg["compressor"], unit=str(msg.get("compUnit", unit)))
                        sends_map = msg.get("sends")
                        if isinstance(sends_map, dict):
                            for target, val in sends_map.items():
                                if val is not None:
                                    self.service.set_send(ch, str(target), val, unit=unit)
                    finally:
                        self.service.end_batch()
            elif action == "beginGesture":
                # A drag (pointer down) opens one ledger batch: every value the
                # drag sends coalesces into a single undo step.
                self.service.begin_batch()
                self._gesture_client = str(msg.get("clientId") or "")
                self._gesture_started = time.monotonic()
            elif action == "endGesture":
                steps = self.service.end_batch()
                self._gesture_client = None
                extra = {"steps": steps}
            elif action == "previewChangePlan":
                from flow8.change_plan import make_plan

                plan = make_plan(msg.get("title"), msg.get("changes") or [])
                rows, guard = self.service.stage_change_plan(plan)
                extra = {
                    "planId": plan.plan_id,
                    "title": plan.title,
                    "guard": guard,
                    "rows": [row.as_dict() for row in rows],
                    "willSend": sum(1 for row in rows if row.status == "change"),
                }
            elif action == "commitChangePlan":
                from flow8.change_plan import PreviewRequiredError, make_plan

                plan = make_plan(msg.get("title"), msg.get("changes") or [])
                try:
                    result = self.service.commit_change_plan(
                        plan, guard=msg.get("guard"), require_guard=True
                    )
                except PreviewRequiredError as error:
                    return 409, {
                        "ok": False,
                        "code": "preview_required",
                        "error": str(error),
                    }
                if result.stale:
                    return 409, {
                        "ok": False,
                        "code": "stale_plan",
                        "error": result.error,
                        "staleParameters": result.stale_rows,
                        "rows": result.fresh_rows,
                        "planId": result.plan_id,
                    }
                extra = {
                    "planId": result.plan_id,
                    "title": result.title,
                    "applied": result.applied,
                    "skipped": result.skipped,
                    "rolledBack": result.rolled_back,
                    "snapshot": result.snapshot_label,
                    "undoReady": result.undo_ready,
                }
                if result.error and not result.stale:
                    extra["failed"] = result.failed
                    return 409, {
                        "ok": False,
                        "error": (
                            "The change plan failed and the values already sent were restored."
                            if result.rolled_back else
                            "The change plan failed; some values could not be restored "
                            "(their previous value was unknown)."
                        ),
                        **extra,
                    }
            elif action == "saveShowMode":
                extra = {"mode": self.show_modes.save(str(msg.get("id", "")), msg.get("steps"))}
            elif action == "runShowMode":
                from flow8.change_plan import make_plan

                mode = self.show_modes.get(str(msg.get("id", "")))
                unset = unset_steps(mode)
                if unset:
                    return 409, {
                        "ok": False, "code": "show_mode_unset", "unsetSteps": unset,
                        "error": f"{mode['name']} has {len(unset)} step(s) NOT SET. Set them in Setup > Show modes.",
                    }
                plan = make_plan(f"SHOW MODE · {mode['name']}", compile_mode(mode))
                # One lock hold: a second client's run must see this run's values, and
                # the guard must not see a value this same request is about to write.
                with self.service._ledger_lock:
                    rows, guard = self.service.stage_change_plan(plan)
                    result = self.service.commit_change_plan(plan, guard=guard, require_guard=True)
                if result.stale:
                    return 409, {
                        "ok": False, "mode": mode["name"], "rolledBack": False, "failed": [],
                        "error": "The mix changed while the mode was running; nothing was sent. Hold the mode again.",
                    }
                if result.error:
                    return 409, {
                        "ok": False, "mode": mode["name"],
                        "error": (
                            "The mode failed and the values already sent were restored."
                            if result.rolled_back else
                            "The mode failed; some values could not be restored (their previous value "
                            "was unknown). Check the mixer."
                        ) + f" ({result.error})",
                        "rolledBack": result.rolled_back, "failed": result.failed,
                    }
                extra = {
                    "mode": mode["name"], "applied": result.applied, "skipped": result.skipped,
                    "undoReady": result.undo_ready,
                    "unknownBefore": sum(1 for row in rows if row.status == "change" and row.from_value is None),
                }
            elif action == "resetEqFlat":
                ch = int(msg["channel"])
                with self.service._ledger_lock:
                    self.service.begin_batch()
                    try:
                        for band in ("low", "low_mid", "hi_mid", "hi"):
                            self.service.set_eq_band(ch, band, 64, unit="raw")
                    finally:
                        self.service.end_batch()
            elif action == "setScribble":
                ch = int(msg["channel"])
                if 1 <= ch <= 7:
                    self._scribbles[ch] = {
                        "label": str(msg.get("label", ""))[:14] or LOGICAL_CHANNELS[ch].name,
                        "color": str(msg.get("color", "#38bdf8")),
                    }
            elif action == "setActiveBus":
                extra = {"activeBus": self.service.set_active_bus(str(msg.get("bus", "main")))}
            elif action == "setActiveView":
                extra = {"activeView": self.service.set_active_view(str(msg.get("view", "mixer")))}
            elif action == "setTransportMode":
                extra = {"transportMode": self.service.set_transport_mode(str(msg.get("mode", "usb_midi")))}
            elif action == "bleDumpTrigger":
                extra = {"triggered": self.service.request_ble_dump()}
            else:
                return 400, {"ok": False, "error": f"unsupported or blocked action: {action!r}"}
        except Exception as exc:
            return 400, {"ok": False, "error": str(exc)}
        finally:
            if getattr(self._local, "in_dispatch", False):
                try:
                    self.service._notify_listeners("__changed__", None)
                finally:
                    self._local.in_dispatch = False

        with self._scene_lock:
            if action in ("captureScene", "recallScene"):
                # A partial recall (WHAT TO LOAD) leaves the rest of the mix as it was.
                scope = msg.get("scope") if action == "recallScene" else None
                partial = bool(scope) and not set(RECALL_SCOPES) <= {str(x).upper() for x in scope}
                self._current_scene = str(msg["name"])
                self._scene_edited = partial
            elif action in _MIX_ACTIONS and self._current_scene is not None:
                self._scene_edited = True
        # "tx" tells every client which strip a command went to, for the TX lamp.
        self.broadcast({
            "type": "tx",
            "action": action,
            "channel": msg.get("channel"),
            "bus": msg.get("bus"),
            "target": msg.get("target"),
            "clientId": msg.get("clientId"),
        })
        return 200, {"ok": True, "action": action, **extra}


def main(argv: Optional[list[str]] = None) -> int:
    """Run standalone headless FLOW 8 LAN Remote Hub with auto-reconnect.

    Pass --no-meters to skip the USB audio meter stream.
    """
    import sys

    from flow8.audio_meter import Flow8AudioMeter

    args = sys.argv[1:] if argv is None else argv
    service = Flow8Service(auto_connect=True)
    library = default_library_path()
    if "--library" in args and args.index("--library") + 1 < len(args):
        library = Path(args[args.index("--library") + 1])
    hub = Flow8LanHub(service, port=DEFAULT_LAN_PORT, library_path=library)
    hub.start()
    meter = None if "--no-meters" in args else Flow8AudioMeter(hub.publish_meters, hub.set_meter_status)
    print(f"FLOW 8 LAN Remote Hub active (MIDI connected={service.is_connected})")
    for url in hub.lan_urls():
        print(f"  Mobile URL: {url}")
    try:
        while True:
            if service.is_connected:
                service.check_connection_health()
            else:
                service.connect()
            if meter is not None:
                meter.ensure_running()
            time.sleep(3.0)
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