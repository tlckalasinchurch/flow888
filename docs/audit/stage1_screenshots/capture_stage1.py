"""Stage 1 visual verification: drive the real Flow8App (offline service) and capture its window.

Capture = Win32 PrintWindow of the Tk top-level HWND, encoded to PNG with zlib (no Pillow).
Run from the repo root:  python docs/audit/stage1_screenshots/capture_stage1.py
Never opens MIDI ports and never sends +48V: the service is created with auto_connect=False.
"""
import ctypes
import os
import struct
import sys
import zlib
from ctypes import wintypes

sys.path.insert(0, os.getcwd())
from flow8.service import Flow8Service  # noqa: E402
from flow8.ui.app import Flow8App  # noqa: E402
from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
SIZES = [(1600, 900), (1366, 768), (1280, 720)]


def png(path, w, h, bgra):
    rows = bytearray()
    stride = w * 4
    for y in range(h):
        row = bgra[y * stride:(y + 1) * stride]
        rows.append(0)
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        rows += rgb

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))


def grab(root, path):
    root.update_idletasks(); root.update()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    rect = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetDC(0); mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h); gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT
    bi = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, bi, 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem); user32.ReleaseDC(0, hdc)
    data = bytes(buf)
    distinct = len(set(data[i:i + 4] for i in range(0, len(data), 4 * 997)))
    if not ok or distinct < 8:
        raise RuntimeError(f"capture failed or blank (PrintWindow={ok}, distinct colours={distinct})")
    png(path, w, h, data)
    print(f"{path}  {w}x{h}  distinct-sample-colours={distinct}")


def main():
    service = Flow8Service(auto_connect=False)
    app = Flow8App(service=service, show_placeholder=False, connect_hardware=False)
    root, console = app.root, app.mixer_console
    root.deiconify(); root.lift(); root.update()
    print("screen", root.winfo_screenwidth(), root.winfo_screenheight())
    for w, h in SIZES:
        tag = f"{w}x{h}"
        root.geometry(f"{w}x{h}+0+0"); root.update()
        console.clear_selection(); root.update()
        grab(root, f"{OUT}/{tag}_1_main.png")
        # commanded baseline first, so the preset/undo/redo have a known previous value
        for band in ("low", "low_mid", "hi_mid", "hi"):
            service.set_eq_band(1, band, 64, unit="raw")
        console.select_target(SelectionTarget.input(1))
        console.inspector.show_tab(ChannelDetailPanel.TAB_EQ); root.update()
        grab(root, f"{OUT}/{tag}_2_inspector.png")
        service.apply_channel_preset(1, "vocal-worship-ballad"); console._drain_ui_queue()
        grab(root, f"{OUT}/{tag}_3_preset.png")
        console.undo(); grab(root, f"{OUT}/{tag}_4_undo.png")
        console.redo(); grab(root, f"{OUT}/{tag}_5_redo.png")
        service.disconnect(); console._drain_ui_queue()
        grab(root, f"{OUT}/{tag}_6_reconnect_unsynced.png")
        service.ledger.clear()
    app.close()


if __name__ == "__main__":
    main()
