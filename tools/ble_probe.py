"""Read-only BLE discovery, GATT enumeration, and passive notify capture for Behringer FLOW 8.

Never writes to any GATT characteristic and never opens repository files in write/append mode.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
from typing import Any

FLOW8_SERVICE_UUID = "14839ad4-8d7e-415c-9a42-167340cf2339"
FLOW8_DATA_CHAR_UUID = "0034594a-a8e7-4b1a-a6b1-cd5243059a57"


def _find_flow8_match(discovered: dict[str, tuple[Any, Any]], target_filter: str) -> Any | None:
    flt = target_filter.lower()
    for _addr, (dev, adv) in discovered.items():
        name = (dev.name or adv.local_name or "").lower()
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        if FLOW8_SERVICE_UUID in uuids or flt in name or "behringer" in name:
            return dev
    return None


def _format_diff(prev: bytes | None, curr: bytes) -> str:
    if prev is None:
        return "initial"
    if len(prev) != len(curr):
        return f"len {len(prev)}->{len(curr)}"
    diffs = [f"[{i}]:{prev[i]:02x}->{curr[i]:02x}" for i in range(len(curr)) if prev[i] != curr[i]]
    return " ".join(diffs) if diffs else "identical"


async def _scan_and_inspect(scan_seconds: float, target_filter: str, listen_notify: bool, listen_seconds: float) -> int:
    from bleak import BleakClient, BleakScanner

    print(f"Scanning BLE advertisements for {scan_seconds:.1f}s...")
    discovered = await BleakScanner.discover(timeout=scan_seconds, return_adv=True)

    named: list[tuple[Any, Any]] = []
    for _addr, (dev, adv) in discovered.items():
        name = dev.name or adv.local_name or ""
        if name:
            named.append((dev, adv))

    print(f"Discovered {len(discovered)} BLE device(s) ({len(named)} named):")
    for dev, adv in sorted(named, key=lambda item: -(item[1].rssi or -999)):
        name = dev.name or adv.local_name or "<unnamed>"
        uuids = ", ".join(adv.service_uuids or []) or "-"
        print(f"  - {name!r} [{dev.address}] RSSI={adv.rssi} services=[{uuids}]")

    target_dev = _find_flow8_match(discovered, target_filter)
    if target_dev is None:
        print(
            "\nNo FLOW 8 BLE peripheral found advertising.\n"
            "Ensure the official phone app is disconnected and Bluetooth/pairing on the FLOW 8 is active."
        )
        return 0

    print(f"\nConnecting read-only to {target_dev.name!r} [{target_dev.address}]...")
    async with BleakClient(target_dev.address, timeout=12.0, pair=True) as client:
        print(f"Connected: {client.is_connected}")
        if not listen_notify:
            for svc in client.services:
                print(f"\n[Service] {svc.uuid} ({svc.description}) handle={svc.handle}")
                for char in svc.characteristics:
                    props = ",".join(char.properties)
                    print(f"  [Char] {char.uuid} handle={char.handle} props=[{props}] ({char.description})")
                    if "read" in char.properties:
                        try:
                            val = await client.read_gatt_char(char.uuid)
                            print(f"    read -> {bytes(val)!r}")
                        except Exception as exc:
                            print(f"    read -> <error: {exc}>")
                    for desc in char.descriptors:
                        print(f"    [Desc] {desc.uuid} handle={desc.handle} ({desc.description})")
            return 0

        packets: list[bytes] = []
        prev_pkt: bytes | None = None

        def on_notify(_sender: Any, data: bytearray) -> None:
            nonlocal prev_pkt
            raw = bytes(data)
            packets.append(raw)
            ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            hex_str = " ".join(f"{b:02x}" for b in raw)
            diff_str = _format_diff(prev_pkt, raw)
            print(f"[{ts}] #{len(packets):03d} len={len(raw):2d} hex=[{hex_str}] diff=({diff_str})", flush=True)
            prev_pkt = raw

        print(f"Subscribing to notify on {FLOW8_DATA_CHAR_UUID} for {listen_seconds:.1f}s (no writes)...", flush=True)
        winrt_token = None
        char_obj = None
        try:
            await client.start_notify(FLOW8_DATA_CHAR_UUID, on_notify)
        except Exception as exc:
            char = client.services.get_characteristic(FLOW8_DATA_CHAR_UUID)
            if char is not None and hasattr(getattr(char, "obj", None), "add_value_changed"):
                print(f"start_notify skipped ({exc}); attaching WinRT ValueChanged listener directly (no CCCD)...", flush=True)
                from winrt.windows.storage.streams import DataReader

                char_obj = char.obj

                def _on_winrt_val(_sender: Any, args: Any) -> None:
                    buf = args.characteristic_value
                    reader = DataReader.from_buffer(buf)
                    raw = bytearray(buf.length)
                    reader.read_bytes(raw)
                    on_notify(_sender, raw)

                winrt_token = char_obj.add_value_changed(_on_winrt_val)
            else:
                raise

        await asyncio.sleep(listen_seconds)
        if winrt_token is not None and char_obj is not None:
            char_obj.remove_value_changed(winrt_token)
        else:
            await client.stop_notify(FLOW8_DATA_CHAR_UUID)
        print(f"\nCapture finished: {len(packets)} notification packet(s) received.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only FLOW 8 BLE discovery and passive notify probe.")
    parser.add_argument("--scan-seconds", type=float, default=5.0, help="BLE scan duration in seconds (default 5.0)")
    parser.add_argument("--filter", default="flow", help="Substring to match target BLE device name (default 'flow')")
    parser.add_argument("--listen-notify", action="store_true", help="Subscribe to vendor notify characteristic (read-only)")
    parser.add_argument("--seconds", type=float, default=20.0, help="Notify listen duration in seconds (default 20.0)")
    args = parser.parse_args(argv)
    return asyncio.run(_scan_and_inspect(args.scan_seconds, args.filter, args.listen_notify, args.seconds))


if __name__ == "__main__":
    raise SystemExit(main())
