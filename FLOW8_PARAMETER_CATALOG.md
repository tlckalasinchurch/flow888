# Behringer FLOW 8 Parameter Catalog
**Scope:** Behringer FLOW 8 Digital Mixer ONLY  
**Version:** Phase C Final — revised in Phase C.2  
**Date:** 2026-11-09  

---

## 1. Overview & MIDI Addressing Rules

The Behringer FLOW 8 maps each mixer strip and bus to a dedicated MIDI channel ($1 \dots 16$). Standard MIDI Control Change (CC) messages ($0 \dots 127$) address each parameter.

- **MIDI Status Byte:** `0xB0 | (channel - 1)`
- **Data Byte 1:** Controller Number (CC)
- **Data Byte 2:** Value ($0 \dots 127$)

---

## 2. Input Channels (Channels 1–7)

### Channel Allocation
- **Ch 1:** Input 1 (Mic 1, XLR with +48V Phantom)
- **Ch 2:** Input 2 (Mic 2, XLR with +48V Phantom)
- **Ch 3:** Input 3 (Mic/Line 3, XLR/TRS Combo)
- **Ch 4:** Input 4 (Mic/Line 4, XLR/TRS Combo)
- **Ch 5:** Input 5/6 (Line 5L / 6R Stereo Pair, Hi-Z on 6R)
- **Ch 6:** Input 7/8 (Line 7L / 8R Stereo Pair, Hi-Z on 8R)
- **Ch 7:** USB / Bluetooth Stereo Audio Return

### Parameter Specifications

| Parameter ID Template | CC # | Channel Scope | Parameter Name | Range | Default | Engineering Range | Notes |
|---|---|---|---|---|---|---|---|
| `ch{i}.eq_low` | **CC 1** | Ch 1–7 | 4-Band EQ Low | 0–127 | 64 | -15.0 dB to +15.0 dB | Low shelf / bell; 64 = 0.0 dB |
| `ch{i}.eq_low_mid` | **CC 2** | Ch 1–7 | 4-Band EQ Low-Mid | 0–127 | 64 | -15.0 dB to +15.0 dB | Parametric bell band; 64 = 0.0 dB |
| `ch{i}.eq_hi_mid` | **CC 3** | Ch 1–7 | 4-Band EQ High-Mid | 0–127 | 64 | -15.0 dB to +15.0 dB | Parametric bell band; 64 = 0.0 dB |
| `ch{i}.eq_hi` | **CC 4** | Ch 1–7 | 4-Band EQ High | 0–127 | 64 | -15.0 dB to +15.0 dB | High shelf / bell; 64 = 0.0 dB |
| `ch{i}.mute` | **CC 5** | Ch 1–7 | Channel Mute | 0–127 | 0 | 0 = OFF, 127 = ON | Hard mute |
| `ch{i}.solo` | **CC 6** | Ch 1–7 | Channel Solo (PFL/AFL) | 0–127 | 0 | 0 = OFF, 127 = ON | PFL / AFL bus routing |
| `ch{i}.fader` | **CC 7** | Ch 1–7 | Channel Fader | 0–127 | 0 | $-\infty$, -70 dB to +10 dB | Channel mix level to Main L/R |
| `ch{i}.gain` | **CC 8** | **Ch 1–4 only** | Preamp Gain | 0–127 | 0 | -20.0 dB to +60.0 dB | Analog input preamp stage |
| `ch{i}.low_cut` | **CC 9** | **Ch 1–4 only** | Low Cut Filter | 0–127 | 0 | 20 Hz to 600 Hz | High-pass rumble filter |
| `ch{i}.pan` | **CC 10** | Ch 1–7 | Pan / Balance | 0–127 | 64 | -100% (L) to +100% (R) | Ch 1–4 Pan; Ch 5–7 Stereo Balance |
| `ch{i}.compressor` | **CC 11** | **Ch 1–4 only** | 1-Knob Dynamics | 0–127 | 0 | 0.0% to 100.0% | Values 101–127 clamp to 100% |
| `ch{i}.phantom` | **CC 12** | **Ch 1–2 only** | +48V Phantom Power | 0–127 | 0 | 0 = OFF, 127 = ON | Hardware relay control |
| `ch{i}.send_mon1` | **CC 14** | Ch 1–7 | Aux Send to Mon 1 | 0–127 | 0 | $-\infty$, -70 dB to +10 dB | Monitor 1 mix send level |
| `ch{i}.send_mon2` | **CC 15** | Ch 1–7 | Aux Send to Mon 2 | 0–127 | 0 | $-\infty$, -70 dB to +10 dB | Monitor 2 mix send level |
| `ch{i}.send_fx1` | **CC 16** | Ch 1–7 | Send to FX 1 | 0–127 | 0 | $-\infty$, -70 dB to +10 dB | Reverb / delay send level |
| `ch{i}.send_fx2` | **CC 17** | Ch 1–7 | Send to FX 2 | 0–127 | 0 | $-\infty$, -70 dB to +10 dB | Modulation / pitch send level |

### Channel Restriction Matrix

| Feature | Ch 1 (Mic 1) | Ch 2 (Mic 2) | Ch 3 (Mic/Line 3) | Ch 4 (Mic/Line 4) | Ch 5/6 (Line 5/6) | Ch 7/8 (Line 7/8) | USB/BT (Audio Return) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Preamp Gain (CC 8)** | Supported | Supported | Supported | Supported | **REJECTED** | **REJECTED** | **REJECTED** |
| **Low Cut (CC 9)** | Supported | Supported | Supported | Supported | **REJECTED** | **REJECTED** | **REJECTED** |
| **Compressor (CC 11)** | Supported | Supported | Supported | Supported | **UNKNOWN** (address) | **UNKNOWN** (address) | **NOT PRESENT** |
| **+48V Phantom (CC 12)** | Supported | Supported | **REJECTED** | **REJECTED** | **REJECTED** | **REJECTED** | **REJECTED** |
| **4-Band EQ (CC 1–4)** | Supported | Supported | Supported | Supported | Supported | Supported | Supported |
| **Fader & Mute (CC 7, 5)**| Supported | Supported | Supported | Supported | Supported | Supported | Supported |
| **Sends (CC 14–17)** | Supported | Supported | Supported | Supported | Supported | Supported | Supported |
| **Pan / Balance (CC 10)** | Pan | Pan | Pan | Pan | Balance | Balance | Balance |

---

## 3. Output & Bus Channels (Channels 8–12)

| Parameter ID | MIDI Channel | CC # | Bus Name | Function | Range | Engineering Value |
|---|---|---|---|---|---|---|
| `main.fader` | Ch 8 | **CC 7** | Main L/R Bus | Master Fader Level | 0–127 | $-\infty$, -70 dB to +10 dB |
| `main.balance` | Ch 8 | **CC 10** | Main L/R Bus | Master Stereo Balance | 0–127 | -100% (L) to +100% (R) |
| `main.limiter` | Ch 8 | **CC 8** | Main L/R Bus | Master Bus Limiter Threshold | 0–127 | -30.0 dB to 0.0 dB |
| `main.geq_62` | Ch 8 | **CC 11** | Main L/R Bus | 9-Band GEQ 62.5 Hz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_125` | Ch 8 | **CC 12** | Main L/R Bus | 9-Band GEQ 125 Hz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_250` | Ch 8 | **CC 13** | Main L/R Bus | 9-Band GEQ 250 Hz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_500` | Ch 8 | **CC 14** | Main L/R Bus | 9-Band GEQ 500 Hz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_1k` | Ch 8 | **CC 15** | Main L/R Bus | 9-Band GEQ 1 kHz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_2k` | Ch 8 | **CC 16** | Main L/R Bus | 9-Band GEQ 2 kHz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_4k` | Ch 8 | **CC 17** | Main L/R Bus | 9-Band GEQ 4 kHz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_8k` | Ch 8 | **CC 18** | Main L/R Bus | 9-Band GEQ 8 kHz | 0–127 | -15.0 dB to +15.0 dB |
| `main.geq_16k` | Ch 8 | **CC 19** | Main L/R Bus | 9-Band GEQ 16 kHz | 0–127 | -15.0 dB to +15.0 dB |
| `mon1.fader` | Ch 9 | **CC 7** | Monitor 1 Bus | Master Monitor Fader | 0–127 | $-\infty$, -70 dB to +10 dB |
| `mon1.limiter` | Ch 9 | **CC 8** | Monitor 1 Bus | Monitor 1 Limiter | 0–127 | -30.0 dB to 0.0 dB |
| `mon1.geq_*` | Ch 9 | **CC 11–19** | Monitor 1 Bus | 9-Band GEQ Bands | 0–127 | -15.0 dB to +15.0 dB |
| `mon2.fader` | Ch 10 | **CC 7** | Monitor 2 Bus | Master Monitor Fader | 0–127 | $-\infty$, -70 dB to +10 dB |
| `mon2.limiter` | Ch 10 | **CC 8** | Monitor 2 Bus | Monitor 2 Limiter | 0–127 | -30.0 dB to 0.0 dB |
| `mon2.geq_*` | Ch 10 | **CC 11–19** | Monitor 2 Bus | 9-Band GEQ Bands | 0–127 | -15.0 dB to +15.0 dB |
| `fx1.fader` | Ch 11 | **CC 7** | FX 1 Bus | FX 1 Master Send Level | 0–127 | $-\infty$, -70 dB to +10 dB |
| `fx2.fader` | Ch 12 | **CC 7** | FX 2 Bus | FX 2 Master Send Level | 0–127 | $-\infty$, -70 dB to +10 dB |
