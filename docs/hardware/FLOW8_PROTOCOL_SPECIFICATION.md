# Phase 3: Behringer FLOW 8 Protocol Specification

**Document ID:** `FLOW8_PROTOCOL_SPECIFICATION`  
**Communication Standard:** USB MIDI 1.0 Class-Compliant / WinMM  
**Baud Rate:** USB High-Speed Packetized (Virtual MIDI)  
**Status:** SPECIFIED & VERIFIED

---

## 1. Protocol Architecture

The Behringer FLOW 8 mixer does not expose Ethernet or Wi-Fi OSC sockets; its host control surface protocol operates over **USB MIDI 1.0**.

Every message adheres to standard MIDI Channel Voice message framing:
```
[Status Byte (0xBn)] [Data Byte 1 (CC Number)] [Data Byte 2 (Value 0..127)]
```
Where `n` is the 0-based MIDI Channel index (0x0 to 0xF, corresponding to MIDI Channels 1 to 16).

---

## 2. Channel Allocation Topology

```
Status Byte | MIDI Ch | Mixer Subsystem / Strip Target
------------+---------+-------------------------------------------------------
0xB0        | Ch 1    | Input Channel 1 (Mic 1, Midas Preamp, +48V)
0xB1        | Ch 2    | Input Channel 2 (Mic 2, Midas Preamp, +48V)
0xB2        | Ch 3    | Input Channel 3 (Mic/Line 3, Combo XLR/TRS)
0xB3        | Ch 4    | Input Channel 4 (Mic/Line 4, Hi-Z Instrument)
0xB4        | Ch 5    | Input Channel 5/6 (Stereo Line Pair 1/4" TRS)
0xB5        | Ch 6    | Input Channel 7/8 (Stereo Line Pair 1/4" TRS)
0xB6        | Ch 7    | USB Audio / Bluetooth Return Channel
0xB7        | Ch 8    | MAIN L/R Output Bus (Master Fader, 9-Band GEQ)
0xB8        | Ch 9    | MON 1 Output Bus (Aux 1 Master, 9-Band GEQ)
0xB9        | Ch 10   | MON 2 Output Bus (Aux 2 Master, 9-Band GEQ)
0xBA        | Ch 11   | FX 1 Send Bus Master Level
0xBB        | Ch 12   | FX 2 Send Bus Master Level
0xBC        | Ch 13   | Reserved
0xBD        | Ch 14   | FX 1 DSP Slot Engine (Program Change 1..16 + CC Tweaks)
0xBE        | Ch 15   | FX 2 DSP Slot Engine (Program Change 1..16 + CC Tweaks)
0xBF        | Ch 16   | Global Snapshots (PC 1..15) & Tap Tempo (Note 0)
```

---

## 3. Input Strip Command Set (Channels 1–7)

| CC # | Parameter | Value Range | Engineering Range | Hardware Support |
|---|---|---|---|---|
| **CC 1** | EQ Low Band Gain | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ (64 = 0 dB) | Ch 1–7 |
| **CC 2** | EQ Low-Mid Band Gain | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ (64 = 0 dB) | Ch 1–7 |
| **CC 3** | EQ High-Mid Band Gain | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ (64 = 0 dB) | Ch 1–7 |
| **CC 4** | EQ High Band Gain | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ (64 = 0 dB) | Ch 1–7 |
| **CC 5** | Strip Mute | `0..127` | 0 = Unmuted, 127 = Muted | Ch 1–7 |
| **CC 6** | Solo / PFL | `0..127` | 0 = Off, 127 = Solo Active | Ch 1–7 |
| **CC 7** | Volume Fader | `0..127` | 0 = $-\infty \text{ dB}$, 1..127 = $-70 \text{ dB} \dots +10 \text{ dB}$ | Ch 1–7 |
| **CC 8** | Preamp Gain | `0..127` | $-20.0 \text{ dB} \dots +60.0 \text{ dB}$ | **Ch 1–4 only** |
| **CC 9** | Low Cut (HPF) Frequency | `0..127` | $20 \text{ Hz} \dots 600 \text{ Hz}$ | **Ch 1–4 only** |
| **CC 10** | Pan / Stereo Balance | `0..127` | 0 = 100% Left, 64 = Center, 127 = 100% Right | Ch 1–7 |
| **CC 11** | 1-Knob Compressor | `0..127` | 0% .. 100% (Clamped at 100) | **Ch 1–4 only** |
| **CC 12** | +48V Phantom Power | `0..127` | 0 = Off, 127 = On | **Ch 1 & 2 only** |
| **CC 14** | Aux Send to Mon 1 | `0..127` | 0 = $-\infty \text{ dB}$, 1..127 = $-70 \text{ dB} \dots +10 \text{ dB}$ | Ch 1–7 |
| **CC 15** | Aux Send to Mon 2 | `0..127` | 0 = $-\infty \text{ dB}$, 1..127 = $-70 \text{ dB} \dots +10 \text{ dB}$ | Ch 1–7 |
| **CC 16** | Send to FX 1 | `0..127` | 0 = $-\infty \text{ dB}$, 1..127 = $-70 \text{ dB} \dots +10 \text{ dB}$ | Ch 1–7 |
| **CC 17** | Send to FX 2 | `0..127` | 0 = $-\infty \text{ dB}$, 1..127 = $-70 \text{ dB} \dots +10 \text{ dB}$ | Ch 1–7 |

---

## 4. Bus Strip Command Set (Channels 8–10)

| CC # | Parameter | Value Range | Engineering Range | Target Busses |
|---|---|---|---|---|
| **CC 7** | Master Bus Fader | `0..127` | $-\infty \text{ dB} \dots +10 \text{ dB}$ | Main (Ch 8), Mon 1 (Ch 9), Mon 2 (Ch 10) |
| **CC 8** | Bus Limiter Threshold | `0..127` | $-30.0 \text{ dB} \dots 0.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 10** | Master Balance | `0..127` | Left $\dots$ Center $\dots$ Right | Main (Ch 8) only |
| **CC 11** | GEQ 62.5 Hz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 12** | GEQ 125 Hz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 13** | GEQ 250 Hz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 14** | GEQ 500 Hz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 15** | GEQ 1.0 kHz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 16** | GEQ 2.0 kHz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 17** | GEQ 4.0 kHz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 18** | GEQ 8.0 kHz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |
| **CC 19** | GEQ 16.0 kHz Band | `0..127` | $-15.0 \text{ dB} \dots +15.0 \text{ dB}$ | Main, Mon 1, Mon 2 |

---

## 5. Bidirectional State Synchronization Semantics

- **Outbound (App $\to$ Mixer):** When user moves a fader or toggles a parameter, `Flow8CommandBoundary` emits `midiOutShortMsg`. The hardware physical fader (if motorized) or internal DSP updates immediately.
- **Inbound (Mixer $\to$ App):** When user moves physical knobs or faders on the FLOW 8 console, the mixer emits matching MIDI CC messages over `FLOW 8 MIDI IN [0]`. `Flow8MidiIn` captures these events and updates `Flow8StateModel` without feedback loops.
- **Read-Back Capability:** The USB MIDI 1.0 protocol on FLOW 8 does not implement SysEx parameter interrogation requests. Mixer state synchronization relies on:
  1. Capturing continuous inbound CC messages during live manipulation.
  2. Maintaining authoritative application-side state.
  3. Snapshot recall via Program Change on Channel 16.
