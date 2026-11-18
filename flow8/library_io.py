"""Behringer FLOW Mix Library (New_8.json) Export/Import & SysEx Snapshot Parser.

Adapted from Flow8-Remote-Pro (`default_library.json` & `flow8_sysex_parser.py`).
Import always dispatches through Flow8Service and never touches preamp gain or +48V.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any, Optional, Union

from flow8.parameter_mapping import (
    compressor_midi_to_percent,
    eq_midi_to_db,
    low_cut_midi_to_hz,
)
from flow8.service import Flow8Service

BEHRINGER_SYSEX_HEADER = bytes([0xF0, 0x00, 0x20, 0x32, 0x21, 0x00])
FLOW_MAGIC = b"FLOW"
_EQ_BANDS = ("low", "low_mid", "hi_mid", "hi")


def _known_raw(service: Flow8Service, param_id: str) -> Optional[int]:
    state = service.state_store.get_parameter(param_id)
    if state is None:
        return None
    raw = state.commanded_raw_midi
    if raw is None:
        raw = state.observed_raw_midi
    return int(raw) if raw is not None else None


def export_library_json(service: Flow8Service, path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """Export current known/commanded FLOW 8 channel & bus parameters in New_8.json format."""
    channels = []
    for ch in range(1, 8):
        eq_gains = []
        for band in _EQ_BANDS:
            raw = _known_raw(service, f"ch{ch}.eq_{band}")
            eq_gains.append(round(eq_midi_to_db(raw), 2) if raw is not None else 0.0)

        lc_raw = _known_raw(service, f"ch{ch}.low_cut") if ch <= 4 else None
        comp_raw = _known_raw(service, f"ch{ch}.compressor") if ch <= 4 else None
        fader_raw = _known_raw(service, f"ch{ch}.fader")
        pan_raw = _known_raw(service, f"ch{ch}.pan")
        mute_raw = _known_raw(service, f"ch{ch}.mute")

        sends = {}
        for target in ("mon1", "mon2", "fx1", "fx2"):
            s_raw = _known_raw(service, f"ch{ch}.send_{target}")
            sends[target] = s_raw if s_raw is not None else 0

        channels.append({
            "channel": ch,
            "fader": fader_raw,
            "pan": pan_raw,
            "mute": bool(mute_raw) if mute_raw is not None else None,
            "lowcutHz": round(low_cut_midi_to_hz(lc_raw), 1) if lc_raw is not None else None,
            "compressorPercent": round(compressor_midi_to_percent(comp_raw), 1) if comp_raw is not None else None,
            "peqGain": eq_gains,
            "sends": sends,
        })

    buses = {}
    for bus_id in ("main", "mon1", "mon2", "fx1", "fx2"):
        buses[bus_id] = {"fader": _known_raw(service, f"{bus_id}.fader")}

    payload = {
        "format": "flow8-library-v1",
        "channels": channels,
        "buses": buses,
    }
    if path is not None:
        out_path = Path(path)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def import_library_json(service: Flow8Service, source: Union[str, Path, dict[str, Any]]) -> dict[str, int]:
    """Import a New_8.json / flow8-library-v1 snapshot safely through Flow8Service.

    Preamp gain and +48V phantom power are never modified by library import.
    All changes are grouped into a single atomic undo batch.
    """
    if isinstance(source, (str, Path)):
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        data = dict(source)

    applied = 0
    skipped = 0

    with service._ledger_lock:
        service.begin_batch()
        try:
            for entry in data.get("channels", []):
                ch = int(entry.get("channel", 0))
                if not (1 <= ch <= 7):
                    skipped += 1
                    continue

                peq_gain = entry.get("peqGain")
                if isinstance(peq_gain, list):
                    for band, gain_db in zip(_EQ_BANDS, peq_gain):
                        if gain_db is not None:
                            service.set_eq_band(ch, band, float(gain_db), unit="dB")
                            applied += 1

                if ch <= 4:
                    lc = entry.get("lowcutHz")
                    if lc is not None:
                        service.set_low_cut(ch, float(lc), unit="Hz")
                        applied += 1
                    comp = entry.get("compressorPercent")
                    if comp is not None:
                        service.set_compressor(ch, float(comp), unit="%")
                        applied += 1

                if entry.get("pan") is not None:
                    service.set_pan(ch, int(entry["pan"]))
                    applied += 1
                if entry.get("mute") is not None:
                    service.set_mute(ch, bool(entry["mute"]))
                    applied += 1
                if entry.get("fader") is not None:
                    service.set_fader(ch, int(entry["fader"]))
                    applied += 1

                sends = entry.get("sends")
                if isinstance(sends, dict):
                    for target, val in sends.items():
                        if target in ("mon1", "mon2", "fx1", "fx2") and val is not None:
                            service.set_send(ch, target, int(val), unit="raw")
                            applied += 1

            buses = data.get("buses", {})
            if isinstance(buses, dict):
                for bus_id, bdata in buses.items():
                    if not isinstance(bdata, dict) or bdata.get("fader") is None:
                        continue
                    if bus_id == "main":
                        service.set_fader(8, int(bdata["fader"]))
                        applied += 1
                    elif bus_id in ("mon1", "mon2", "fx1", "fx2"):
                        service.set_bus_fader(bus_id, int(bdata["fader"]))
                        applied += 1
        finally:
            service.end_batch()

    return {"applied": applied, "skipped": skipped}


# ---------------------------------------------------------------------------
# SysEx Snapshot Encoder / Decoder (offline inspection)
# ---------------------------------------------------------------------------


def unpack_7bit_to_8bit(data_7bit: bytes) -> bytes:
    """Decode 7-bit MIDI SysEx payload into an 8-bit binary stream."""
    out = bytearray()
    shift = 0
    accum = 0
    for byte in data_7bit:
        accum |= (byte & 0x7F) << shift
        shift += 7
        if shift >= 8:
            out.append(accum & 0xFF)
            accum >>= 8
            shift -= 8
    return bytes(out)


def pack_8bit_to_7bit(data_8bit: bytes) -> bytes:
    """Encode an 8-bit binary stream into a 7-bit MIDI SysEx payload."""
    out = bytearray()
    accum = 0
    shift = 0
    for byte in data_8bit:
        accum |= byte << shift
        shift += 8
        while shift >= 7:
            out.append(accum & 0x7F)
            accum >>= 7
            shift -= 7
    if shift > 0:
        out.append(accum & 0x7F)
    return bytes(out)


def parse_dsp_snapshot(raw_payload: bytes) -> dict[str, Any]:
    """Parse an un-nibblized 8-bit FLOW 8 DSP snapshot payload and verify CRC-32."""
    if len(raw_payload) < 0x4E0 + 2600:
        raise ValueError(f"Payload too short: {len(raw_payload)} bytes (expected >= {0x4E0 + 2600})")

    magic = raw_payload[0x4D0:0x4D4]
    if magic != FLOW_MAGIC:
        raise ValueError(f"Invalid magic header: {magic!r}, expected {FLOW_MAGIC!r}")

    revision = struct.unpack("<I", raw_payload[0x4D4:0x4D8])[0]
    expected_crc = struct.unpack("<I", raw_payload[0x4D8:0x4DC])[0]
    dsp_block = raw_payload[0x4E0:0x4E0 + 2600]
    calc_crc = zlib.crc32(dsp_block) & 0xFFFFFFFF

    return {
        "magic": magic.decode("ascii"),
        "revision": revision,
        "crc32": hex(expected_crc),
        "calculated_crc32": hex(calc_crc),
        "crc_valid": expected_crc == calc_crc,
        "dsp_bytes": len(dsp_block),
    }


def parse_sysex_message(sysex_bytes: bytes) -> dict[str, Any]:
    """Strip F0 .. F7 Behringer FLOW 8 SysEx framing, unpack 7-bit payload, and parse."""
    if not sysex_bytes.startswith(BEHRINGER_SYSEX_HEADER) or not sysex_bytes.endswith(b"\xF7"):
        raise ValueError("Invalid Behringer FLOW 8 SysEx frame")
    body_7bit = sysex_bytes[len(BEHRINGER_SYSEX_HEADER):-1]
    raw_8bit = unpack_7bit_to_8bit(body_7bit)
    return parse_dsp_snapshot(raw_8bit)
