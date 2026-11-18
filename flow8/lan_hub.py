"""Wi-Fi / LAN Remote Hub (HTTP + SSE) for Behringer FLOW 8 Workstation.

Adapted from Flow8-Remote-Pro's multi-screen SSE architecture, but strictly
enforces flow888's command boundary and safety policy:
- Every control action routes through Flow8Service (and so Flow8CommandBoundary).
- Preamp gain (CC 8) and +48V Phantom Power ON (CC 12) are blocked over LAN.
- Reported state always includes explicit provenance (never fakes hardware sync).
"""

from __future__ import annotations

import http.server
import json
import logging
import queue
import re
import socket
import threading
import time
from pathlib import Path
from typing import Any, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.presets import list_channel_presets
from flow8.safety import BLOCKED_PARAMETER_TYPES
from flow8.service import MAIN_CHANNEL, Flow8Service
from flow8.state_model import ParameterProvenance

logger = logging.getLogger(__name__)

DEFAULT_LAN_PORT = 8844
WEB_UI_DIR = Path(__file__).resolve().parent / "web_ui"
FONT_PATH = re.compile(r"^/fonts/([a-z0-9-]+\.woff2)$")

# Meter frames: at most one SSE frame per interval; the feed counts as live
# while frames arrive within METER_STALE_S.
METER_MIN_INTERVAL_S = 1.0 / 30.0
METER_STALE_S = 2.0

# Actions that change the mix. After a scene recall, any of these marks the
# current scene as edited. Scene, scribble and preset-list actions do not.
_MIX_ACTIONS = frozenset({
    "setFader", "setPan", "setMute", "muteAll", "setBusFader", "setEqBand",
    "setLowCut", "setCompressor", "setSend", "undo", "redo", "applyPreset",
    "resetEqFlat",
})


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
    ) -> None:
        self.service = service
        self.host = host
        self._requested_port = port
        self._server: Optional[_ThreadedHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._sse_lock = threading.Lock()
        self._subscribers: list[tuple[queue.Queue[bytes], Optional[str]]] = []
        self._listening = False
        self._scribbles: dict[int, dict[str, str]] = {}
        self._scene_lock = threading.Lock()
        self._current_scene: Optional[str] = None
        self._scene_edited = False
        self._last_meter_frame = 0.0
        self._last_meter_sent = 0.0

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
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_asset(self, filename: str, content_type: str) -> None:
                asset_path = WEB_UI_DIR / filename
                if not asset_path.is_file():
                    self._send_json(404, {"error": f"missing asset: {filename}"})
                    return
                body = asset_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path == "/" or self.path.startswith("/index.html"):
                    self._send_asset("index.html", "text/html; charset=utf-8")
                    return
                if self.path == "/styles.css":
                    self._send_asset("styles.css", "text/css; charset=utf-8")
                    return
                if self.path == "/app.js":
                    self._send_asset("app.js", "application/javascript; charset=utf-8")
                    return
                font = FONT_PATH.match(self.path)
                if font:
                    self._send_asset(f"fonts/{font.group(1)}", "font/woff2")
                    return

                if self.path.startswith("/api/status"):
                    self._send_json(200, hub.status_snapshot())
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

                if self.path.startswith("/api/session"):
                    self._send_json(200, hub.session_snapshot())
                    return

                if self.path.startswith("/api/events"):
                    client_id = None
                    if "clientId=" in self.path:
                        client_id = self.path.split("clientId=")[1].split("&")[0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
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
                                pass
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
                    return

                self._send_json(404, {"error": "not found"})

            def do_POST(self) -> None:
                if self.path != "/api/action":
                    self._send_json(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", "0") or 0)
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

    def _on_service_event(self, param_id: str, value: Any) -> None:
        # The service reports a real parameter id only for values the mixer sent
        # over MIDI IN (hardware moves). "__name__" ids are internal state events.
        if param_id.startswith("__"):
            kind = "link" if param_id == "__reconcile__" else "state"
            self.broadcast({"type": kind})
            return
        with self._scene_lock:
            if self._current_scene is not None:
                self._scene_edited = True
        self.broadcast({"type": "rx", "paramId": param_id, "value": value})

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
        return True

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
                except Exception:
                    dead.append(item)
            for item in dead:
                if item in self._subscribers:
                    self._subscribers.remove(item)

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "midiConnected": self.service.is_connected,
            "midiOutOpen": self.service.midi_out_open,
            "midiInOpen": self.service.midi_in_open,
            "meterFeed": self.meter_feed_live,
            "lanUrls": self.lan_urls(),
            "port": self.port,
        }

    def _param_raw(self, param_id: str, default: Any) -> tuple[Any, str]:
        st = self.service.state_store.get_parameter(param_id)
        if st is None:
            return default, ParameterProvenance.UNSYNCED.value
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
            sends = {
                target: int(self._param_raw(f"ch{idx}.send_{target}", 0)[0])
                for target in ("mon1", "mon2", "fx1", "fx2")
            }
            low_cut = int(self._param_raw(f"ch{idx}.low_cut", 0)[0]) if idx <= 4 else 0
            comp = int(self._param_raw(f"ch{idx}.compressor", 0)[0]) if idx <= 4 else 0
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
                "lowCut": low_cut,
                "compressor": comp,
                "sends": sends,
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
        with self._scene_lock:
            current_scene, scene_edited = self._current_scene, self._scene_edited
        return {
            "midiConnected": self.service.is_connected,
            "midiOutOpen": self.service.midi_out_open,
            "midiInOpen": self.service.midi_in_open,
            "meterFeed": self.meter_feed_live,
            "currentScene": current_scene,
            "sceneEdited": scene_edited,
            "channels": channels,
            "buses": buses,
            "scenes": list(self.service.scenes.names()),
        }

    def dispatch_action(self, msg: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Execute a LAN action strictly through Flow8Service and safety rules."""
        action = str(msg.get("action", ""))

        # Safety blocks: never allow gain or +48V ON over LAN
        if action == "setGain" or "gain" in BLOCKED_PARAMETER_TYPES and action == "gain":
            return 403, {"ok": False, "error": "Preamp gain is blocked by safety policy (SR-05)."}
        if action in ("set48V", "setPhantom", "phantom"):
            return 403, {"ok": False, "error": "+48V phantom power requires explicit host confirmation dialog."}

        # A command sent while MIDI is closed would be recorded as "commanded" but
        # never reach the mixer. Reject it so the remote cannot show a false success.
        # Scribble labels stay local to the hub, so they stay allowed.
        if action != "setScribble" and not self.service.is_connected:
            return 503, {
                "ok": False,
                "code": "not_connected",
                "error": "Mixer is not connected. The command was not sent.",
            }

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
                self.service.recall_scene(str(msg["name"]))
            elif action == "applyPreset":
                ok = self.service.apply_channel_preset(
                    int(msg["channel"]), str(msg["presetId"]), preserve_levels=True
                )
                if not ok:
                    return 400, {"ok": False, "error": "invalid channel or preset"}
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
            else:
                return 400, {"ok": False, "error": f"unsupported or blocked action: {action!r}"}
        except Exception as exc:
            return 400, {"ok": False, "error": str(exc)}

        with self._scene_lock:
            if action in ("captureScene", "recallScene"):
                self._current_scene = str(msg["name"])
                self._scene_edited = False
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
        return 200, {"ok": True, "action": action}


def main() -> int:
    """Run standalone headless FLOW 8 LAN Remote Hub with auto-reconnect."""
    service = Flow8Service(auto_connect=True)
    hub = Flow8LanHub(service, port=DEFAULT_LAN_PORT)
    hub.start()
    print(f"FLOW 8 LAN Remote Hub active (MIDI connected={service.is_connected})")
    for url in hub.lan_urls():
        print(f"  Mobile URL: {url}")
    try:
        while True:
            if service.is_connected:
                service.check_connection_health()
            else:
                service.connect()
            time.sleep(3.0)
    except KeyboardInterrupt:
        pass
    finally:
        hub.stop()
        service.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
