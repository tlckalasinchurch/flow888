# Phase 8: Known Limitations & Hardware Boundaries

**Document ID:** `KNOWN_LIMITATIONS`  
**Mixer Model:** Behringer FLOW 8 (Firmware 11739+)  
**Host Subsystem:** Windows WinMM / USB MIDI Class 1.0  
**Status:** FORMALIZED & VERIFIED  

---

## 1. Hardware & Firmware Constraints

1. **Write-Only USB MIDI Interrogation (No SysEx Dump):**
   - The Behringer FLOW 8 USB MIDI 1.0 implementation does not support SysEx state dumping (such as Behringer X32/Wing `/xremote` or MIDI parameter inquiry).
   - The application cannot query the mixer for initial physical rotary knob positions or switch positions upon startup.
   - State tracking is strictly software model-driven, augmented by live incoming MIDI CC capture when the user moves controls on the console.

2. **Inbound MIDI Telemetry Console Setting (`USB TX: ON`):**
   - Inbound MIDI messages on `FLOW 8 MIDI IN` are emitted by the hardware **only** when the mixer console's menu is configured to `SETUP -> MIDI -> USB TX: ON`.
   - When set to `OFF` or `THRU` (default factory profile), manual knob movements on the physical console do not transmit MIDI messages over the USB connection.

3. **FX Parameter Modulation Constraints:**
   - FLOW 8 firmware exposes FX engine preset slot selection (Program Change 1..16 on MIDI Channel 13 for FX 1 and Channel 14 for FX 2 — S0 correction; previously stated as Channels 14 and 15) and bus send/return levels (CC 16/17 on Ch 1..7; CC 7 on Ch 11/12).
   - The firmware **does not** expose continuous MIDI CC controllers for internal DSP algorithm parameters (such as reverb decay time in ms, pre-delay, room size, or chorus rate).
   - **S0 CORRECTION (2026-11-18):** the official chart documents two controls per FX engine: CC 1 = Parameter 1 (0–100 %) and CC 2 = Parameter 2 (A/B switch) on Channels 13/14. What each parameter does per preset is UNCONFIRMED, so the statement above holds only for named quantities such as decay time in ms. Snapshot recall is Program Change 1–15 on Channel 16; Program Change 16 resets the mixer and must never be sent.
   - In the application, FX preset profiles (e.g. `fx-vocal-hall`, `fx-quarter-delay`) provide curated starting-point metadata and select the corresponding hardware slot, but do not imply continuous DSP modulation over MIDI.

4. **Channel-Specific Feature Scoping:**
   - **+48V Phantom Power:** Available on Channels 1 and 2 ONLY. The hardware has no relays on Channels 3 through 8.
   - **Analog Preamp Gain & Low Cut:** Available on Channels 1 through 4 ONLY. Channels 5/6 and 7/8 are fixed line-level inputs with digital trim only.
   - **1-Knob Dynamics Compressor:** Verified address available on Channels 1 through 4 ONLY.

5. **EZ-Gain Hardware Boundary:**
   - The EZ-Gain automatic gain calibration routine is an internal firmware state machine executed locally on the hardware via the console button or through proprietary Bluetooth Low Energy (BLE) packets. It cannot be remotely triggered over standard USB MIDI CC.
   - **2026-11-20 note:** the manufacturer documents on hand (E01, E02) do not mention EZ-Gain. A retailer page (E18) says EZ-Gain can switch +48 V on by itself for a condenser mic on ch 1 or 2. This is UNCONFIRMED (conflict C-13).

6. **Mixer state can change outside this application (2026-11-20):**
   - **+48 V:** the manufacturer guide says phantom power "can be activated in the control app" (E01, printed p. 10–11), and EZ-Gain may switch it (UNCONFIRMED, C-13). The mixer does not report +48 V back. This application's +48 V state is therefore never a synchronised mixer reading.
   - **Footswitch snapshots:** in footswitch mode "SNAPSHOT", switch 1 loads the next snapshot and switch 2 the previous one (E01, printed p. 12–13). A snapshot change on the mixer can change every channel value without any message to this application.
   - **Bus limiter / GEQ and FX engines (opened 2026-11-20):** the mixer reports none of them. The console shows `--` (UNSYNCED) until it sends a value, then the commanded value. A change made in the FLOW app, on the mixer or by a footswitch is not seen. FX mute and tap tempo stay locked because they use MIDI channel 16 with the mixer reset.
   - **Consequence:** after any external change, the values this application shows (COMMANDED) may no longer match the mixer. They should be treated as UNSYNCED. No detection exists, because the mixer sends nothing on USB MIDI (C-02); no part of the application may claim that phantom or snapshot state is synchronised.

---

## 2. Platform & Environment Constraints

1. **Windows Multimedia Subsystem (WinMM):**
   - Direct hardware communication relies on `winmm.dll`.
   - WinMM provides exclusive device access: a port opened by one application or handle cannot be simultaneously opened by another handle without closing the first.
   - On non-Windows platforms (macOS/Linux), a mock MIDI backend must be used for offline development.

2. **Tkinter Rendering Engine:**
   - Tkinter Canvas renders vector graphics and geometric controls with sub-millisecond redraws.
   - Tkinter does not provide GPU shader pipelines (DirectX/Metal), blur filters, or native rounded widget styling. All visual glow effects in the CyberNeon theme are implemented via precision multi-layered vector lines.
