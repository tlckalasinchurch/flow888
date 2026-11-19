"""Transport router: single-writer policy for USB MIDI, BLE, and Hybrid control.

Sits between the command boundary (which owns safety + allowlist validation)
and the physical transports. One command is dispatched to exactly one
transport — never both.

Modes
-----
``usb_midi``  USB MIDI only. BLE is never used for control.
``ble``       BLE only, and only for parameters with verified BLE protocol
              evidence (input faders on logical strips 1-6, packet type
              ``0x06`` / param ``0x0F``). Every other allowlisted parameter is
              rejected explicitly — BLE is NOT a full MIDI replacement.
``hybrid``    Single-writer per command: BLE-capable parameters go over BLE
              while BLE is connected *and* authenticated, otherwise over USB;
              all other parameters go over USB. If a BLE write fails the
              command fails — it is never retried over USB, so a command can
              never be applied twice.

Dispatch contract (used by ``Flow8CommandBoundary``):
    dispatch(param_id, spec, raw_midi) -> Optional[str]
        returns "usb_midi" | "ble" when a transport accepted the command,
        returns None when no control transport is connected (offline accept —
        same semantics as the legacy USB-only path),
        raises Flow8CommandError on transport failure,
        raises Flow8CommandRejectedError when the mode cannot carry the param.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Callable, Dict, Optional

from .command_boundary import Flow8CommandError, Flow8CommandRejectedError

#: Logical channel strips (1..6) whose faders have verified BLE write evidence.
#: Strip 7 (USB/BT return) has no confirmed BLE channel address -> excluded.
BLE_FADER_STRIP_RE = re.compile(r"^ch([1-7])\.fader$")
BLE_FADER_STRIPS = frozenset(range(1, 7))

#: Honest per-mode capability summary, surfaced to the UI. BLE is deliberately
#: described as faders-only: the clean-room spec verifies type 0x06 param 0x0F
#: for channels 0x01..0x06 and nothing else for host->mixer writes.
TRANSPORT_FEATURES: Dict[str, Dict[str, Any]] = {
    "usb_midi": {
        "control": "USB MIDI (WinMM)",
        "commands": "All allowlisted parameters: faders, mute, pan/balance, EQ, sends, low cut, compressor, +48V (confirmed), scenes/undo.",
        "observations": "USB MIDI IN telemetry + USB audio meters (WASAPI).",
        "limits": "Requires the FLOW 8 USB cable; no wireless control.",
    },
    "ble": {
        "control": "Bluetooth LE (vendor GATT 0x14839ad4…)",
        "commands": "Input faders on strips 1-6 only (packet 0x06, param 0x0F). Mute, pan, EQ, sends, buses, +48V and all other parameters are rejected.",
        "observations": "BLE notifications (fader echoes, metering 0x22, snapshot names 0x27). The 3068-byte state dump is observed but NOT decoded.",
        "limits": "No USB required for faders; everything else needs USB MIDI.",
    },
    "hybrid": {
        "control": "BLE for strips 1-6 faders; USB MIDI for everything else (single writer per command).",
        "commands": "Same union as USB MIDI, but faders prefer BLE when it is connected and authenticated.",
        "observations": "USB MIDI IN telemetry, BLE notifications, and USB audio meters — all independent of the control writer.",
        "limits": "If BLE drops, faders fall back to USB MIDI; a command is never sent on both transports.",
    },
}


class TransportRouter:
    """Routes validated commands to exactly one control transport."""

    MODES = ("usb_midi", "ble", "hybrid")

    def __init__(
        self,
        midi_out: Any,
        ble_provider: Callable[[], Optional[Any]],
    ) -> None:
        self._midi_out = midi_out
        self._ble_provider = ble_provider
        self._lock = threading.Lock()
        self._mode = "usb_midi"

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str) -> str:
        m_key = str(mode or "usb_midi").lower()
        if m_key not in self.MODES:
            raise ValueError(f"Unsupported transport mode: {mode!r}")
        with self._lock:
            self._mode = m_key
        return m_key

    @staticmethod
    def ble_fader_strip(param_id: str) -> Optional[int]:
        """Logical strip index (1..6) when param_id is a BLE-capable fader, else None."""
        match = BLE_FADER_STRIP_RE.match(param_id)
        if match is None:
            return None
        strip = int(match.group(1))
        return strip if strip in BLE_FADER_STRIPS else None

    @classmethod
    def ble_capable(cls, param_id: str, spec: Optional[Dict[str, Any]] = None) -> bool:
        """True only for parameters with verified BLE write evidence."""
        if cls.ble_fader_strip(param_id) is None:
            return False
        if spec is not None and spec.get("type") != "fader":
            return False
        return True

    def supported_features(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """Capability summary for *mode* (defaults to the active mode)."""
        return dict(TRANSPORT_FEATURES.get(mode or self.mode, TRANSPORT_FEATURES["usb_midi"]))

    # -- dispatch ------------------------------------------------------------

    def dispatch(self, param_id: str, spec: Dict[str, Any], raw_midi: int) -> Optional[str]:
        """Send one validated command to exactly one transport.

        Returns the transport name ("usb_midi"/"ble") or None when offline.
        """
        mode = self.mode
        if mode == "usb_midi":
            return self._dispatch_usb(spec, raw_midi)
        if mode == "ble":
            if not self.ble_capable(param_id, spec):
                raise Flow8CommandRejectedError(
                    f"'{param_id}' is not supported over BLE. Verified BLE writes cover "
                    "input faders on strips 1-6 only (packet 0x06, param 0x0F); "
                    "use USB MIDI or Hybrid mode for this parameter."
                )
            return self._dispatch_ble(param_id, raw_midi)
        # hybrid: explicit single-writer policy per command.
        ble = self._ble()
        if self.ble_capable(param_id, spec) and ble is not None and ble.is_connected:
            return self._dispatch_ble(param_id, raw_midi)
        return self._dispatch_usb(spec, raw_midi)

    def _ble(self) -> Optional[Any]:
        try:
            return self._ble_provider()
        except Exception:
            return None

    def _dispatch_usb(self, spec: Dict[str, Any], raw_midi: int) -> Optional[str]:
        if not getattr(self._midi_out, "is_connected", False):
            return None
        # send_cc re-validates through safety.validate_outbound — the boundary
        # already ran authorize_command, and the phantom ON permit context is
        # held by the caller around this call.
        self._midi_out.send_cc(int(spec["channel"]), int(spec["cc"]), int(raw_midi))
        return "usb_midi"

    def _dispatch_ble(self, param_id: str, raw_midi: int) -> Optional[str]:
        ble = self._ble()
        if ble is None or not ble.is_connected:
            return None
        strip = self.ble_fader_strip(param_id)
        if strip is None:
            raise Flow8CommandRejectedError(
                f"'{param_id}' has no verified BLE write address."
            )
        try:
            accepted = ble.send_fader(strip, raw_midi)
        except Exception as exc:
            raise Flow8CommandError(
                f"BLE transport failed for '{param_id}': {exc}"
            ) from exc
        if not accepted:
            raise Flow8CommandError(
                f"BLE transport did not accept '{param_id}' (not connected or write failed)."
            )
        return "ble"
