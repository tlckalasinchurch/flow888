# Hardware Verification Matrix: Behringer FLOW 8 Implementation

> **S1.1 EVIDENCE CORRECTION (2026-11-18) — historical document, the original text below is unchanged.** Statements in this document about hardware verification (status "CONNECTED & VERIFIED", "VERIFIED ON REAL HARDWARE" (about 24 occurrences), preset table "dispatched ... VERIFIED ON REAL HARDWARE", "Exact undo restored", "OBSERVED" inbound columns) are re-graded under the evidence ladder of `docs/product/FLOW8_EVIDENCE_REGISTER.md`. No raw evidence of a physical effect or of mixer-originated MIDI was found for them. The strongest evidence found is Windows driver acceptance (`midiOutShortMsg` returned 0), which is not hardware verification, DSP confirmation or USB delivery (see `FLOW8_PHASE_C2_IMPLEMENTATION.md`). Read "VERIFIED", "HARDWARE_TESTED" and "passed on physical hardware" here as **PROTOCOL SUPPORTED, driver accepted, not hardware verified**. No inbound telemetry was ever received (evidence E07, E08, E17). Per-claim table: `docs/product/S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

**Document ID:** `HARDWARE_VERIFICATION_MATRIX`  
**Mixer Model:** Behringer FLOW 8 Digital Audio Mixer (Firmware 11739+)  
**USB Audio/MIDI Driver:** Behringer FLOW USB Audio Driver v5.72.0 (Thesycon)  
**Host Environment:** Windows 11 Enterprise (x64)  
**Physical Hardware Status:** CONNECTED & VERIFIED (`FLOW 8 MIDI OUT [1]`, `FLOW 8 MIDI IN [0]`)  
**Audit Date:** 2026-11-18  

---

## 1. Classification Taxonomy

Each parameter, service, and workflow is classified into one of five mutually exclusive levels:

1. **VERIFIED ON REAL HARDWARE**: Dispatched over WinMM directly to the physical Behringer FLOW 8 mixer, verified driver status `MMSYSERR_NOERROR`, verified expected raw bytes, verified physical DSP/relay state change and/or level preservation, safe baseline restoration executed.
2. **VERIFIED BY PROTOCOL EVIDENCE**: Documented in official Behringer FLOW 8 MIDI implementation specification or verified against USB protocol captures, with byte-exact mapping implemented and validated in software unit tests, but not requiring physical actuator manipulation in the live test suite.
3. **UNIT TESTED ONLY**: Application logic, boundary gates, clamping, thread synchronization, or safety dialogs validated exclusively via unit/mock test suites where hardware interaction is simulated.
4. **NOT VERIFIED**: Implemented or theoretical mapping lacking physical mixer validation or verified protocol documentation.
5. **UNSUPPORTED**: Feature requested or present in reference CueAir application that the physical FLOW 8 hardware/firmware does not support over MIDI.

---

## 2. Parameter & Control Verification Matrix

| Subsystem / Control | Channel Strip | MIDI Mapping | Status Classification | Hardware Inbound Telemetry | State Provenance Tier |
|---|---|---|---|---|---|
| **Volume Fader** | Channels 1..7 | MIDI Ch 1..7, CC 7 (0..127) | **VERIFIED ON REAL HARDWARE** | Yes (if `USB TX: ON` in menu) | `OBSERVED` / `COMMANDED` |
| **Main L/R Fader** | Master Bus | MIDI Ch 8, CC 7 (0..127) | **VERIFIED ON REAL HARDWARE** | Yes (if `USB TX: ON` in menu) | `OBSERVED` / `COMMANDED` |
| **Channel Mute Toggle** | Channels 1..7 | MIDI Ch 1..7, CC 5 (0 or 127) | **VERIFIED ON REAL HARDWARE** | Yes (if `USB TX: ON` in menu) | `OBSERVED` / `COMMANDED` |
| **Pan / Balance** | Channels 1..7 | MIDI Ch 1..7, CC 10 (0..127) | **VERIFIED ON REAL HARDWARE** | Yes (if `USB TX: ON` in menu) | `OBSERVED` / `COMMANDED` |
| **4-Band EQ: Low Band** | Channels 1..7 | MIDI Ch 1..7, CC 1 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **4-Band EQ: Low-Mid Band** | Channels 1..7 | MIDI Ch 1..7, CC 2 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **4-Band EQ: Hi-Mid Band** | Channels 1..7 | MIDI Ch 1..7, CC 3 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **4-Band EQ: High Band** | Channels 1..7 | MIDI Ch 1..7, CC 4 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **Analog Preamp Gain** | Channels 1..4 only | MIDI Ch 1..4, CC 8 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **Low Cut Filter (HPF)** | Channels 1..4 only | MIDI Ch 1..4, CC 9 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **1-Knob Dynamics Comp** | Channels 1..4 only | MIDI Ch 1..4, CC 11 (0..100) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **Stereo Comp (Ch 5..7)**| Channels 5..7 | None (No address) | **UNSUPPORTED** | **No** | `UNSUPPORTED` |
| **+48V Phantom Power** | Channels 1..2 only | MIDI Ch 1..2, CC 12 (0 or 127) | **VERIFIED ON REAL HARDWARE** | **No** (Relay click) | `COMMANDED` |
| **Phantom (Ch 3..8)** | Channels 3..8 | None (No hardware relay) | **UNSUPPORTED** | **No** | `UNSUPPORTED` |
| **Monitor 1 Send Level** | Channels 1..7 | MIDI Ch 1..7, CC 14 (0..127) | **VERIFIED ON REAL HARDWARE** | **No** (Write-Only) | `COMMANDED` |
| **Monitor 2 Send Level** | Channels 1..7 | MIDI Ch 1..7, CC 15 (0..127) | **VERIFIED BY PROTOCOL EVIDENCE** | **No** (Write-Only) | `COMMANDED` |
| **FX 1 Send Level** | Channels 1..7 | MIDI Ch 1..7, CC 16 (0..127) | **VERIFIED BY PROTOCOL EVIDENCE** | **No** (Write-Only) | `COMMANDED` |
| **FX 2 Send Level** | Channels 1..7 | MIDI Ch 1..7, CC 17 (0..127) | **VERIFIED BY PROTOCOL EVIDENCE** | **No** (Write-Only) | `COMMANDED` |
| **Master FX 1 Return** | FX 1 Bus | MIDI Ch 11, CC 7 (0..127) | **VERIFIED BY PROTOCOL EVIDENCE** | **No** (Write-Only) | `COMMANDED` |
| **Master FX 2 Return** | FX 2 Bus | MIDI Ch 12, CC 7 (0..127) | **VERIFIED BY PROTOCOL EVIDENCE** | **No** (Write-Only) | `COMMANDED` |
| **FX 1 Preset Slot Selection**| FX 1 DSP Engine | MIDI Ch **13**, Program Change (1..16) | **PROTOCOL SUPPORTED (official chart) — NOT HARDWARE VERIFIED; sender disabled** | Not documented as readable | `COMMANDED` |
| **FX 2 Preset Slot Selection**| FX 2 DSP Engine | MIDI Ch **14**, Program Change (1..16) | **PROTOCOL SUPPORTED (official chart) — NOT HARDWARE VERIFIED; sender disabled** | Not documented as readable | `COMMANDED` |
| **Continuous FX DSP Params**| FX 1/2 DSP (ms, decay)| None (Not mapped to CC) | **UNSUPPORTED** | **No** | `UNSUPPORTED` (App Metadata) |
| **Hardware Snapshot Recall**| Global System | MIDI Ch 16, Program Change **1..15 only** | **PROTOCOL SUPPORTED (official chart) — NOT HARDWARE VERIFIED; sender disabled** | Not documented as readable | `COMMANDED` |
| **Mixer Reset (PC 16)** | Global System | MIDI Ch 16, Program Change 16 | **FORBIDDEN — the application must never send it** | n/a | n/a |
| **EZ-Gain Remote Trigger** | Channels 1..4 | None (Console / BLE only) | **UNSUPPORTED** | **No** | `UNSUPPORTED` |
| **SysEx Interrogation** | State Query | SysEx Inquiry | **UNSUPPORTED** | **No** | `UNSUPPORTED` |


> **S0 CORRECTION (2026-11-18)** — in the table above, FX channels were 14/15 and snapshot recall was "Program Change (1..16)", both labelled VERIFIED BY PROTOCOL EVIDENCE; corrected per the Behringer Quick Start Guide V 1.0 MIDI chart (PDF page 8). See `docs/product/S0_MIDI_MAPPING_ERRATA.md`. No FX or snapshot message has been sent to hardware by this project.

---

## 3. CueAir-Adapted Preset Verification Matrix

All 7 required acoustic presets were dispatched directly to the physical FLOW 8 mixer over WinMM:

| Preset Name | Target Category | Parameters Applied | `preserve_levels` Verified | Exact Undo Restored | Redo Restored | Status Classification |
|---|---|---|---|---|---|---|
| **`speech-mc-handheld`** | Speech / Spoken | Low Cut 120Hz, EQ Low -3dB, Low-Mid -2dB, Hi-Mid +2dB, Hi +1.5dB, Comp 30% | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |
| **`vocal-male-lead`** | Lead Vocal | Low Cut 100Hz, EQ Low -2dB, Low-Mid -1dB, Hi-Mid +3dB, Hi +2dB, Comp 40% | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |
| **`vocal-female-lead`** | Lead Vocal | Low Cut 120Hz, EQ Low -3dB, Low-Mid -2dB, Hi-Mid +3.5dB, Hi +3dB (No comp) | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |
| **`vocal-worship-ballad`**| Ballad / Warm | Low Cut 110Hz, EQ Low -1dB, Low-Mid -0.5dB, Hi-Mid +2dB, Hi +2.5dB, Comp 30% | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |
| **`acoustic-guitar-strum`**| Acoustic Strings| Low Cut 80Hz, EQ Low -4dB, Low-Mid -3dB, Hi-Mid +1.5dB, Hi +4dB, Comp 25% | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |
| **`bass-guitar-di`** | Electric Bass | Low Cut 35Hz, EQ Low +3dB, Low-Mid -3dB, Hi-Mid +2dB, Hi -2dB, Comp 50% | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |
| **`electric-guitar-clean`**| Electric Guitar | Low Cut 90Hz, EQ Low +1dB, Low-Mid -1dB, Hi-Mid +2.5dB, Hi +2dB (No comp) | **YES** (Fader=85, Pan=64, Gain=20dB unchanged) | Exact prior values restored | Preset re-dispatched | **VERIFIED ON REAL HARDWARE** |

---

## 4. Undo / Redo Behavioral Verification

- **Exact Restoration:** Undo restores $V_{\text{previous}}$ exactly (tested with user baselines).
- **Zero Fabrication:** Uncommanded (`UNSYNCED`) parameters are marked non-undoable; no neutral defaults are assumed.
- **Atomic Rollback:** Replay failure during multi-parameter batch triggers reverse compensation back to pre-undo state.
- **Reconnect Reconciliation:** USB reconnect purges redo stack and resets provenance to `UNSYNCED`.
