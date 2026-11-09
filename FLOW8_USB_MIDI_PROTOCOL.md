# FLOW 8 USB MIDI Protocol Specification
**Target:** Behringer FLOW 8 Digital Mixer  
**Phase:** Phase 0.5 — Hardware & Protocol Verification  
**Date:** 2026-11-09  
**Status:** CHART-MAPPED — internal transcription (see provenance note)  
**Revision:** Rev 2 (Phase C.2 corrections applied)

> **Provenance caveat (Phase C.2).** This document is the project's internal
> transcription of a FLOW 8 MIDI implementation chart. No external artifact,
> revision identifier, URL, or capture is retained alongside it, and it cannot be
> independently corroborated from the repository. Treat every mapping below as
> *chart-mapped*, not *independently verified*. Obtaining the source chart (or an
> inbound-MIDI correlation trace) is the single highest-value evidence action.  

---

## 1. MIDI Architecture Overview

The Behringer FLOW 8 exposes a standard class-compliant USB MIDI interface (`FLOW 8 MIDI IN [0]`, `FLOW 8 MIDI OUT [0]`). Communication is organized by **MIDI Channels**, where each channel addresses a specific mixer strip, output bus, effects engine, or global utility.

### 1.1 MIDI Channel Allocation Matrix

| MIDI Channel | Target Section / Subsystem | Functional Scope |
|---|---|---|
| **Ch 1** | Input Channel 1 | Mic 1 (XLR, +48V, Gain, Low Cut, 4-Band PEQ, Compressor) |
| **Ch 2** | Input Channel 2 | Mic 2 (XLR, +48V, Gain, Low Cut, 4-Band PEQ, Compressor) |
| **Ch 3** | Input Channel 3 | Mic/Line 3 (Combo, Gain, Low Cut, 4-Band PEQ, Compressor) — **no Hi-Z** |
| **Ch 4** | Input Channel 4 | Mic/Line 4 (Combo, Gain, Low Cut, 4-Band PEQ, Compressor) — **no Hi-Z** |
| **Ch 5** | Input Channel 5/6 (Stereo) | Line 5/6 (TRS Stereo, Level, Balance, 4-Band Semi-PEQ) |
| **Ch 6** | Input Channel 7/8 (Stereo) | Line 7/8 (TRS Stereo, Level, Balance, 4-Band Semi-PEQ) |
| **Ch 7** | USB / Bluetooth Input | USB Audio 1/2 or BT Audio Return (Level, Balance, 4-Band EQ) |
| **Ch 8** | MAIN L/R Bus | Master Level, Balance, 9-Band GEQ, Master Limiter |
| **Ch 9** | MON 1 Bus | Monitor 1 Master Level, 9-Band GEQ, Limiter |
| **Ch 10** | MON 2 Bus | Monitor 2 Master Level, 9-Band GEQ, Limiter |
| **Ch 11** | FX 1 Send Bus | Effects 1 Master Send Level |
| **Ch 12** | FX 2 Send Bus | Effects 2 Master Send Level |
| **Ch 13** | *Reserved* | Unused |
| **Ch 14** | FX 1 Slot | Engine 1 Algorithm Selector (PC 1–16) & Parameter Tweaks |
| **Ch 15** | FX 2 Slot | Engine 2 Algorithm Selector (PC 1–16) & Parameter Tweaks |
| **Ch 16** | Global Controls & Snapshots | Snapshot Recall (PC 1–15), Reset (PC 16), Tap Tempo (Note 0) |

---

## 2. Input Channels Control Map (Channels 1–7)

The following Control Change (CC) messages apply across Input Channels 1 through 7 on their respective MIDI channels:

| CC # | Parameter | Value Range | Mapped Engineering Value | Exceptions / Notes |
|---|---|---|---|---|
| **CC 1** | EQ LOW | 0 – 127 | -15 dB to +15 dB (Value 64 = 0.0 dB) | Standard shelf / bell |
| **CC 2** | EQ LOW MID | 0 – 127 | -15 dB to +15 dB (Value 64 = 0.0 dB) | Parametric bell band |
| **CC 3** | EQ HI MID | 0 – 127 | -15 dB to +15 dB (Value 64 = 0.0 dB) | Parametric bell band |
| **CC 4** | EQ HI | 0 – 127 | -15 dB to +15 dB (Value 64 = 0.0 dB) | Standard shelf / bell |
| **CC 5** | MUTE | 0 – 127 | 0 = Mute OFF, 1–127 = Mute ON | Hard mute |
| **CC 6** | SOLO | 0 – 127 | 0 = Solo OFF, 1–127 = Solo ON | PFL / AFL bus routing |
| **CC 7** | Channel LEVEL (to MAIN) | 0 – 127 | 0 = OFF (-70 dB), 1–127 = -70 dB to +10 dB | Channel fader |
| **CC 8** | PREAMP GAIN | 0 – 127 | -20 dB to +60 dB | **Channels 1–4 only** (line pairs 5/6 & 7/8 have trim, not a mic preamp) |
| **CC 9** | LOW CUT | 0 – 127 | 20 Hz to 600 Hz | **Channels 1–4 only** |
| **CC 10** | Channel PAN / BALANCE | 0 – 127 | 1.0 Left to 1.0 Right (Value 64 = Center) | Stereo pan or pair balance |
| **CC 11** | COMPRESSOR | 0 – 127 | 0% to 100% (101–127 clamp to 100%) | 1-knob dynamics; **verified address on Channels 1–4 only**. Compressor capability on 5/6 and 7/8 is hardware-specified but its control address is `UNKNOWN`. |
| **CC 12** | +48V PHANTOM POWER | 0 – 127 | 0 = OFF, 1–127 = ON | **Channels 1 & 2 only** |
| **CC 14** | Send Level to MON 1 | 0 – 127 | 0 = OFF, 1–127 = -70 dB to +10 dB | Monitor 1 mix send |
| **CC 15** | Send Level to MON 2 | 0 – 127 | 0 = OFF, 1–127 = -70 dB to +10 dB | Monitor 2 mix send |
| **CC 16** | Send Level to FX 1 | 0 – 127 | 0 = OFF, 1–127 = -70 dB to +10 dB | FX 1 reverb/delay send |
| **CC 17** | Send Level to FX 2 | 0 – 127 | 0 = OFF, 1–127 = -70 dB to +10 dB | FX 2 modulation/pitch send |

---

## 3. Busses Control Map (Channels 8–12)

Output busses are addressed via MIDI Channels 8 through 12:

| CC # | Parameter | Target Busses | Value Range | Engineering Range |
|---|---|---|---|---|
| **CC 7** | Master Bus Level | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10), FX 1 (Ch 11), FX 2 (Ch 12) | 0 – 127 | 0 = OFF, 1–127 = -70 dB to +10 dB |
| **CC 8** | Bus Limiter | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -30 dB to 0 dB threshold |
| **CC 10** | Bus Balance | MAIN (Ch 8) only | 0 – 127 | 1.0 Left to 1.0 Right (64 = Center) |
| **CC 11** | GEQ 62.5 Hz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 12** | GEQ 125 Hz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 13** | GEQ 250 Hz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 14** | GEQ 500 Hz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 15** | GEQ 1 kHz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 16** | GEQ 2 kHz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 17** | GEQ 4 kHz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 18** | GEQ 8 kHz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |
| **CC 19** | GEQ 16 kHz | MAIN (Ch 8), MON 1 (Ch 9), MON 2 (Ch 10) | 0 – 127 | -15 dB to +15 dB (64 = 0 dB) |

---

## 4. FX Slot Engines (Channels 14 & 15)

The two multi-effects engines are controlled independently via Channels 14 and 15:

### 4.1 Algorithm Selection (Program Change)
- **Message:** Program Change (`0xC0` – `0xCF`)
- **Range:** Values 1 to 16 select one of the 16 onboard DSP algorithms:
  - **FX 1 (Channel 14):** 16 Reverbs, Delays, and Ambience models (Hall, Room, Plate, Spring, Echo, etc.).
  - **FX 2 (Channel 15):** 16 Modulation and Tempo models (Chorus, Flanger, Phaser, Pitch Shift, Delay, Tremolo).

### 4.2 FX Parameter Continuous Controllers
- **CC 1 to CC 4:** Modify algorithm-specific tweak parameters (decay time, pre-delay, modulation depth, feedback).

---

## 5. Global Controls & Snapshots (Channel 16)

MIDI Channel 16 provides whole-mixer utilities and scene management:

### 5.1 Snapshot Recall & Reset
- **Message:** Program Change (`0xCF`) on MIDI Channel 16
- **PC 1 to PC 15:** Recalls hardware **Snapshot 1 through Snapshot 15**.
- **PC 16:** Triggers **Full Mixer Hardware Reset** (returns all parameters to initial factory default).

### 5.2 Global Tap Tempo
- **Message:** Note On (`0x9F`) on MIDI Channel 16
- **Note Number:** `0` (Note C-1)
- **Velocity:** `1` to `127` (Velocity `0` and Note Off are ignored)
- **Mechanism:** Repeated Note On events measure time intervals to dynamically synchronize the global delay / tempo BPM (matching the physical hardware TAP button).

---

## 6. Parameter Coverage & Protocol Gaps

| Mixer Function | Control Message | Status | Notes |
|---|---|---|---|
| Faders (Channels 1–8) | CC 7 on Ch 1–7 | VERIFIED | Complete coverage ($-\infty$ to $+10\text{ dB}$) |
| Preamp Gain (Ch 1–4) | CC 8 on Ch 1–4 | VERIFIED | Complete coverage ($-20\text{ dB}$ to $+60\text{ dB}$) |
| Low Cut (Ch 1–4) | CC 9 on Ch 1–4 | VERIFIED | Complete coverage ($20\text{ Hz}$ to $600\text{ Hz}$) |
| 4-Band PEQ (Ch 1–8) | CC 1–4 on Ch 1–7 | VERIFIED | Complete coverage ($-15\text{ dB}$ to $+15\text{ dB}$) |
| 1-Knob Compressor (Ch 1–4) | CC 11 on Ch 1–4 | VERIFIED | Complete coverage ($0\%$ to $100\%$) |
| +48V Phantom (Ch 1–2) | CC 12 on Ch 1–2 | VERIFIED | Complete coverage |
| Mute & Solo (Ch 1–8) | CC 5 & CC 6 on Ch 1–7 | VERIFIED | Complete coverage |
| Monitor Sends (MON 1/2) | CC 14 & CC 15 on Ch 1–7 | VERIFIED | Complete coverage |
| FX Sends (FX 1/2) | CC 16 & CC 17 on Ch 1–7 | VERIFIED | Complete coverage |
| Master Output & 9-Band GEQ | CC 7, CC 11–19 on Ch 8–10 | VERIFIED | Complete coverage |
| FX Algorithm & Tweaks | PC 1–16, CC 1–4 on Ch 14–15 | VERIFIED | Complete coverage |
| Snapshots (1–15) & Reset | PC 1–16 on Ch 16 | VERIFIED | Complete coverage |
| Tap Tempo | Note On 0 on Ch 16 | VERIFIED | Complete coverage |
| Real-time Meter Streaming | N/A | **UNKNOWN / UNDOCUMENTED** | Not exposed via standard MIDI CC |
| Bulk SysEx Memory Dump | SysEx `0xF0 ... 0xF7` | **UNKNOWN / UNDOCUMENTED** | Transport **not established**. BLE GATT, BLE MIDI and USB MIDI SysEx are three different transports; none is evidenced for memory dumps. Do not assume SysEx-over-GATT. |
