"""Clean-room Bluetooth HCI snoop (btsnoop) ATT parser for FLOW 8 BLE analysis.

Reads a raw `btsnoop_hci.log` or an Android `bugreport*.zip` containing `btsnoop_hci.log`,
extracts HCI ACL Data (0x02) -> L2CAP ATT (CID 0x0004) frames, and prints ATT Write
Requests/Commands (0x12 / 0x52) and Handle Value Notifications (0x1B) for the target
attribute handle (default 0x000a / 0x000b).

Strictly read-only: never modifies files and never writes to any BLE device.
"""

from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path
from typing import Iterator

BTSNOOP_MAGIC = b"btsnoop\x00"
ATT_CID = 0x0004
ATT_OPCODES = {
    0x12: "WRITE_REQ",
    0x13: "WRITE_RSP",
    0x52: "WRITE_CMD",
    0x1B: "NOTIFY",
    0x1D: "INDICATE",
}


def _load_btsnoop_bytes(path: Path) -> bytes:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith("btsnoop_hci.log") or "btsnoop" in n.lower()]
            if not candidates:
                raise FileNotFoundError(f"No btsnoop log found inside {path}")
            return zf.read(candidates[0])
    return path.read_bytes()


def iter_att_frames(blob: bytes) -> Iterator[tuple[int, int, int, int, bytes]]:
    """Yield (pkt_index, direction_flags, opcode, att_handle, payload) from btsnoop bytes."""
    if not blob.startswith(BTSNOOP_MAGIC) or len(blob) < 16:
        raise ValueError("Input is not a valid btsnoop v1 file (missing 'btsnoop\\x00' header)")
    offset = 16
    pkt_idx = 0
    while offset + 24 <= len(blob):
        orig_len, incl_len, flags, _drops, _ts = struct.unpack(">IIIIQ", blob[offset : offset + 24])
        offset += 24
        pkt = blob[offset : offset + incl_len]
        offset += incl_len
        pkt_idx += 1
        if len(pkt) < 5:
            continue
        # H4 HCI packet type: 0x02 = ACL Data
        if pkt[0] != 0x02:
            continue
        acl_len = struct.unpack("<H", pkt[3:5])[0]
        acl_payload = pkt[5 : 5 + acl_len]
        if len(acl_payload) < 4:
            continue
        l2cap_len, cid = struct.unpack("<HH", acl_payload[:4])
        if cid != ATT_CID or len(acl_payload) < 4 + l2cap_len or l2cap_len < 3:
            continue
        att_pdu = acl_payload[4 : 4 + l2cap_len]
        opcode = att_pdu[0]
        if opcode in (0x12, 0x52, 0x1B, 0x1D):
            handle = struct.unpack("<H", att_pdu[1:3])[0]
            yield pkt_idx, flags, opcode, handle, att_pdu[3:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse ATT Write/Notify frames from a btsnoop_hci.log or bugreport zip.")
    parser.add_argument("log_path", type=Path, help="Path to btsnoop_hci.log or Android bugreport .zip")
    parser.add_argument("--handles", default="0x000a,0x000b", help="Comma-separated ATT handles to filter (default 0x000a,0x000b)")
    parser.add_argument("--all-handles", action="store_true", help="Show ATT Write/Notify frames for all handles")
    args = parser.parse_args(argv)

    target_handles = {int(h.strip(), 16) for h in args.handles.split(",") if h.strip()}
    blob = _load_btsnoop_bytes(args.log_path)

    count = 0
    for pkt_idx, flags, opcode, handle, payload in iter_att_frames(blob):
        if not args.all_handles and handle not in target_handles:
            continue
        count += 1
        direction = "RX(mixer->host)" if (flags & 0x01) else "TX(host->mixer)"
        op_name = ATT_OPCODES.get(opcode, f"0x{opcode:02x}")
        hex_str = " ".join(f"{b:02x}" for b in payload)
        print(f"#{pkt_idx:05d} {direction} {op_name:<9s} handle=0x{handle:04x} len={len(payload):3d} hex=[{hex_str}]")

    print(f"\nTotal matching ATT frames: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
