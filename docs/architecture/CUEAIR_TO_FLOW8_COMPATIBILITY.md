# Phase 4: CueAir to FLOW 8 Compatibility Matrix

**Document ID:** `CUEAIR_TO_FLOW8_COMPATIBILITY`  
**Classification System:**
- **Class A:** Directly supported by FLOW 8 hardware.
- **Class B:** Supported with a different protocol / workflow.
- **Class C:** Implementable as application-side functionality.
- **Class D:** Unsupported by FLOW 8 hardware.
- **Class E:** Unknown / Requires further physical investigation.

---

## 1. Feature Compatibility Matrix

| Feature | CueAir Reference Implementation | FLOW 8 Hardware Support | Class | Implementation Adaptation |
|---|---|---|---|---|
| **Channel Strips 1–4 (Mic)** | 16-32 channels over UDP OSC | 4 Mic/Line preamps, Gain, +48V (Ch 1-2), Low Cut, 4-Band EQ, 1-knob Comp | **Class B** | Map CueAir channel UI to FLOW 8 Channels 1–4 via MIDI CC. |
| **Channel Strips 5–8 (Stereo)** | Stereo link mode in software | 2 Stereo Pairs (5/6 & 7/8), Level, Balance, 4-Band EQ | **Class B** | Control via MIDI Ch 5 & 6; balance replaces pan. |
| **USB Audio / BT Return** | Aux return channels | Channel 7 digital return | **Class B** | Map via MIDI Ch 7 (CC 7 level, CC 10 balance, CC 1-4 EQ). |
| **Main L/R Master Bus** | Main stereo bus over OSC | Main bus via MIDI Ch 8 | **Class B** | Master fader (CC 7), balance (CC 10), limiter (CC 8), 9-band GEQ (CC 11-19). |
| **Monitor / Aux Buses** | Aux 1–6 sends over OSC | Mon 1 (Ch 9) & Mon 2 (Ch 10) | **Class B** | Per-channel sends (CC 14 & 15), bus master levels (CC 7). |
| **Parametric EQ Curve Display** | Vector SVG interactive curve | Hardware has 4-band PEQ | **Class C** | Render real-time interactive parametric EQ response curve in UI canvas based on CC 1..4 gains. |
| **50 Curated Presets Library** | `cuetone-basic.cueairpreset` | Mixers do not store presets internally | **Class C** | Parse and embed CueAir presets into Flow8; apply via batch CC dispatch with level protection. |
| **Level-Preserving Preset Recall** | `preserveLevels: true` | Application logic | **Class C** | Apply EQ, Comp, HPF, Gate without changing Fader, Pan, or Preamp Gain. |
| **Pre-Execution Snapshots** | Auto "BEFORE_AI" / "BEFORE_PRESET" | Application `SceneManager` | **Class C** | Capture snapshot to memory before batch changes; provide instant 1-click restore. |
| **Multi-Tier Undo/Redo** | App state stack | Application `CommandLedger` | **Class C** | Bind all UI changes to `CommandLedger` with inverse MIDI command execution. |
| **FX Starting Points** | `cuetone-fx-xair.json` | 16 FX1 Algorithms, 16 FX2 Algorithms | **Class B/C**| Program Change 1..16 on MIDI Ch 14 (FX1) and Ch 15 (FX2) with tailored FX presets. |
| **Multi-Track Recording** | macOS CoreAudio | 10-in / 4-out USB 2.0 Audio Driver | **Class A** | Class-compliant ASIO/WASAPI integration via Windows audio stack. |
| **On-Mixer Wi-Fi / Ethernet** | UDP port 10023 | No on-board network interface | **Class D** | FLOW 8 is USB/BLE only; network bridging would require external companion host. |
| **Deep SysEx State Interrogation**| OSC wildcard `/xremote` query | MIDI 1.0 CC write/listen only | **Class D** | Flow8 application maintains state cache, updated by inbound MIDI CC events from console faders. |
| **Agent / MCP Automation** | `cueair-mcp` stdio JSON-RPC | Application layer service | **Class C** | Expose high-level mixer automation methods inside `Flow8Service` matching CueAir agent paradigms. |
