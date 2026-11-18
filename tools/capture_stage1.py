"""Stage 1 visual verification (safe copy): drive the real Flow8App with an OFFLINE service and capture its window.

Capture = Win32 PrintWindow of the Tk top-level HWND, encoded to PNG with zlib. Never opens MIDI ports
and never sends +48V. Screenshots go to NEW uniquely named files in tools/output/stage1/ (or --out-dir):
earlier screenshots are never overwritten.

Run from the repository root:  python -m tools.capture_stage1 [--out-dir DIR]
"""
import argparse
import ctypes
import os
import struct
import sys
import zlib
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools._output import DEFAULT_OUTPUT_DIR, write_unique_bytes  # noqa: E402

SIZES = [(1600, 900), (1366, 768), (1280, 720)]


def png_bytes(w, h, bgra):
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

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))


def grab(root, out_dir, stem):
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    root.update_idletasks()
    root.update()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT
    bi = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, bi, 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, hdc)
    data = bytes(buf)
    distinct = len(set(data[i:i + 4] for i in range(0, len(data), 4 * 997)))
    if not ok or distinct < 8:
        raise RuntimeError(f"capture failed or blank (PrintWindow={ok}, distinct colours={distinct})")
    path = write_unique_bytes(out_dir, stem, ".png", png_bytes(w, h, data))
    print(f"{path}  {w}x{h}")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR / "stage1"))
    args = parser.parse_args(argv)
    from flow8.service import Flow8Service
    from flow8.ui.app import Flow8App
    from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget

    service = Flow8Service(auto_connect=False)       # offline: no port is opened
    app = Flow8App(service=service, show_placeholder=False, connect_hardware=False)
    root, console = app.root, app.mixer_console
    root.deiconify()
    root.lift()
    root.update()
    try:
        for w, h in SIZES:
            tag = f"{w}x{h}"
            root.geometry(f"{w}x{h}+0+0")
            root.update()
            console.clear_selection()
            root.update()
            grab(root, args.out_dir, f"{tag}_1_main")
            console.select_target(SelectionTarget.input(1))
            console.inspector.show_tab(ChannelDetailPanel.TAB_EQ)
            root.update()
            grab(root, args.out_dir, f"{tag}_2_inspector")
    finally:
        app.close()


if __name__ == "__main__":
    main()
