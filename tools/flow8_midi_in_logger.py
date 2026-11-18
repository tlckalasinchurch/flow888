#!/usr/bin/env python3
"""FLOW 8 MIDI IN staged capture logger (restricted copy, S1.2 G-07).

Strictly read-only toward the mixer: it never sends MIDI. Unlike the historical root script
`flow8_midi_in_logger.py` (kept unchanged as evidence), its report is written to a NEW uniquely
named file in `tools/output/` (or `--out-dir`) and never over an existing file.

Run from the repository root:  python -m tools.flow8_midi_in_logger [--duration 22.5] [--out-dir DIR]
"""
import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools._output import DEFAULT_OUTPUT_DIR, write_unique  # noqa: E402


class Flow8MidiInLogger:
    def __init__(self, listener=None, out_dir=None):
        if listener is None:
            from flow8.midi_in import Flow8MidiIn
            listener = Flow8MidiIn()
        self.listener = listener
        self.out_dir = out_dir if out_dir is not None else DEFAULT_OUTPUT_DIR
        self.captured_events = []

    def handle_event(self, event):
        self.captured_events.append(event)
        print(f"[{event['timestamp']}] << CAPTURED MIDI IN: Status=0x{event['status']:02X} "
              f"(Ch {event['channel']:02d}), Data1={event['data1']:03d}, Data2={event['data2']:03d}")

    def run_stage(self, stage_name, duration_sec=8.0):
        print(f"\nSTAGE: {stage_name}\nListening on 'FLOW 8 MIDI IN' for {duration_sec} seconds...")
        self.listener.register_callback(self.handle_event)
        start = len(self.captured_events)
        with self.listener:
            end = time.time() + duration_sec
            while time.time() < end:
                time.sleep(0.1)
        events = self.captured_events[start:]
        print(f"Stage '{stage_name}' completed. Captured {len(events)} events.")
        return events

    def write_report(self, stage_results):
        """Write a NEW uniquely named report and return its path."""
        _, dev_name = self.listener.device_info
        lines = ["# FLOW 8 MIDI IN capture (restricted logger)\n",
                 f"**Date:** {datetime.now().isoformat()}  \n",
                 f"**Endpoint:** `{self.listener._target_name}` (ID: {self.listener.find_device_id()})  \n",
                 f"**Total events captured:** {len(self.captured_events)}  \n\n",
                 "| Stage | Events |\n|---|---|\n"]
        for name, events in stage_results.items():
            lines.append(f"| {name} | {len(events)} |\n")
        lines.append("\n## Events\n\n")
        if not self.captured_events:
            lines.append("Zero MIDI IN events were captured.\n")
        else:
            lines.append("| # | Timestamp | Status | Channel | Data 1 | Data 2 |\n|---|---|---|---|---|---|\n")
            for i, e in enumerate(self.captured_events, 1):
                lines.append(f"| {i} | {e['timestamp']} | `0x{e['status']:02X}` | {e['channel']} | {e['data1']} | {e['data2']} |\n")
        return write_unique(self.out_dir, "midi_in_capture", ".md", "".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description="FLOW 8 MIDI IN logger (read-only, restricted)")
    parser.add_argument("--duration", type=float, default=5.0, help="listening seconds per stage")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    logger = Flow8MidiInLogger(out_dir=args.out_dir)
    stages = ["Action 1: Channel 1 Physical Fader", "Action 2: Main Physical Fader",
              "Action 3: Channel 1 Pan", "Action 4: Channel 1 Mute"]
    results = {name: logger.run_stage(name, args.duration) for name in stages}
    print("Report written to:", logger.write_report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
