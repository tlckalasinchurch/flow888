# Behringer FLOW 8 Parameter Verification Matrix
**Scope:** Behringer FLOW 8 Digital Mixer ONLY  
**Hardware ID:** `USB\VID_1397&PID_050C\70-B9-50-66-4D-68`  
**Phase:** Phase C Completion  
**Date:** 2026-11-09  

---

## 1. Verification Level Definitions (revised in Phase C.2)

> **Correction notice.** The previous revision of this section defined
> `HARDWARE_TESTED` as satisfied by "live hardware test execution", and four
> parameters were graded on that basis even though the only retained evidence was
> a WinMM return code. That definition is withdrawn: a successful `midiOutShortMsg`
> call never establishes hardware behaviour.

- **`HARDWARE_TESTED`**: Physical mixer behaviour **actually observed** and recorded
  (inbound confirmation, readback, or a documented before/after observation).
  Nothing in the current codebase holds this grade.
- **`API_ACKNOWLEDGED`**: The only proof is that the Windows MIDI driver accepted a
  message (`midiOutShortMsg` returned `MMSYSERR_NOERROR`). Asserts nothing about USB
  transmission, mixer application, or audio.
- **`PROTOCOL_VERIFIED`**: Mapping supported by the project's protocol chart
  (`FLOW8_USB_MIDI_PROTOCOL.md`). **Caveat:** that chart is an internal
  transcription; no external artifact, revision, or URL is retained, so this grade
  means "consistently chart-mapped", not "independently confirmed".
- **`IMPLEMENTED`**: Implemented in software.
- **`HARDWARE_SPECIFIED`**: Documented hardware feature with no verified control address.
- **`UNKNOWN`**: Capability asserted but evidence absent or unresolved. Distinct
  from "not present".

### 1.1 The four states that must not be conflated

| State | Evidence available |
|---|---|
| API acknowledgment | `midiOutShortMsg` returned 0 |
| USB transmission | **not measured** |
| Mixer parameter applied | **never confirmed** (`hardware_applied` is always `None`) |
| Audible audio change | **not measured** |

---

## 2. Input Channel Strips Verification Matrix

| Parameter | Channels 1 & 2 | Channels 3 & 4 | Channels 5/6 & 7/8 | Channel 7 (USB/BT) | Verification Level | Evidence Source |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **Fader (CC 7)** | **API_ACKNOWLEDGED** (Ch 1) / PROTOCOL_VERIFIED (Ch 2) | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | WinMM dispatch only (no readback) / FLOW 8 MIDI Chart |
| **Mute (CC 5)** | **API_ACKNOWLEDGED** (Ch 1) / PROTOCOL_VERIFIED (Ch 2) | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | WinMM dispatch only (no readback) / FLOW 8 MIDI Chart |
| **Pan / Balance (CC 10)** | **API_ACKNOWLEDGED** (Ch 1) / PROTOCOL_VERIFIED (Ch 2) | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | WinMM dispatch only (no readback) / FLOW 8 MIDI Chart |
| **EQ Low (CC 1)** | **API_ACKNOWLEDGED** (Ch 1) / PROTOCOL_VERIFIED (Ch 2) | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | WinMM dispatch only (no readback) / FLOW 8 MIDI Chart |
| **EQ Low-Mid (CC 2)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **EQ High-Mid (CC 3)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **EQ High (CC 4)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **Preamp Gain (CC 8)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | **N/A (REJECTED)** | **N/A (REJECTED)** | FLOW 8 MIDI Chart (Ch 1–4 only) |
| **Low Cut Filter (CC 9)**| PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | **N/A (REJECTED)** | **N/A (REJECTED)** | FLOW 8 MIDI Chart (Ch 1–4 only) |
| **Compressor (CC 11)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | **UNKNOWN** (capability specified, control address not verified) | **UNKNOWN** (same) | FLOW 8 MIDI Chart covers Ch 1–4 only |
| **+48V Phantom (CC 12)**| PROTOCOL_VERIFIED | **N/A (REJECTED)** | **N/A (REJECTED)** | **N/A (REJECTED)** | FLOW 8 MIDI Chart (Ch 1–2 only) |
| **Mon 1 Send (CC 14)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **Mon 2 Send (CC 15)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **FX 1 Send (CC 16)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **FX 2 Send (CC 17)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |
| **Solo (CC 6)** | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | PROTOCOL_VERIFIED | FLOW 8 MIDI Chart |

---

## 3. Bus & Master Strips Verification Matrix

| Bus ID | Channel | Parameter | CC # | Verification Level | Evidence Source |
|---|:---:|---|:---:|:---:|---|
| `main` | Ch 8 | Master Fader | CC 7 | **API_ACKNOWLEDGED** | WinMM dispatch only; no readback, no loopback |
| `main` | Ch 8 | Master Balance | CC 10 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `main` | Ch 8 | Bus Limiter | CC 8 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `main` | Ch 8 | 9-Band GEQ (62 Hz – 16 kHz) | CC 11–19 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `mon1` | Ch 9 | Master Fader | CC 7 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `mon1` | Ch 9 | Bus Limiter & 9-Band GEQ | CC 8, 11–19 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `mon2` | Ch 10 | Master Fader | CC 7 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `mon2` | Ch 10 | Bus Limiter & 9-Band GEQ | CC 8, 11–19 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `fx1` | Ch 11 | FX 1 Master Send Level | CC 7 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |
| `fx2` | Ch 12 | FX 2 Master Send Level | CC 7 | **PROTOCOL_VERIFIED** | FLOW 8 MIDI Chart |

---

## 4. Hardware Specification & Protocol Gaps

| Capability | Scope | Status | Notes |
|---|---|---|---|
| **EZ-Gain Automatic Calibration** | Global / Ch 1–4 | `HARDWARE_SPECIFIED` | Firmware-internal feature triggered from the front panel. Whether any remote trigger exists is `UNKNOWN`; none is documented or verified. Not exposed via USB MIDI CC. |
| **Headphones Monitoring Tap** | Physical Monitor Tap | `HARDWARE_SPECIFIED` | Switchable analog monitoring tap mirroring Main, Mon 1, or Mon 2; not an independent DSP mix bus. |
| **Real-time VU Meter Streaming** | Capture Channels 1–10 | `PROTOCOL_GAP` | Mixer hardware does not stream meter levels over USB MIDI. Handled via software metering in the USB Audio Engine (`FLOW8_AUDIO_ENGINE_SPEC.md`). |
| **Bulk Preset / Memory SysEx Dump** | Full Mixer State | `UNKNOWN` | Transport **unknown**. No official documentation, no protocol evidence, no implementation. Three non-interchangeable candidates exist: USB MIDI SysEx, a BLE MIDI GATT service, or a proprietary GATT payload. None has been captured. This is an open investigation item, not a resolved gap. |
