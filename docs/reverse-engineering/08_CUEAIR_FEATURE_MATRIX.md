# Phase 2: CueAir Feature Matrix & Finding Ledger

**Document ID:** `08_CUEAIR_FEATURE_MATRIX`  
**Target:** `CueAir.app` & `cueair-mcp`  
**Status:** AUDITED & VERIFIED

---

## 1. Finding Ledger

| Finding ID | Feature Name | Source Module / Symbol | Evidence Location | Confidence | Relevance to Behringer FLOW 8 |
|---|---|---|---|---|---|
| **FIND-01** | UDP Broadcast Discovery | `NWListener` / OSC `/xinfo` | `CueAir` binary string table | 100% | FLOW 8 uses Class-Compliant USB MIDI, not UDP network sockets. Discovery must use WinMM device enumeration (`midiInGetDevCapsW`). |
| **FIND-02** | 4-Band Parametric EQ | `strip_detail`, `/eq/1~4/f,g,q` | `cueair-mcp`, reflection strings | 100% | Directly maps to FLOW 8 Channels 1–7 EQ bands (CC 1..4). |
| **FIND-03** | Dynamics / 1-Knob Comp | `/dyn/thr,ratio,knee,mgain` | `cueair-mcp`, reflection strings | 100% | Directly maps to FLOW 8 1-knob compressor on Channels 1–4 (CC 11). |
| **FIND-04** | Low Cut (HPF) Filter | `/preamp/hpf`, `hpon` | `cueair-mcp`, preset JSON | 100% | Directly maps to FLOW 8 Low Cut on Channels 1–4 (CC 9). |
| **FIND-05** | Preamp Gain & +48V | `/headamp/N/gain`, `/phantom` | `cueair-mcp`, reflection strings | 100% | Directly maps to FLOW 8 Gain (CC 8) and +48V (CC 12) on Ch 1–2. |
| **FIND-06** | Curated Presets Library | `cuetone-basic.cueairpreset` | `CueAir_XAirCore.bundle` | 100% | 50 high-value audio engineering presets can be ported directly into the FLOW 8 application! |
| **FIND-07** | Preset Level Protection | `preserveLevels: true` | `cuetone-basic.cueairpreset` | 100% | Critical workflow: applying a preset must not alter input gain, fader volume, or pan. |
| **FIND-08** | Pre-Execution Snapshot | `scene_save`, `BEFORE_AI` | `cueair-mcp` prompt instructions | 100% | Automatically store a scene snapshot before applying batch changes or presets. |
| **FIND-09** | Reverb & Delay FX Presets | `cuetone-fx-xair.json` | `CueAir_XAirCore.bundle` | 100% | Map FX categories (Room, Plate, Hall, Delay) to FLOW 8 FX1 (Reverb) & FX2 (Delay) buses. |
| **FIND-10** | Monitor / Aux Bus Routing | `/mix/01~06/level` | `cueair-mcp` | 100% | Directly maps to FLOW 8 Aux Send Mon 1 (CC 14) and Mon 2 (CC 15). |
| **FIND-11** | Output Bus GEQ & Limiter | `/bus/NN/geql`, `/limiter` | `CueAir` reflection strings | 100% | FLOW 8 features 9-band GEQ on Main and Mon 1-2. |
| **FIND-12** | MCP Agent Integration | `cueair-mcp` JSON-RPC stdio | `Contents/MacOS/cueair-mcp` | 100% | Proves viability of exposing an agentic control boundary for LLMs. |

---

## 2. Feature Adaptation Summary

| CueAir Feature | FLOW 8 Hardware Support | Implementation Strategy |
|---|---|---|
| **OSC Network Discovery** | No (Hardware is USB-only) | WinMM `midiInGetDevCapsW` / `midiOutGetDevCapsW` matching "FLOW 8". |
| **Channel Strips (1-16)** | Channels 1-7 + Main 8 | Render 7 physical strips + 1 Master strip in console. |
| **Preamp Gain** | Ch 1-4 supported | Dedicated Gain rotary dials with dB readouts on Ch 1-4. |
| **+48V Phantom Power** | Ch 1-2 supported | Dedicated toggle with safety confirmation dialog on Ch 1-2. |
| **4-Band EQ** | Supported on all channels | Vector EQ curve visualizer + 4 frequency/gain dials. |
| **Compressor** | Ch 1-4 supported | 1-Knob compressor dial + gain-reduction indicator. |
| **Audio Presets** | Supported via App Logic | Port 50 CueAir presets into FLOW 8 Preset Browser with level protection. |
| **FX Starting Points** | FX 1 (Reverb) & FX 2 (Delay) | Implement FX presets targeting FLOW 8 FX send channels (Ch 11 & 12). |
| **Undo / Redo** | Supported via App Logic | Integrate `CommandLedger` across all new controls and preset recalls. |
