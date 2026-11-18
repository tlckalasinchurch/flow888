#!/usr/bin/env python3
"""FLOW 8 USB MIDI test harness (restricted copy, S1.2 decision D4).

Differences from the historical root script `flow8_midi_harness.py` (kept unchanged as evidence):
  * Nothing is sent unless `--allow-write` is given (default: no MIDI, ports are not even opened).
  * Every message passes `flow8.safety.validate_outbound` first: control change only, allowlisted
    pairs only. Program Change (including the reset), Note, SysEx, gain and unauthorised +48V are refused.
  * Output goes to a NEW uniquely named file in `tools/output/` (or `--out-dir`); no existing file
    is ever opened for writing, and the historical evidence logs are never touched.

Run from the repository root:  python -m tools.flow8_midi_harness [--allow-write] [--out-dir DIR]
"""
import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flow8.safety import validate_outbound  # noqa: E402
from tools._output import DEFAULT_OUTPUT_DIR, write_unique  # noqa: E402

MMSYSERR_NOERROR = 0
MIM_DATA = 0x3C3
CALLBACK_FUNCTION = 0x00030000


class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.DWORD),
                ("szPname", wintypes.WCHAR * 32), ("dwSupport", wintypes.DWORD)]


class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.DWORD),
                ("szPname", wintypes.WCHAR * 32), ("wTechnology", wintypes.WORD), ("wVoices", wintypes.WORD),
                ("wNotes", wintypes.WORD), ("wChannelMask", wintypes.WORD), ("dwSupport", wintypes.DWORD)]


class Flow8MidiHarness:
    def __init__(self, log_path=None, winmm=None, allow_write=False, out_dir=None):
        # `winmm` is injectable so tests can use a mock driver; the real library is only loaded when needed.
        self.winmm = winmm if winmm is not None else ctypes.windll.winmm
        self.allow_write = bool(allow_write)
        self.out_dir = out_dir if out_dir is not None else DEFAULT_OUTPUT_DIR
        self.in_id = self.out_id = self.in_name = self.out_name = None
        self.h_in = wintypes.HANDLE()
        self.h_out = wintypes.HANDLE()
        self.rx_records = []
        self.tx_records = []
        self._cb_ref = None

    def find_endpoints(self):
        """Locate FLOW 8 MIDI IN and OUT devices (enumeration only)."""
        for i in range(self.winmm.midiInGetNumDevs()):
            caps = MIDIINCAPSW()
            if self.winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR \
                    and "FLOW 8" in caps.szPname:
                self.in_id, self.in_name = i, caps.szPname
        for i in range(self.winmm.midiOutGetNumDevs()):
            caps = MIDIOUTCAPSW()
            if self.winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR \
                    and "FLOW 8" in caps.szPname:
                self.out_id, self.out_name = i, caps.szPname
        return self.in_id is not None and self.out_id is not None

    def open(self):
        """Open the endpoints. Only used when `--allow-write` was given."""
        if not self.find_endpoints():
            raise RuntimeError("FLOW 8 MIDI endpoints not found in system enumeration.")
        proc_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
        self._cb_ref = proc_type(self._midi_in_callback)
        res = self.winmm.midiInOpen(ctypes.byref(self.h_in), self.in_id, self._cb_ref, 0, CALLBACK_FUNCTION)
        if res != MMSYSERR_NOERROR:
            raise RuntimeError(f"Failed to open MIDI IN {self.in_id}: error code {res}")
        res = self.winmm.midiOutOpen(ctypes.byref(self.h_out), self.out_id, 0, 0, 0)
        if res != MMSYSERR_NOERROR:
            self.winmm.midiInClose(self.h_in)
            raise RuntimeError(f"Failed to open MIDI OUT {self.out_id}: error code {res}")
        self.winmm.midiInStart(self.h_in)
        return True

    def close(self):
        if self.h_in:
            self.winmm.midiInStop(self.h_in)
            self.winmm.midiInReset(self.h_in)
            self.winmm.midiInClose(self.h_in)
            self.h_in = wintypes.HANDLE()
        if self.h_out:
            self.winmm.midiOutClose(self.h_out)
            self.h_out = wintypes.HANDLE()

    def _midi_in_callback(self, hMidiIn, wMsg, dwInstance, dwParam1, dwParam2):
        if wMsg == MIM_DATA:
            status, b1, b2 = dwParam1 & 0xFF, (dwParam1 >> 8) & 0xFF, (dwParam1 >> 16) & 0xFF
            self.rx_records.append({"timestamp": datetime.now().isoformat(), "driver_ts_ms": dwParam2,
                                    "status": status, "b1": b1, "b2": b2, "channel": (status & 0x0F) + 1})

    def send_short_msg(self, status, b1, b2, param_name=""):
        """Send one short message, but only if writes are allowed AND the safety policy accepts it."""
        if not self.allow_write:
            raise PermissionError("MIDI writes are disabled; pass --allow-write to send the listed safe messages.")
        validate_outbound(status, b1, b2)          # raises SafetyPolicyError before any driver call
        msg = (status & 0xFF) | ((b1 & 0xFF) << 8) | ((b2 & 0xFF) << 16)
        started = time.perf_counter()
        res = self.winmm.midiOutShortMsg(self.h_out, msg)
        self.tx_records.append({"timestamp": datetime.now().isoformat(), "status": status, "b1": b1, "b2": b2,
                                "raw_dword": f"0x{msg:06X}", "channel": (status & 0x0F) + 1, "param": param_name,
                                "result": res, "latency_us": round((time.perf_counter() - started) * 1e6, 2)})
        return res == MMSYSERR_NOERROR

    def run_safe_test_suite(self):
        """The fixed list of low-level fader, mute and pan messages. A no-op unless writes are allowed."""
        if not self.allow_write:
            print("Writes are disabled (no --allow-write): nothing was sent.")
            return
        plan = [(0xB7, 7, v, "Main Fader") for v in (10, 20, 0)] + [(0xB0, 7, v, "Ch 1 Fader") for v in (10, 20, 0)] + \
               [(0xB0, 5, v, "Ch 1 Mute") for v in (127, 0, 127, 0)] + [(0xB0, 10, v, "Ch 1 Pan") for v in (32, 96, 64)]
        for status, b1, b2, name in plan:
            self.send_short_msg(status, b1, b2, name)
            time.sleep(0.2)

    def generate_raw_log(self):
        """Write a NEW uniquely named log file and return its path."""
        lines = ["# FLOW 8 harness raw log (restricted tool)\n", f"**Timestamp:** {datetime.now().isoformat()}\n\n",
                 "## Outbound\n\n| Timestamp | DWORD | Status | Ch | CC | Value | Parameter | Result | µs |\n|---|---|---|---|---|---|---|---|---|\n"]
        for r in self.tx_records:
            lines.append(f"| {r['timestamp']} | `{r['raw_dword']}` | `0x{r['status']:02X}` | {r['channel']} | {r['b1']} | {r['b2']} | "
                         f"{r['param']} | {r['result']} | {r['latency_us']} |\n")
        lines.append("\n## Inbound\n\n")
        lines.append("Zero inbound packets.\n" if not self.rx_records else
                     "".join(f"- {r['timestamp']} status 0x{r['status']:02X} ch {r['channel']} data {r['b1']} {r['b2']}\n" for r in self.rx_records))
        return write_unique(self.out_dir, "harness_raw_log", ".md", "".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description="FLOW 8 MIDI harness (restricted)")
    parser.add_argument("--allow-write", action="store_true", help="send the fixed list of safe fader/mute/pan messages")
    parser.add_argument("--out-dir", default=None, help="directory for the new log file (default tools/output)")
    args = parser.parse_args(argv)
    if not args.allow_write:
        print("No MIDI will be sent and no port will be opened. Pass --allow-write to run the safe test list.")
        return 0
    harness = Flow8MidiHarness(allow_write=True, out_dir=args.out_dir)
    if not harness.find_endpoints():
        print("ERROR: FLOW 8 endpoints missing!")
        return 1
    try:
        harness.open()
        harness.run_safe_test_suite()
        time.sleep(1.0)
    finally:
        harness.close()
    print("Log written to:", harness.generate_raw_log())
    return 0


if __name__ == "__main__":
    sys.exit(main())
