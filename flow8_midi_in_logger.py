#!/usr/bin/env python3
"""
FLOW 8 MIDI IN Staged Capture & Diagnostic Logger.
Phase 2B — Physical MIDI IN Verification.
Strictly READ-ONLY: Never sends MIDI OUT or parameter writes.
"""

import os
import sys
import time
import argparse
from datetime import datetime
from flow8.midi_in import Flow8MidiIn

class Flow8MidiInLogger:
    def __init__(self, log_path="FLOW8_PHASE2B_RAW_MIDI_LOG.md"):
        self.listener = Flow8MidiIn()
        self.log_path = log_path
        self.captured_events = []

    def handle_event(self, event):
        self.captured_events.append(event)
        s = event['status']
        ch = event['channel']
        b1 = event['data1']
        b2 = event['data2']
        ts = event['timestamp']
        print(f"[{ts}] << CAPTURED MIDI IN: Status=0x{s:02X} (Ch {ch:02d}), Data1=0x{b1:02X} ({b1:03d}), Data2=0x{b2:02X} ({b2:03d})")

    def run_stage(self, stage_name: str, duration_sec: float = 8.0):
        print(f"\n========================================================")
        print(f"STAGE: {stage_name}")
        print(f"Listening on 'FLOW 8 MIDI IN' for {duration_sec} seconds...")
        print(f"========================================================")
        
        self.listener.register_callback(self.handle_event)
        stage_start_count = len(self.captured_events)
        
        with self.listener:
            t_end = time.time() + duration_sec
            while time.time() < t_end:
                time.sleep(0.1)

        stage_events = self.captured_events[stage_start_count:]
        print(f"Stage '{stage_name}' completed. Captured {len(stage_events)} events.")
        return stage_events

    def write_report(self, stage_results: dict):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("# FLOW 8 Phase 2B Raw MIDI IN Log\n")
            f.write(f"**Target:** Behringer FLOW 8 Digital Mixer  \n")
            f.write(f"**Date:** {datetime.now().isoformat()}  \n")
            dev_id, dev_name = self.listener.device_info
            f.write(f"**Endpoint:** `{self.listener._target_name}` (ID: {self.listener.find_device_id()})  \n")
            f.write(f"**Total Events Captured:** {len(self.captured_events)}  \n\n")
            f.write("---\n\n")

            f.write("## 1. Staged Execution Summary\n\n")
            f.write("| Stage / Physical Action | Duration | Events Captured | Detected Parameters |\n")
            f.write("|---|---|---|---|\n")
            for name, events in stage_results.items():
                params_str = ", ".join(set(f"Ch {e['channel']} CC {e['data1']}" for e in events)) if events else "None"
                f.write(f"| {name} | Duration logged | {len(events)} | {params_str} |\n")

            f.write("\n---\n\n")
            f.write("## 2. Chronological Raw Event Stream\n\n")
            if not self.captured_events:
                f.write("> [!NOTE]\n")
                f.write("> **Zero MIDI IN events detected across all listening windows.**  \n")
                f.write("> The FLOW 8 USB MIDI interface is open and operational, but no telemetry packets were emitted by the physical hardware during these stages.\n")
            else:
                f.write("| Index | Timestamp | Driver TS (ms) | Status Byte | Channel | Data 1 (CC/Note) | Data 2 (Value) |\n")
                f.write("|---|---|---|---|---|---|---|\n")
                for idx, e in enumerate(self.captured_events, 1):
                    f.write(f"| {idx} | {e['timestamp']} | {e['driver_ts_ms']} | `0x{e['status']:02X}` | {e['channel']} | `0x{e['data1']:02X} ({e['data1']})` | `0x{e['data2']:02X} ({e['data2']})` |\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FLOW 8 MIDI IN Logger")
    parser.add_argument("--duration", type=float, default=5.0, help="Listening duration per stage in seconds")
    args = parser.parse_args()

    logger = Flow8MidiInLogger()
    stages = [
        "Action 1: Channel 1 Physical Fader",
        "Action 2: Main Physical Fader",
        "Action 3: Channel 1 Pan",
        "Action 4: Channel 1 Mute"
    ]
    results = {}
    for st in stages:
        evs = logger.run_stage(st, duration_sec=args.duration)
        results[st] = evs
        time.sleep(0.5)

    logger.write_report(results)
    print(f"\nRaw log written to: {logger.log_path}")
