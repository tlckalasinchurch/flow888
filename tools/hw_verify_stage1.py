"""Stage 1 physical-hardware capture (safe copy). Needs the mixer connected; NOT used by any test.

  python -m tools.hw_verify_stage1 d01 90    passive window: sends NO MIDI, records what arrives and the UI changes

Differences from docs/audit/stage1_screenshots/hw_verify_stage1.py (kept unchanged): the event log and the
screenshots are written to NEW uniquely named files in tools/output/hw_stage1/ (or HW_OUT via --out-dir), never
over an existing file; modes that send DSP commands (d02, d05) were removed, so this copy cannot change the mix.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools._output import DEFAULT_OUTPUT_DIR, write_unique  # noqa: E402
from tools import capture_stage1 as cap  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["d01"])
    parser.add_argument("seconds", type=float, nargs="?", default=60)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR / "hw_stage1"))
    args = parser.parse_args(argv)
    from flow8.service import Flow8Service
    from flow8.ui.app import Flow8App

    t0 = time.time()
    events = []

    def rec(kind, **kw):
        kw.update(kind=kind, t=round(time.time() - t0, 3), wall=time.strftime("%H:%M:%S"))
        events.append(json.dumps(kw, default=str))

    service = Flow8Service(auto_connect=False)
    original = service._on_midi_in_event
    service._on_midi_in_event = lambda e: (rec("midi_in_raw", **{k: e.get(k) for k in ("status", "channel", "data1", "data2")}), original(e))[1]
    app = Flow8App(service=service, show_placeholder=False, connect_hardware=False)
    root, console = app.root, app.mixer_console
    try:
        root.deiconify()
        root.geometry("1366x768+0+0")
        root.update()
        ok = service.connect()
        rec("connect", ok=ok, error=service.connection_error, listening=service.midi_in_listening)
        cap.grab(root, args.out_dir, "d01_before")
        end = time.time() + args.seconds
        while time.time() < end:
            root.update()
            time.sleep(0.02)
        cap.grab(root, args.out_dir, "d01_after")
    finally:
        rec("done")
        print("Event log:", write_unique(args.out_dir, f"{args.mode}_events", ".jsonl", "\n".join(events) + "\n"))
        app.close()


if __name__ == "__main__":
    main()
