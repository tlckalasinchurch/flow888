"""Real input meters for the FLOW 8, measured from its USB capture stream.

The FLOW 8 sends no meter data over USB MIDI. In Recording Mode it streams its
inputs to the host as the 10-channel endpoint "Multi In 1-10"
(FLOW8_USB_AUDIO_CAPABILITIES.md, section 4). This module reads that stream,
measures peak and RMS per mixer strip, and hands the levels to a publisher
(normally ``Flow8LanHub.publish_meters``).

What the levels mean:
- ch1..ch6: the input signal after the preamp and before the fader
  (the capture is "pre-fader / post-preamp"). Moving a fader does not change
  these meters, as on a console's input meter.
- main: the Main L/R mix as the mixer sends it to USB.
- ch7 (USB/BT return) and the MON/FX buses are not in the capture stream, so
  they get no meter.

The audio callback only accumulates numbers. A separate thread reads and
publishes them, so publishing can never block the audio thread.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Capture channel (0-based) -> mixer strip, Recording Mode "Multi In 1-10".
# Stereo strips use the louder side, as a console's mono meter on a pair does.
CAPTURE_MAP_RECORDING: dict[str, tuple[int, ...]] = {
    "ch1": (0,),      # Mic 1
    "ch2": (1,),      # Mic 2
    "ch3": (2,),      # Mic/Line 3
    "ch4": (3,),      # Mic/Line 4
    "ch5": (4, 5),    # Line 5/6
    "ch6": (6, 7),    # Line 7/8
    "main": (8, 9),   # Main L/R
    # Single jacks, for the input meters on the I/O setup page.
    "in5": (4,),      # Line 5 (L)
    "in6": (5,),      # Line 6 (R / Hi-Z)
    "in7": (6,),      # Line 7 (L)
    "in8": (7,),      # Line 8 (R / Hi-Z)
}
# Streaming Mode exposes only the stereo main mix (2 channels).
CAPTURE_MAP_STREAMING: dict[str, tuple[int, ...]] = {"main": (0, 1)}

RECORDING_CHANNELS = 10
STREAMING_CHANNELS = 2
FLOOR_DB = -120.0
RMS_WINDOW_S = 0.3          # FLOW8_AUDIO_ENGINE_SPEC.md 2.3: 300 ms RMS
BLOCK_FRAMES = 512          # ~10.7 ms at 48 kHz
PUBLISH_HZ = 25.0           # below the hub's 30 frames/s limit
RETRY_INTERVAL_S = 5.0
FRAME_TIMEOUT_S = 2.0     # active stream with no frames for this long = lost device

MeterLevels = dict[str, dict[str, float]]


def to_dbfs(linear: float) -> float:
    """Linear full-scale amplitude (1.0 = 0 dBFS) to dBFS, floored at -120."""
    if linear <= 1e-6:
        return FLOOR_DB
    return max(FLOOR_DB, 20.0 * math.log10(linear))


class LevelMeter:
    """Peak and RMS per strip from blocks of float samples in [-1, 1].

    RMS uses exponential smoothing with a 300 ms time constant. Peak is the
    largest sample since the last ``read()``, so a short transient between two
    reads is never lost.
    """

    def __init__(self, capture_map: Mapping[str, Sequence[int]], sample_rate: float,
                 rms_window_s: float = RMS_WINDOW_S) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        self._map = {k: tuple(v) for k, v in capture_map.items()}
        self._rate = float(sample_rate)
        self._window = float(rms_window_s)
        self._lock = threading.Lock()
        self._mean_square = {k: 0.0 for k in self._map}
        self._peak = {k: 0.0 for k in self._map}

    @property
    def strips(self) -> tuple[str, ...]:
        return tuple(self._map)

    def process(self, block: np.ndarray) -> None:
        """Add one block shaped (frames, channels). Safe to call from the audio thread."""
        if block.ndim != 2 or block.shape[0] == 0:
            return
        frames, channels = block.shape
        alpha = 1.0 - math.exp(-frames / (self._rate * self._window))
        abs_max = np.max(np.abs(block), axis=0)
        mean_sq = np.mean(np.square(block, dtype=np.float64), axis=0)
        with self._lock:
            for strip, chans in self._map.items():
                idx = [c for c in chans if c < channels]
                if not idx:
                    continue
                peak = float(np.max(abs_max[idx]))
                ms = float(np.max(mean_sq[idx]))
                self._mean_square[strip] += alpha * (ms - self._mean_square[strip])
                if peak > self._peak[strip]:
                    self._peak[strip] = peak

    def read(self) -> MeterLevels:
        """Return dBFS levels per strip and restart the peak window."""
        with self._lock:
            out = {
                strip: {
                    "peak": round(to_dbfs(self._peak[strip]), 1),
                    "rms": round(to_dbfs(math.sqrt(max(self._mean_square[strip], 0.0))), 1),
                }
                for strip in self._map
            }
            for strip in self._peak:
                self._peak[strip] = 0.0
        return out


@dataclass(frozen=True)
class CaptureDevice:
    index: int
    name: str
    host_api: str
    channels: int
    sample_rate: float
    mode: str  # "recording" or "streaming"

    @property
    def capture_map(self) -> dict[str, tuple[int, ...]]:
        return CAPTURE_MAP_RECORDING if self.mode == "recording" else CAPTURE_MAP_STREAMING


# Lower is better. WASAPI gives the multichannel endpoint; MME may cap channels.
_HOST_API_RANK = {"windows wasapi": 0, "asio": 1, "windows wdm-ks": 2, "core audio": 3, "alsa": 4}


def pick_capture_device(devices: Sequence[Mapping[str, Any]],
                        host_apis: Sequence[Mapping[str, Any]]) -> Optional[CaptureDevice]:
    """Choose the FLOW 8 capture endpoint from a PortAudio device list.

    Prefers the 10-channel Recording Mode endpoint ("Multi In 1-10"); falls back
    to a 2-channel FLOW 8 main mix (Streaming Mode). Returns None when no FLOW 8
    input is present.
    """
    def host_name(dev: Mapping[str, Any]) -> str:
        i = int(dev.get("hostapi", -1))
        return str(host_apis[i]["name"]) if 0 <= i < len(host_apis) else ""

    def is_flow8(dev: Mapping[str, Any]) -> bool:
        name = str(dev.get("name", "")).lower()
        return "flow 8" in name or "flow8" in name or "multi in 1-10" in name

    def rank(item: tuple[int, Mapping[str, Any]]) -> tuple[int, int]:
        i, dev = item
        return (_HOST_API_RANK.get(host_name(dev).lower(), 9), i)

    flow = [(i, d) for i, d in enumerate(devices) if is_flow8(d)]
    for wanted, mode in ((RECORDING_CHANNELS, "recording"), (STREAMING_CHANNELS, "streaming")):
        pool = [(i, d) for i, d in flow if int(d.get("max_input_channels", 0)) >= wanted]
        if mode == "streaming":
            # Streaming Mode has only the main mix; ignore single-input endpoints.
            pool = [(i, d) for i, d in pool if int(d.get("max_input_channels", 0)) < RECORDING_CHANNELS]
        if pool:
            i, d = sorted(pool, key=rank)[0]
            return CaptureDevice(
                index=i,
                name=str(d.get("name", "")),
                host_api=host_name(d),
                channels=wanted,
                sample_rate=float(d.get("default_samplerate") or 48000.0),
                mode=mode,
            )
    return None


class Flow8AudioMeter:
    """Open the FLOW 8 capture stream and publish meter levels.

    ``publish`` receives ``{strip: {"peak": dBFS, "rms": dBFS}}`` about 25 times
    per second. ``on_status`` receives a status dict whenever the state changes:
    ``{"state", "detail", "device", "mode"}`` with state one of
    ``unavailable`` (no audio library), ``no_device``, ``running``,
    ``error`` or ``stopped``.

    ``backend`` defaults to the ``sounddevice`` module, imported on first start.
    """

    def __init__(self, publish: Callable[[MeterLevels], Any],
                 on_status: Optional[Callable[[dict[str, Any]], Any]] = None,
                 backend: Any = None, publish_hz: float = PUBLISH_HZ,
                 frame_timeout_s: float = FRAME_TIMEOUT_S) -> None:
        self._publish = publish
        self._on_status = on_status
        self._backend = backend
        self._interval = 1.0 / publish_hz
        self._frame_timeout = float(frame_timeout_s)
        self._lock = threading.Lock()
        self._stream: Any = None
        self._meter: Optional[LevelMeter] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._last_attempt = -math.inf
        self._frames = 0                 # incremented from the audio thread
        self._last_frame_at = 0.0
        self.overflows = 0
        self._reset_stats()
        self.status: dict[str, Any] = {"state": "stopped", "detail": "Meters are off.", "device": None, "mode": None}

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def _reset_stats(self) -> None:
        # shortcut: plain counters updated without a lock from two threads; a torn
        # read is off by one sample, fine for diagnostics, not for accounting.
        self._frames = 0
        self.overflows = 0
        self._cb_total_s = 0.0
        self._cb_max_s = 0.0
        self._publish_count = 0
        self._publish_total_s = 0.0
        self._publish_max_s = 0.0

    def stats(self) -> dict[str, Any]:
        """Capture health since the stream started: callbacks, overflows, publish timing."""
        frames, published = self._frames, self._publish_count
        intervals = max(published - 1, 0)
        return {
            "frames": frames,
            "overflows": self.overflows,
            "callbackMaxMs": round(self._cb_max_s * 1000.0, 3),
            "callbackMeanMs": round(self._cb_total_s / frames * 1000.0, 3) if frames else 0.0,
            "publishCount": published,
            "publishIntervalMaxMs": round(self._publish_max_s * 1000.0, 3),
            "publishIntervalMeanMs": round(self._publish_total_s / intervals * 1000.0, 3) if intervals else 0.0,
        }

    def _set_status(self, state: str, detail: str, device: Optional[CaptureDevice] = None) -> None:
        self.status = {
            "state": state,
            "detail": detail,
            "device": device.name if device else None,
            "mode": device.mode if device else None,
        }
        if self._on_status is not None:
            try:
                self._on_status(dict(self.status))
            except Exception:  # never let a status listener stop metering
                logger.exception("meter status listener failed")

    def _load_backend(self) -> Any:
        if self._backend is None:
            import sounddevice  # noqa: PLC0415 - optional dependency, loaded on demand
            self._backend = sounddevice
        return self._backend

    def start(self) -> bool:
        """Try to open the capture stream. Returns True when meters run."""
        with self._lock:
            if self._running.is_set():
                return True
            self._last_attempt = time.monotonic()
            try:
                backend = self._load_backend()
            except (ImportError, OSError) as exc:
                self._set_status(
                    "unavailable",
                    f"Meters need the 'sounddevice' package and PortAudio ({exc}).",
                )
                return False
            try:
                device = pick_capture_device(list(backend.query_devices()), list(backend.query_hostapis()))
            except Exception as exc:
                self._set_status("error", f"Cannot list audio devices: {exc}")
                return False
            if device is None:
                self._set_status(
                    "no_device",
                    "No FLOW 8 audio input found. Connect the FLOW 8 by USB in Recording Mode.",
                )
                return False

            meter = LevelMeter(device.capture_map, device.sample_rate)

            def callback(indata, frames, time_info, status):  # audio thread
                t0 = time.perf_counter()
                if status:
                    self.overflows += 1
                self._last_frame_at = time.monotonic()
                meter.process(indata)
                spent = time.perf_counter() - t0
                self._cb_total_s += spent
                if spent > self._cb_max_s:
                    self._cb_max_s = spent
                self._frames += 1

            try:
                stream = backend.InputStream(
                    device=device.index,
                    channels=device.channels,
                    samplerate=device.sample_rate,
                    blocksize=BLOCK_FRAMES,
                    dtype="float32",
                    callback=callback,
                )
                stream.start()
            except Exception as exc:
                self._set_status("error", f"Cannot open {device.name}: {exc}", device)
                return False

            self._reset_stats()
            self._stream, self._meter = stream, meter
            self._last_frame_at = time.monotonic()
            self._running.set()
            self._thread = threading.Thread(target=self._publish_loop, name="flow8-meter-publish", daemon=True)
            self._thread.start()
            detail = (
                "Input meters from the FLOW 8 USB capture (before the fader)."
                if device.mode == "recording"
                else "Streaming Mode: only the Main L/R meter is available."
            )
            self._set_status("running", detail, device)
            return True

    def ensure_running(self) -> bool:
        """Start, or retry at most every 5 s. Call this from a periodic loop."""
        if self._running.is_set():
            return True
        if time.monotonic() - self._last_attempt < RETRY_INTERVAL_S:
            return False
        return self.start()

    def _publish_loop(self) -> None:
        last_frames = -1
        last_publish = 0.0
        while self._running.is_set():
            time.sleep(self._interval)
            stream, meter = self._stream, self._meter
            if stream is None or meter is None:
                break
            if not getattr(stream, "active", True):
                # Device unplugged or the driver stopped the stream.
                self._close(state="error", detail="The FLOW 8 audio stream stopped. Retrying.")
                break
            if self._frames == last_frames and time.monotonic() - self._last_frame_at > self._frame_timeout:
                # The endpoint stays "active" after some unplugs but delivers no
                # frames, so silence is treated as a lost device, not as -120 dBFS.
                self._close(
                    state="error",
                    detail="The FLOW 8 USB audio stream sends no frames. Retrying.",
                )
                break
            last_frames = self._frames
            try:
                self._publish(meter.read())
            except Exception:
                logger.exception("meter publish failed")
            now = time.perf_counter()
            if self._publish_count:
                gap = now - last_publish
                self._publish_total_s += gap
                if gap > self._publish_max_s:
                    self._publish_max_s = gap
            self._publish_count += 1
            last_publish = now

    def _close(self, state: str, detail: str) -> None:
        with self._lock:
            self._running.clear()
            stream, self._stream, self._meter = self._stream, None, None
        if stream is not None:
            for op in ("stop", "close"):
                try:
                    getattr(stream, op)()
                except Exception:
                    pass
        self._set_status(state, detail)

    def stop(self) -> None:
        """Stop metering and close the stream."""
        thread = self._thread
        self._close(state="stopped", detail="Meters are off.")
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None
