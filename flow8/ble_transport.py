"""Bluetooth Low Energy (BLE) transport and packet codec for Behringer FLOW 8.

Implements the vendor GATT protocol documented in docs/product/REA_FLOW_MIX_SPEC.md
(service 14839ad4-8d7e-415c-9a42-167340cf2339, char 0034594a-a8e7-4b1a-a6b1-cd5243059a57).

All outbound commands remain subject to flow8/safety.py boundaries:
- Never sends +48V phantom power, analog preamp gain, or Program Change 16 reset.
- Clamps values to valid bounds and suppresses mixer command-echo loops.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

FLOW8_SERVICE_UUID = "14839ad4-8d7e-415c-9a42-167340cf2339"
FLOW8_DATA_CHAR_UUID = "0034594a-a8e7-4b1a-a6b1-cd5243059a57"

AUTH_PACKET = bytes.fromhex("3901fd062b0639f17fe7b7278b8f355a495c2a")
SESSION_START_PACKET = bytes.fromhex("370138")
CONFIG_REQUEST_PACKET = bytes.fromhex("070108")
DUMP_TRIGGER_PACKET = bytes.fromhex("4b014c")

PKT_PARAM_CMD = 0x06
PKT_CONFIG_REQ = 0x07
PKT_METERING = 0x22
PKT_PARAM_RESP = 0x25
PKT_SNAPSHOT_NAMES = 0x27
PKT_IDENTITY = 0x35
PKT_AUTH_ACK = 0x36
PKT_SESSION_START = 0x37
PKT_STATE_DUMP = 0x38
PKT_AUTH = 0x39
PKT_DUMP_TRIGGER = 0x4B

PARAM_FADER = 0x0F
ECHO_SUPPRESS_WINDOW_S = 0.50


def ble_checksum(body: bytes) -> int:
    """Return the 8-bit modular sum checksum over *body*."""
    return sum(body) & 0xFF


def build_ble_packet(pkt_type: int, payload: bytes = b"", version: int = 0x01) -> bytes:
    """Build a framed FLOW 8 BLE packet: [type, version, *payload, checksum]."""
    body = bytes([pkt_type & 0xFF, version & 0xFF]) + payload
    return body + bytes([ble_checksum(body)])


def verify_ble_packet(packet: bytes) -> bool:
    """Verify minimum packet length (3 bytes) and trailing modular checksum."""
    if len(packet) < 3:
        return False
    return ble_checksum(packet[:-1]) == packet[-1]


def raw_midi_to_ble_byte(raw_midi: int) -> int:
    """Scale 7-bit MIDI (0..127) to 8-bit BLE value (0..255)."""
    clamped = max(0, min(127, int(raw_midi)))
    return max(0, min(255, round((clamped / 127.0) * 255.0)))


def ble_byte_to_raw_midi(ble_val: int) -> int:
    """Scale 8-bit BLE value (0..255) to 7-bit MIDI (0..127)."""
    clamped = max(0, min(255, int(ble_val)))
    return max(0, min(127, round((clamped / 255.0) * 127.0)))


def encode_fader_command(channel: int, raw_midi: int) -> bytes:
    """Encode a verified Type 0x06 fader write packet for input channels 1..6.

    Channels 1..6 correspond to BLE channel bytes 0x01..0x06. Bus/master BLE
    addresses are not confirmed and are refused here.
    """
    ch = int(channel)
    if not (1 <= ch <= 6):
        raise ValueError(f"BLE fader command supports channels 1..6 only (got {channel})")
    val = raw_midi_to_ble_byte(raw_midi)
    return build_ble_packet(PKT_PARAM_CMD, bytes([ch, PARAM_FADER, val]))


def parse_snapshot_names(packet: bytes) -> list[Optional[str]]:
    """Decode Type 0x27 snapshot names response into a list of up to 15 slot names."""
    if len(packet) < 3 or packet[0] != PKT_SNAPSHOT_NAMES:
        return []
    payload = packet[2:-1]
    names: list[Optional[str]] = []
    pos = 0
    while pos < len(payload) and len(names) < 15:
        length = payload[pos]
        pos += 1
        if length == 0:
            names.append(None)
        elif pos + length <= len(payload):
            text = payload[pos : pos + length].decode("utf-8", errors="replace").strip()
            names.append(text or None)
            pos += length
        else:
            break
    return names


@dataclass(frozen=True)
class BleEvent:
    """Decoded notification event from FLOW 8 BLE characteristic 0034594a-..."""

    pkt_type: int
    raw: bytes
    channel: Optional[int] = None
    param_id: Optional[int] = None
    raw_midi: Optional[int] = None
    snapshot_names: Optional[list[Optional[str]]] = None


def decode_ble_notification(packet: bytes) -> Optional[BleEvent]:
    """Decode an incoming notification packet from FLOW 8 LE."""
    if len(packet) < 3:
        return None
    pkt_type = packet[0]
    if pkt_type == PKT_PARAM_CMD and len(packet) >= 6 and verify_ble_packet(packet):
        ch = packet[2]
        param = packet[3]
        val = packet[4]
        raw_midi = ble_byte_to_raw_midi(val) if param == PARAM_FADER else None
        return BleEvent(
            pkt_type=pkt_type,
            raw=packet,
            channel=ch,
            param_id=param,
            raw_midi=raw_midi,
        )
    if pkt_type == PKT_SNAPSHOT_NAMES:
        return BleEvent(
            pkt_type=pkt_type,
            raw=packet,
            snapshot_names=parse_snapshot_names(packet),
        )
    return BleEvent(pkt_type=pkt_type, raw=packet)


class BleTransport:
    """Background bleak BLE transport for FLOW 8 LE with echo-loop suppression."""

    def __init__(
        self,
        on_parameter: Optional[Callable[[str, int], None]] = None,
        on_snapshot_names: Optional[Callable[[list[Optional[str]]], None]] = None,
        on_status: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self._on_parameter = on_parameter
        self._on_snapshot_names = on_snapshot_names
        self._on_status = on_status

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._client: Any = None
        self._connected = False
        self._authenticated = False
        self._device_name: Optional[str] = None
        self._device_address: Optional[str] = None
        self._last_error: Optional[str] = None
        self._packets_rx = 0
        self._packets_tx = 0
        self._recent_echoes: dict[tuple[int, int, int], float] = {}
        self._snapshot_names: list[Optional[str]] = []

    @property
    def is_connected(self) -> bool:
        return self._connected and self._authenticated

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "connected": self._connected,
                "authenticated": self._authenticated,
                "device": self._device_name,
                "address": self._device_address,
                "packetsRx": self._packets_rx,
                "packetsTx": self._packets_tx,
                "snapshotNames": list(self._snapshot_names),
                "error": self._last_error,
            }

    def _emit_status(self) -> None:
        if self._on_status is not None:
            try:
                self._on_status(self.status_snapshot())
            except Exception:
                pass

    def start(self) -> bool:
        """Start the background BLE worker thread. Returns True if started."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
            self._last_error = None
            ready = threading.Event()
            self._thread = threading.Thread(
                target=self._run_worker, args=(ready,), name="flow8-ble", daemon=True
            )
            self._thread.start()
        ready.wait(timeout=3.0)
        return True

    def stop(self) -> None:
        """Disconnect and stop the background BLE worker thread."""
        loop = self._loop
        stop_ev = self._stop_event
        if loop is not None and stop_ev is not None and not loop.is_closed():
            loop.call_soon_threadsafe(stop_ev.set)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=4.0)
        with self._lock:
            self._connected = False
            self._authenticated = False
            self._client = None
            self._thread = None
        self._emit_status()

    def send_fader(self, channel: int, raw_midi: int) -> bool:
        """Send a Type 0x06 fader write over BLE if connected and authenticated."""
        if not self.is_connected or self._loop is None or self._client is None:
            return False
        pkt = encode_fader_command(channel, raw_midi)
        val_byte = pkt[4]
        with self._lock:
            self._recent_echoes[(int(channel), PARAM_FADER, val_byte)] = time.monotonic()
        fut = asyncio.run_coroutine_threadsafe(self._write_packet(pkt), self._loop)
        try:
            return bool(fut.result(timeout=2.0))
        except Exception as exc:
            logger.warning("BLE write failed: %s", exc)
            return False

    def request_dump_trigger(self) -> bool:
        """Send Type 0x4B dump trigger so FLOW 8 emits its 3068-byte SysEx state dump."""
        if not self.is_connected or self._loop is None or self._client is None:
            return False
        fut = asyncio.run_coroutine_threadsafe(self._write_packet(DUMP_TRIGGER_PACKET), self._loop)
        try:
            return bool(fut.result(timeout=2.0))
        except Exception as exc:
            logger.warning("BLE dump trigger failed: %s", exc)
            return False

    async def _write_packet(self, payload: bytes) -> bool:
        client = self._client
        if client is None or not getattr(client, "is_connected", False):
            return False
        await client.write_gatt_char(FLOW8_DATA_CHAR_UUID, payload, response=True)
        with self._lock:
            self._packets_tx += 1
        return True

    def _handle_notification(self, raw: bytes) -> None:
        with self._lock:
            self._packets_rx += 1
        ev = decode_ble_notification(raw)
        if ev is None:
            return
        if ev.pkt_type == PKT_AUTH_ACK:
            with self._lock:
                self._authenticated = True
            self._emit_status()
            return
        if ev.pkt_type == PKT_SNAPSHOT_NAMES and ev.snapshot_names is not None:
            with self._lock:
                self._snapshot_names = list(ev.snapshot_names)
            if self._on_snapshot_names is not None:
                self._on_snapshot_names(ev.snapshot_names)
            self._emit_status()
            return
        if ev.pkt_type == PKT_PARAM_CMD and ev.channel is not None and ev.param_id == PARAM_FADER and ev.raw_midi is not None:
            val_byte = raw[4]
            key = (ev.channel, ev.param_id, val_byte)
            now = time.monotonic()
            with self._lock:
                sent_at = self._recent_echoes.get(key)
                if sent_at is not None and (now - sent_at) <= ECHO_SUPPRESS_WINDOW_S:
                    del self._recent_echoes[key]
                    return
            if 1 <= ev.channel <= 6 and self._on_parameter is not None:
                self._on_parameter(f"ch{ev.channel}.fader", ev.raw_midi)

    def _run_worker(self, ready: threading.Event) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        ready.set()
        try:
            loop.run_until_complete(self._ble_session())
        finally:
            loop.close()

    async def _ble_session(self) -> None:
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError as exc:
            with self._lock:
                self._last_error = f"bleak not installed: {exc}"
            self._emit_status()
            return

        stop_ev = self._stop_event
        assert stop_ev is not None

        while not stop_ev.is_set():
            try:
                discovered = await BleakScanner.discover(timeout=5.0, return_adv=True)
                target = None
                for _addr, (dev, adv) in discovered.items():
                    name = (dev.name or adv.local_name or "").lower()
                    uuids = [u.lower() for u in (adv.service_uuids or [])]
                    if FLOW8_SERVICE_UUID in uuids or "flow" in name:
                        target = dev
                        break
                if target is None:
                    with self._lock:
                        self._last_error = "FLOW 8 LE not advertising"
                    self._emit_status()
                    await asyncio.sleep(2.0)
                    continue

                async with BleakClient(target.address, timeout=12.0) as client:
                    self._client = client
                    with self._lock:
                        self._connected = True
                        self._device_name = target.name or "FLOW 8 LE"
                        self._device_address = target.address
                        self._last_error = None

                    winrt_token = None
                    char_obj = None
                    try:
                        await client.start_notify(
                            FLOW8_DATA_CHAR_UUID, lambda _s, d: self._handle_notification(bytes(d))
                        )
                    except Exception:
                        char = client.services.get_characteristic(FLOW8_DATA_CHAR_UUID)
                        if char is not None and hasattr(getattr(char, "obj", None), "add_value_changed"):
                            from winrt.windows.storage.streams import DataReader

                            char_obj = char.obj

                            def _on_winrt(_sender: Any, args: Any) -> None:
                                buf = args.characteristic_value
                                reader = DataReader.from_buffer(buf)
                                raw = bytearray(buf.length)
                                reader.read_bytes(raw)
                                self._handle_notification(bytes(raw))

                            winrt_token = char_obj.add_value_changed(_on_winrt)
                        else:
                            raise

                    # Handshake: Auth (0x39) -> Session Start (0x37) -> Config Request (0x07) -> Dump Trigger (0x4B)
                    await self._write_packet(AUTH_PACKET)
                    await asyncio.sleep(0.3)
                    with self._lock:
                        # Mark authenticated after auth write completes (0x36 ack also confirms)
                        self._authenticated = True
                    self._emit_status()
                    await self._write_packet(SESSION_START_PACKET)
                    await asyncio.sleep(0.5)
                    await self._write_packet(CONFIG_REQUEST_PACKET)
                    await asyncio.sleep(0.2)
                    await self._write_packet(DUMP_TRIGGER_PACKET)

                    while not stop_ev.is_set() and client.is_connected:
                        await asyncio.sleep(0.5)

                    if winrt_token is not None and char_obj is not None:
                        char_obj.remove_value_changed(winrt_token)
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
            finally:
                with self._lock:
                    self._connected = False
                    self._authenticated = False
                    self._client = None
                self._emit_status()
                if not stop_ev.is_set():
                    await asyncio.sleep(2.0)
