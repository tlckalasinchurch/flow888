# Phase 2: CueAir Function & Subsystem Analysis

**Target:** `CueAir.app` & `cueair-mcp`  
**Analysis Framework:** REA (Mach-O Inspection, String Table Analysis, Swift Reflection Ledger, MCP Tool Schemas)  
**Status:** RECONSTRUCTED & VERIFIED

---

## 1. Subsystem Architecture

CueAir is structured into three primary functional layers:
1. **Presentation & Interaction Layer (`CueAir` SwiftUI App):** Declarative UI with reactive state observation (`libswiftObservation`), channel strips, tactile knobs, EQ curves, and speech recognition.
2. **Core Domain & Protocol Layer (`XAirCore`):** Hardware abstraction for digital mixing consoles, UDP/OSC protocol framing, command dispatch, parameter translation, preset engines, and scene serialization.
3. **Agent Automation & Boundary Layer (`cueair-mcp`):** Native Model Context Protocol (MCP) server implementing read/propose/execute workflows with built-in acoustic safety gates and pre-execution snapshots.

---

## 2. Core Functional Modules (A through M)

### A. Mixer Connection and Discovery
- **Evidence:** Mach-O string references to UDP discovery broadcast, port `10023` / `10024`, `/xinfo`, `/xremote`.
- **Observed Behavior:**
  - Emits UDP broadcast `/xinfo` across local network interfaces.
  - Listens for responses containing mixer family (`XR18`, `XR16`, `XR12`, `X32`, `WING`, `CQ`, `TF`).
  - Initiates periodic heartbeat ping (`/xremote` every 9 seconds).
  - Handles network timeout and triggers reconnection backoff without freezing UI.

### B. Mixer State Retrieval
- **Evidence:** `mixer_status` tool in `cueair-mcp`, `/ch/%02d/mix/fader`, `strip_detail`.
- **Observed Behavior:**
  - Queries device capabilities (read/write profile per parameter).
  - Syncs initial strip topologies (input channels, stereo pairs, DCA groups, Aux buses, FX send/returns, Main LR).
  - Maintains local cached mirror of all faders, mutes, pans, and DSP parameters.

### C. Channel Management
- **Evidence:** Swift Reflection `Strip`, `ChannelKind`, `/config/name`, `/config/color`, `/mix/on`, `/mix/fader`, `/mix/pan`.
- **Observed Behavior:**
  - Strict separation between Mono strips, Stereo-linked pairs, and Return channels.
  - Mute toggles (`/mix/on` where `on` is unmuted, `off` is muted).
  - Faders mapped in standard decibels ($-\infty \text{ dB}$ to $+10 \text{ dB}$).
  - Panning mapped as `L100` .. `C` .. `R100`.

### D. EQ Processing and Parameter Control
- **Evidence:** `/eq/on`, `/eq/1/f`, `/eq/1/g`, `/eq/1/q` .. `/eq/4/q`, `/preamp/hpf`.
- **Observed Behavior:**
  - 4-Band Parametric EQ with selectable filter topologies (Low Cut / Shelf, PEQ, High Shelf).
  - Frequency bounds: $20 \text{ Hz}$ to $20,000 \text{ Hz}$.
  - Gain bounds: $-15 \text{ dB}$ to $+15 \text{ dB}$.
  - Quality factor ($Q$): $0.3$ to $10.0$.
  - Independent High-Pass Filter (Low Cut): $20 \text{ Hz}$ to $400 \text{ Hz}$.

### E. Dynamics Processing (Compressor & Gate)
- **Evidence:** `/dyn/on`, `/dyn/thr`, `/dyn/ratio`, `/dyn/knee`, `/dyn/mgain`, `/dyn/attack`, `/dyn/release`, `/gate/on`, `/gate/thr`.
- **Observed Behavior:**
  - Compressor threshold: $-60 \text{ dB}$ to $0 \text{ dB}$.
  - Ratio choices: `1.1, 1.3, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10, 20, 100`.
  - Auto-makeup gain ($M_{\text{gain}}$): $0 \text{ dB}$ to $24 \text{ dB}$ to compensate for gain reduction.
  - Expander/Noise Gate threshold: $-80 \text{ dB}$ to $0 \text{ dB}$.

### F. Effects and FX Engine
- **Evidence:** `cuetone-fx-xair.json`, `cuetone-fx.json`, `propose_fx_preset`, `/fx/N/type`.
- **Observed Behavior:**
  - Algorithm categories: `reverb` (Room, Plate, Hall, Chamber), `delay` (Stereo, Tap, Slapback), `modulation` (Chorus, Flanger).
  - Use-case tagged: `speech`, `vocal`, `ballad`, `worship`, `pop`.
  - Send/Return vs Insert placement modes.

### G. Routing Matrix
- **Evidence:** Aux sends `/mix/01~06/level`, FX sends `/mix/07~10/level`, Main LR routing `/mix/lr`.
- **Observed Behavior:**
  - Independent send levels per channel to Monitor Aux buses and FX processors.
  - Pre-fader vs Post-fader send taps.

### H. Main and Bus Controls
- **Evidence:** `/lr/mix/fader`, `/bus/NN/mix/fader`, 9-band GEQ, Limiter on output buses.
- **Observed Behavior:**
  - Dedicated master fader and mute for Main LR.
  - Dedicated bus master levels for Aux Monitors.

### I. Scene and Preset Handling
- **Evidence:** `cuetone-basic.cueairpreset`, `scene_save`, `scene_advance`, `scene_card`.
- **Observed Behavior:**
  - 50 curated channel strip presets.
  - **Level Preservation Rule (`preserveLevels: true`):** Applying a channel preset updates EQ, dynamics, HPF, and gate while preserving fader level, pan, and preamp gain.
  - Pre-change snapshot automation ("BEFORE AI" / "BEFORE RECALL").

### J. Monitoring & Metering
- **Evidence:** Audio VU meters, peak indicators, Solo/PFL bus routing.
- **Observed Behavior:** Real-time peak level monitoring per channel.

### K. Real-Time Synchronization & Safety
- **Evidence:** `propose_changes`, `confirmRequired`, `requiresOperatorReview`.
- **Observed Behavior:**
  - "Staged Plan -> User Preview -> Operator Confirm -> Mixer Commit".
  - Out-of-range clamping and immediate rollback upon communication error.

### L. AI & Natural Language Assistance ("CueAi")
- **Evidence:** Embedded `cueair-mcp` tools, speech dictation (`Speech.framework`), localized prompt engineering.
- **Observed Behavior:**
  - Translates natural language engineering requests (e.g., "Add vocal warmth", "Fix boominess on speech mic") into precise parametric adjustments.
  - Enforces acoustic safety rules (refuses chat-driven automatic monitoring gain jumps).
