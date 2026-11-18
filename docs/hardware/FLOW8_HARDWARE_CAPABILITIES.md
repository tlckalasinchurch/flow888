# Phase 3: Behringer FLOW 8 Hardware Capabilities

**Device:** Behringer FLOW 8  
**Firmware Baseline:** 11739+  
**Architecture:** 8-Input Digital Mixer with USB Audio Interface, USB MIDI, and Dual Bluetooth  
**Status:** VERIFIED FROM HARDWARE CAPTURES & DRIVER STACK

---

## 1. Physical & DSP Architecture

```mermaid
flowchart LR
    subgraph Physical_Inputs["Physical Inputs"]
        In1["Mic 1 (XLR) +48V"]
        In2["Mic 2 (XLR) +48V"]
        In3["Mic/Line 3 (TRS/XLR)"]
        In4["Mic/Line 4 (TRS/XLR) Hi-Z"]
        In56["Line 5/6 (Dual 1/4\" TRS)"]
        In78["Line 7/8 (Dual 1/4\" TRS)"]
        USB_In["USB Playback 1/2 or BT"]
    end

    subgraph Channel_DSP["Channel DSP Strips (1-7)"]
        Preamp["Midas Preamp (Ch 1-4)"]
        LowCut["Low Cut Filter (Ch 1-4)"]
        EQ4["4-Band Parametric EQ (Ch 1-7)"]
        Comp["1-Knob Compressor (Ch 1-4)"]
        Pan["Pan / Balance"]
        MuteFader["Mute & 60mm Level Fader"]
    end

    subgraph Mix_Buses["Mix Buses & DSP"]
        MainBus["Main L/R Bus (9-Band GEQ + Limiter)"]
        Mon1Bus["Mon 1 Bus (9-Band GEQ + Limiter)"]
        Mon2Bus["Mon 2 Bus (9-Band GEQ + Limiter)"]
        FX1Bus["FX 1 Send Bus (Reverbs & Delays)"]
        FX2Bus["FX 2 Send Bus (Modulation & Delays)"]
    end

    subgraph Outputs["Physical Outputs"]
        MainOut["Main L/R (Gold XLR & 1/4\" TRS)"]
        Mon1Out["Mon 1 Out (Balanced 1/4\" TRS)"]
        Mon2Out["Mon 2 Out (Balanced 1/4\" TRS)"]
        Phones["Headphones Out (1/4\" Stereo)"]
        USB_Rec["USB 10-Track Audio Interface"]
    end

    In1 & In2 --> Preamp --> LowCut --> EQ4 --> Comp --> Pan --> MuteFader
    In3 & In4 --> Preamp --> LowCut --> EQ4 --> Comp --> Pan --> MuteFader
    In56 & In78 --> EQ4 --> Pan --> MuteFader
    USB_In --> EQ4 --> Pan --> MuteFader

    MuteFader --> MainBus --> MainOut & Phones & USB_Rec
    MuteFader --> Mon1Bus --> Mon1Out
    MuteFader --> Mon2Bus --> Mon2Out
    MuteFader --> FX1Bus & FX2Bus
```

---

## 2. Hardware Subsystem Specifications

### 2.1 Preamps & Analog Front-End
- **Inputs 1 & 2:** Midas-designed discrete microphone preamplifiers on balanced XLR-F connectors. Switchable +48V Phantom Power (individually controllable via MIDI CC 12). Gain range: $-20 \text{ dB}$ to $+60 \text{ dB}$.
- **Inputs 3 & 4:** Combo XLR / 1/4" TRS connectors with microphone/line level sensitivity. Input 4 features high-impedance (Hi-Z) guitar input switch.
- **Inputs 5/6 & 7/8:** Balanced/unbalanced 1/4" TRS stereo pairs with line-level trim.
- **Low Cut Filter:** 12 dB/octave high-pass filter adjustable from $20 \text{ Hz}$ to $600 \text{ Hz}$ on Channels 1–4.

### 2.2 Channel DSP Processing
- **4-Band Parametric EQ:**
  - Low Band: $20 \text{ Hz} - 400 \text{ Hz}$, $-15 \text{ dB} \text{ to } +15 \text{ dB}$.
  - Low-Mid Band: $100 \text{ Hz} - 2,000 \text{ Hz}$, $-15 \text{ dB} \text{ to } +15 \text{ dB}$.
  - High-Mid Band: $500 \text{ Hz} - 8,000 \text{ Hz}$, $-15 \text{ dB} \text{ to } +15 \text{ dB}$.
  - High Band: $2,000 \text{ Hz} - 20,000 \text{ Hz}$, $-15 \text{ dB} \text{ to } +15 \text{ dB}$.
- **Dynamics / 1-Knob Compressor:** Optimized single-control compressor on Channels 1–4 simultaneously adjusting threshold, ratio, and makeup gain with auto-knee characteristics.

### 2.3 Output & Master Buses
- **Main L/R:** Gold-plated XLR male and balanced 1/4" TRS master outputs. Equipped with 9-band Graphic Equalizer ($62.5 \text{ Hz}$ to $16 \text{ kHz}$) and Master Limiter.
- **Monitor Sends (Mon 1 & Mon 2):** Two balanced 1/4" TRS auxiliary monitor outputs with dedicated 9-band GEQ and limiters.
- **Dual Multi-FX Engines:**
  - FX 1: 16 studio-grade reverbs, halls, rooms, plates, and vocal delays.
  - FX 2: 16 modulation effects (chorus, flanger, phaser, tremolo) and pitch-shifting models.

### 2.4 Digital Audio & Control Interfaces
- **USB Audio Interface:** 24-bit / 48 kHz operation. Supports Recording Mode (10-in / 4-out multi-track) and Streaming Mode (2-in / 4-out).
- **USB MIDI Control:** Class-compliant USB MIDI 1.0 endpoint for bi-directional parameter control and state synchronization.
- **Bluetooth Control & Audio:** Dual-mode Bluetooth module providing GATT Server for mobile control app and A2DP sink for wireless stereo audio playback.
