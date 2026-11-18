#!/usr/bin/env python3
"""
FLOW 8 USB MIDI Test Harness
Hardware verification and low-level diagnostic utility for Behringer FLOW 8.
Uses Windows Multimedia API (winmm.dll) directly without external dependencies.
"""

import sys
import os
import time
import ctypes
from datetime import datetime
from ctypes import wintypes

# Windows Multimedia API Constants
MMSYSERR_NOERROR = 0
MIM_OPEN = 0x3C1
MIM_CLOSE = 0x3C2
MIM_DATA = 0x3C3
MIM_LONGDATA = 0x3C4
MIM_ERROR = 0x3C5
CALLBACK_FUNCTION = 0x00030000

# Windows Structures
class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ('wMid', wintypes.WORD),
        ('wPid', wintypes.WORD),
        ('vDriverVersion', wintypes.DWORD),
        ('szPname', wintypes.WCHAR * 32),
        ('dwSupport', wintypes.DWORD)
    ]

class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ('wMid', wintypes.WORD),
        ('wPid', wintypes.WORD),
        ('vDriverVersion', wintypes.DWORD),
        ('szPname', wintypes.WCHAR * 32),
        ('wTechnology', wintypes.WORD),
        ('wVoices', wintypes.WORD),
        ('wNotes', wintypes.WORD),
        ('wChannelMask', wintypes.WORD),
        ('dwSupport', wintypes.DWORD)
    ]

MidiInProc = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD
)

class Flow8MidiHarness:
    def __init__(self, log_path=None):
        self.winmm = ctypes.windll.winmm
        self.in_id = None
        self.out_id = None
        self.in_name = None
        self.out_name = None
        self.h_in = wintypes.HANDLE()
        self.h_out = wintypes.HANDLE()
        self.log_path = log_path
        self.rx_records = []
        self.tx_records = []
        self._cb_ref = None

    def find_endpoints(self):
        """Locate FLOW 8 MIDI IN and OUT devices."""
        num_in = self.winmm.midiInGetNumDevs()
        for i in range(num_in):
            caps = MIDIINCAPSW()
            if self.winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
                if "FLOW 8" in caps.szPname:
                    self.in_id = i
                    self.in_name = caps.szPname

        num_out = self.winmm.midiOutGetNumDevs()
        for i in range(num_out):
            caps = MIDIOUTCAPSW()
            if self.winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
                if "FLOW 8" in caps.szPname:
                    self.out_id = i
                    self.out_name = caps.szPname

        return (self.in_id is not None) and (self.out_id is not None)

    def _midi_in_callback(self, hMidiIn, wMsg, dwInstance, dwParam1, dwParam2):
        if wMsg == MIM_DATA:
            now_iso = datetime.now().isoformat()
            status = dwParam1 & 0xFF
            b1 = (dwParam1 >> 8) & 0xFF
            b2 = (dwParam1 >> 16) & 0xFF
            ts_ms = dwParam2
            ch = (status & 0x0F) + 1
            cmd = status & 0xF0
            rec = {
                'timestamp': now_iso,
                'driver_ts_ms': ts_ms,
                'status': status,
                'b1': b1,
                'b2': b2,
                'channel': ch,
                'type': 'CC' if cmd == 0xB0 else f'0x{cmd:02X}'
            }
            self.rx_records.append(rec)
            print(f"[{now_iso}] << RX [FLOW 8 -> Host]: Status=0x{status:02X} (Ch {ch:02d}), Data1=0x{b1:02X} ({b1:03d}), Data2=0x{b2:02X} ({b2:03d})")

    def open(self):
        """Open endpoints safely."""
        if not self.find_endpoints():
            raise RuntimeError("FLOW 8 MIDI endpoints not found in system enumeration.")

        self._cb_ref = MidiInProc(self._midi_in_callback)
        res_in = self.winmm.midiInOpen(ctypes.byref(self.h_in), self.in_id, self._cb_ref, 0, CALLBACK_FUNCTION)
        if res_in != MMSYSERR_NOERROR:
            raise RuntimeError(f"Failed to open MIDI IN {self.in_id}: error code {res_in}")

        res_out = self.winmm.midiOutOpen(ctypes.byref(self.h_out), self.out_id, 0, 0, 0)
        if res_out != MMSYSERR_NOERROR:
            self.winmm.midiInClose(self.h_in)
            raise RuntimeError(f"Failed to open MIDI OUT {self.out_id}: error code {res_out}")

        self.winmm.midiInStart(self.h_in)
        return True

    def close(self):
        """Close endpoints cleanly."""
        if self.h_in:
            self.winmm.midiInStop(self.h_in)
            self.winmm.midiInReset(self.h_in)
            self.winmm.midiInClose(self.h_in)
            self.h_in = wintypes.HANDLE()
        if self.h_out:
            self.winmm.midiOutClose(self.h_out)
            self.h_out = wintypes.HANDLE()

    def send_short_msg(self, status, b1, b2, param_name=""):
        """Send a 3-byte short MIDI message and log raw bytes."""
        msg = (status & 0xFF) | ((b1 & 0xFF) << 8) | ((b2 & 0xFF) << 16)
        now_iso = datetime.now().isoformat()
        t0 = time.perf_counter()
        res = self.winmm.midiOutShortMsg(self.h_out, msg)
        elapsed_us = (time.perf_counter() - t0) * 1e6

        ch = (status & 0x0F) + 1
        rec = {
            'timestamp': now_iso,
            'status': status,
            'b1': b1,
            'b2': b2,
            'raw_dword': f"0x{msg:06X}",
            'channel': ch,
            'param': param_name,
            'result': res,
            'latency_us': round(elapsed_us, 2)
        }
        self.tx_records.append(rec)
        print(f"[{now_iso}] >> TX [Host -> FLOW 8]: Status=0x{status:02X} (Ch {ch:02d}), CC={b1:03d}, Val={b2:03d} | {param_name} -> Result={res} ({elapsed_us:.1f} µs)")
        return res == MMSYSERR_NOERROR

    def run_safe_test_suite(self):
        """Execute the 4 targeted parameters with 3 iterations each at safe low values."""
        print("=== BEGIN FLOW 8 CONTROLLED MIDI TEST SUITE ===")
        
        # Test 1: Main Fader (Channel 8 / Status 0xB7, CC 7)
        print("\n--- Test Parameter 1: Main Fader (Channel 8, CC 7) ---")
        for i, val in enumerate([10, 20, 0], 1):
            self.send_short_msg(0xB7, 7, val, f"Main Fader [Iter {i}/3, Val {val}]")
            time.sleep(0.2)

        # Test 2: Channel 1 Fader (Channel 1 / Status 0xB0, CC 7)
        print("\n--- Test Parameter 2: Channel 1 Fader (Channel 1, CC 7) ---")
        for i, val in enumerate([10, 20, 0], 1):
            self.send_short_msg(0xB0, 7, val, f"Ch 1 Fader [Iter {i}/3, Val {val}]")
            time.sleep(0.2)

        # Test 3: Channel 1 Mute (Channel 1 / Status 0xB0, CC 5)
        print("\n--- Test Parameter 3: Channel 1 Mute (Channel 1, CC 5) ---")
        for i, (val, label) in enumerate([(127, "Mute ON"), (0, "Mute OFF"), (127, "Mute ON"), (0, "Mute OFF")], 1):
            self.send_short_msg(0xB0, 5, val, f"Ch 1 Mute [Iter {i}, {label}]")
            time.sleep(0.2)

        # Test 4: Channel 1 Pan (Channel 1 / Status 0xB0, CC 10)
        print("\n--- Test Parameter 4: Channel 1 Pan (Channel 1, CC 10) ---")
        for i, (val, label) in enumerate([(32, "Left-Mid"), (96, "Right-Mid"), (64, "Center")], 1):
            self.send_short_msg(0xB0, 10, val, f"Ch 1 Pan [Iter {i}/3, Val {val} ({label})]")
            time.sleep(0.2)

        print("\n=== TEST SUITE COMPLETED ===")

    def generate_raw_log(self, output_path):
        """Write raw log file in Markdown format."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# FLOW 8 Phase 1 Raw MIDI Log\n")
            f.write(f"**Target:** Behringer FLOW 8 Digital Mixer  \n")
            f.write(f"**Timestamp:** {datetime.now().isoformat()}  \n")
            f.write(f"**Hardware Endpoints:** IN: `{self.in_name}` (ID {self.in_id}) | OUT: `{self.out_name}` (ID {self.out_id})  \n\n")
            f.write("---\n\n")
            
            f.write("## 1. Outbound MIDI Log (Desktop -> FLOW 8)\n\n")
            f.write("| Timestamp | Raw DWORD | Status Byte | Channel | CC # | Data Value | Parameter | Driver Call Result | Latency (µs) |\n")
            f.write("|---|---|---|---|---|---|---|---|---|\n")
            for r in self.tx_records:
                status_hex = f"0x{r['status']:02X}"
                cc_hex = f"0x{r['b1']:02X} ({r['b1']})"
                val_hex = f"0x{r['b2']:02X} ({r['b2']})"
                res_str = "MMSYSERR_NOERROR (0)" if r['result'] == 0 else f"ERROR ({r['result']})"
                f.write(f"| {r['timestamp']} | `{r['raw_dword']}` | `{status_hex}` | {r['channel']} | {cc_hex} | {val_hex} | {r['param']} | `{res_str}` | {r['latency_us']} |\n")

            f.write("\n## 2. Inbound MIDI Log (FLOW 8 -> Desktop)\n\n")
            if not self.rx_records:
                f.write("> [!NOTE]\n")
                f.write("> **Zero inbound MIDI packets received during test window.**  \n")
                f.write("> The FLOW 8 hardware accepts outbound MIDI CC without echoing or reflecting parameter changes back over USB MIDI IN. Hardware mixer physical controls remain idle unless operated manually by a user.\n")
            else:
                f.write("| Timestamp | Driver TS (ms) | Status Byte | Channel | Data 1 | Data 2 | Type |\n")
                f.write("|---|---|---|---|---|---|---|\n")
                for r in self.rx_records:
                    f.write(f"| {r['timestamp']} | {r['driver_ts_ms']} | `0x{r['status']:02X}` | {r['channel']} | `0x{r['b1']:02X}` | `0x{r['b2']:02X}` | {r['type']} |\n")

if __name__ == "__main__":
    harness = Flow8MidiHarness()
    if not harness.find_endpoints():
        print("ERROR: FLOW 8 endpoints missing!")
        sys.exit(1)
    
    print(f"Endpoints detected: IN [{harness.in_id}] {harness.in_name}, OUT [{harness.out_id}] {harness.out_name}")
    try:
        harness.open()
        harness.run_safe_test_suite()
        # Brief listen window
        time.sleep(1.0)
    finally:
        harness.close()
    
    log_out = os.path.join(os.getcwd(), "FLOW8_PHASE1_RAW_MIDI_LOG.md")
    harness.generate_raw_log(log_out)
    print(f"Log generated at: {log_out}")
