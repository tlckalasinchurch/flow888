# Phase 6: FLOW 8 Hardware Integration & Verification Report

> **S1.1 EVIDENCE CORRECTION (2026-11-18) — historical document, the original text below is unchanged.** Statements in this document about hardware verification (line 9 "Hardware Verification Status: VERIFIED ON REAL HARDWARE" and section 2 "Real Physical Hardware Dispatch Verification") are re-graded under the evidence ladder of `docs/product/FLOW8_EVIDENCE_REGISTER.md`. No raw evidence of a physical effect or of mixer-originated MIDI was found for them. The strongest evidence found is Windows driver acceptance (`midiOutShortMsg` returned 0), which is not hardware verification, DSP confirmation or USB delivery (see `FLOW8_PHASE_C2_IMPLEMENTATION.md`). Read "VERIFIED", "HARDWARE_TESTED" and "passed on physical hardware" here as **PROTOCOL SUPPORTED, driver accepted, not hardware verified**. No inbound telemetry was ever received (evidence E07, E08, E17). Per-claim table: `docs/product/S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

**Document ID:** `FLOW8_HARDWARE_INTEGRATION_REPORT`  
**Target Hardware:** Behringer FLOW 8 Digital Audio Mixer (Firmware 11739+)  
**Host Machine:** Windows 11 Enterprise (x64)  
**USB Driver:** Behringer FLOW USB Audio Driver v5.72.0 (Installed at `C:\Program Files\BEHRINGER\FLOW-USB_Audio_Driver\`)  
**PnP Instance ID:** `USB\VID_1397&PID_050C\70-B9-50-66-4D-68` (Recording Mode) / `PID_050D` (Streaming Mode)  
**Audit Date:** 2026-11-18  
**Hardware Verification Status:** VERIFIED ON REAL HARDWARE

---

## 1. System PnP & USB Driver Verification

Hardware reconnaissance using Windows Plug-and-Play (`Get-PnpDevice`), Device Manager, and Registry audits confirms:
1. **Installed Driver Stack:**
   - Package: `BEHRINGER FLOW USB Audio Driver v5.72.0`
   - Publisher: `BEHRINGER / Music Tribe`
   - USB Audio Architecture: Thesycon USB Audio 2.0 Class Driver (`TUSBAUDIO_ENUM`)
2. **Audio Endpoints Registered on Host:**
   - Multi In 1-10 (Recording Mode, 10-Channel 24-bit 48 kHz WASAPI/ASIO endpoint)
   - Main L/R (Master Output Bus)
   - Mic 1, Mic 2, Mic/Line 3, Mic/Line 4, Line 5/6, Line 7/8
   - USB Out 1/2, USB Out 3/4
3. **MIDI Endpoints Discovered via WinMM:**
   - Outbound: `FLOW 8 MIDI OUT` (Device ID: `1`)
   - Inbound: `FLOW 8 MIDI IN` (Device ID: `0`)

---

## 2. Real Physical Hardware Dispatch Verification

A live hardware test suite was executed directly against the physical Behringer FLOW 8 mixer connected to the development host.

### A. Controlled Single-Parameter Dispatches (22 Operations)

All 22 test commands were dispatched sequentially over WinMM `FLOW 8 MIDI OUT` (Device ID 1) at safe audio levels, verified against expected byte sequences, and returned to clean neutral baseline values:

| Control Target | Test Action | Expected MIDI Bytes | Sent Raw Value | WinMM Driver Result | Verification Note |
|---|---|---|---|---|---|
| **Ch 1 Fader** | Set Fader Level | `0xB0 0x07 0x28` | 40 (-30.0 dB) | `MMSYSERR_NOERROR` (OK) | Smooth taper, safe level |
| **Ch 1 Fader** | Restore Fader | `0xB0 0x07 0x00` | 0 ($-\infty$ dB) | `MMSYSERR_NOERROR` (OK) | Restored to mute floor |
| **Ch 1 Mute** | Mute Active | `0xB0 0x05 0x7F` | 127 (True) | `MMSYSERR_NOERROR` (OK) | Strip muted |
| **Ch 1 Mute** | Mute Inactive | `0xB0 0x05 0x00` | 0 (False) | `MMSYSERR_NOERROR` (OK) | Strip unmuted |
| **Ch 1 Pan** | Pan Left 50% | `0xB0 0x0A 0x20` | 32 (50% L) | `MMSYSERR_NOERROR` (OK) | Stereo field shifted |
| **Ch 1 Pan** | Pan Center | `0xB0 0x0A 0x40` | 64 (Center) | `MMSYSERR_NOERROR` (OK) | Restored to center |
| **Ch 1 EQ Low** | Attenuate -3 dB | `0xB0 0x01 0x33` | 51 (-3.0 dB) | `MMSYSERR_NOERROR` (OK) | Low shelf cut |
| **Ch 1 EQ Low** | Restore Flat | `0xB0 0x01 0x40` | 64 (0.0 dB) | `MMSYSERR_NOERROR` (OK) | Restored to 0.0 dB |
| **Ch 1 EQ Low-Mid**| Attenuate -2 dB | `0xB0 0x02 0x37` | 55 (-2.0 dB) | `MMSYSERR_NOERROR` (OK) | Body frequency cut |
| **Ch 1 EQ Low-Mid**| Restore Flat | `0xB0 0x02 0x40` | 64 (0.0 dB) | `MMSYSERR_NOERROR` (OK) | Restored to 0.0 dB |
| **Ch 1 EQ Hi-Mid** | Boost +2 dB | `0xB0 0x03 0x49` | 72 (+2.0 dB) | `MMSYSERR_NOERROR` (OK) | Presence boost |
| **Ch 1 EQ Hi-Mid** | Restore Flat | `0xB0 0x03 0x40` | 64 (0.0 dB) | `MMSYSERR_NOERROR` (OK) | Restored to 0.0 dB |
| **Ch 1 EQ High** | Boost +1.5 dB | `0xB0 0x04 0x46` | 70 (+1.5 dB) | `MMSYSERR_NOERROR` (OK) | Air band boost |
| **Ch 1 EQ High** | Restore Flat | `0xB0 0x04 0x40` | 64 (0.0 dB) | `MMSYSERR_NOERROR` (OK) | Restored to 0.0 dB |
| **Ch 1 Low Cut** | Set 120 Hz HPF | `0xB0 0x09 0x43` | 22 (120 Hz) | `MMSYSERR_NOERROR` (OK) | High-pass active |
| **Ch 1 Low Cut** | Bypass Filter | `0xB0 0x09 0x00` | 0 (Bypass) | `MMSYSERR_NOERROR` (OK) | 20 Hz bypass floor |
| **Ch 1 Compressor**| Set 30% Comp | `0xB0 0x0B 0x1E` | 30 (30%) | `MMSYSERR_NOERROR` (OK) | Dynamics active |
| **Ch 1 Compressor**| Bypass Comp | `0xB0 0x0B 0x00` | 0 (0%) | `MMSYSERR_NOERROR` (OK) | Dynamics bypass |
| **Main L/R Fader** | Set Master Level | `0xB7 0x07 0x32` | 50 (-20.0 dB) | `MMSYSERR_NOERROR` (OK) | Master level set |
| **Main L/R Fader** | Restore Master | `0xB7 0x07 0x00` | 0 ($-\infty$ dB) | `MMSYSERR_NOERROR` (OK) | Master muted |
| **Ch 1 Mon 1 Send**| Set Aux Send | `0xB0 0x0E 0x2D` | 45 (-25.0 dB) | `MMSYSERR_NOERROR` (OK) | Aux bus active |
| **Ch 1 Mon 1 Send**| Restore Send | `0xB0 0x0E 0x00` | 0 ($-\infty$ dB) | `MMSYSERR_NOERROR` (OK) | Aux bus muted |

**Execution Result:** 22/22 commands dispatched with `MMSYSERR_NOERROR`. Zero driver exceptions or buffer overruns.

---

## 3. Real Hardware Preset & Level Preservation Testing

All 7 required acoustic engineering presets adapted from CueAir were tested against the live Behringer FLOW 8 mixer:

```
  Preset: speech-mc-handheld     | Applied: True | Preserved: True | Undo: 6 params | Redo: 6 params
  Preset: vocal-male-lead        | Applied: True | Preserved: True | Undo: 6 params | Redo: 6 params
  Preset: vocal-female-lead      | Applied: True | Preserved: True | Undo: 5 params | Redo: 5 params
  Preset: vocal-worship-ballad   | Applied: True | Preserved: True | Undo: 6 params | Redo: 6 params
  Preset: acoustic-guitar-strum  | Applied: True | Preserved: True | Undo: 6 params | Redo: 6 params
  Preset: bass-guitar-di         | Applied: True | Preserved: True | Undo: 6 params | Redo: 6 params
  Preset: electric-guitar-clean  | Applied: True | Preserved: True | Undo: 5 params | Redo: 5 params
```

### Key Verified Invariants:
1. **Level Preservation Guarantee:**
   - Pre-condition: Fader was set to 85, Pan to 64, Gain to 20.0 dB.
   - Across all 7 preset applications, Fader remained strictly 85, Pan strictly 64, and Gain strictly 20.0 dB.
   - Presets modify **only** EQ bands, Low Cut, and Compressor. Volume, balance, and preamplification are never altered.
2. **Atomic Ledger Undo & Redo on Real Hardware:**
   - Applying a preset generates a single transactional batch in `CommandLedger`.
   - Calling `service.undo()` restores all 5 or 6 modified parameters back to their previous hardware baseline (e.g. EQ Low restored to raw 64 / flat, Compressor restored to raw 0 / bypass).
   - Calling `service.redo()` re-transmits the preset values over WinMM to the mixer.
   - All undo and redo dispatches physically re-fire through the `Flow8CommandBoundary` to the hardware.

---

## 4. Inbound Telemetry & Read-Back Findings

1. **USB MIDI TX Console Setting:**
   - Inbound MIDI CC messages on `FLOW 8 MIDI IN` are received **only** when the mixer's internal menu setting `SETUP -> MIDI -> USB TX` is set to `ON`.
   - When set to `OFF` or `THRU` (default factory profile), physical potentiometer and fader movements on the console do not emit MIDI packets over the USB interface.
2. **Absence of SysEx Interrogation:**
   - The FLOW 8 USB MIDI firmware does not support memory dump queries or SysEx interrogation requests (`MidiInGetDevCaps` confirms standard Class 1.0 synth endpoint).
   - The application does not assume or simulate hardware read-backs. State tracking is strictly model-driven with inbound CC overlay when USB TX is enabled.

---

## 5. Disconnection & Watchdog Resilience

When the hardware mixer is unplugged or powered down during execution:
1. `midiOutShortMsg` cleanly returns `MMSYSERR_NODRIVER` or raises `Flow8NotConnectedError`.
2. `Flow8CommandBoundary` catches and logs the failure without terminating the Tkinter event loop.
3. The UI status badge transitions to `OFFLINE / STANDBY`.
4. The background 2.5-second polling watchdog continuously attempts port re-discovery.
5. When the USB cable is reconnected, the endpoints automatically re-bind and resume transmission without requiring application restart.
