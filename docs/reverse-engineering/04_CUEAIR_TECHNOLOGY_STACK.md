# Phase 1: CueAir Technology Stack Analysis

**Document ID:** `04_CUEAIR_TECHNOLOGY_STACK`  
**Target:** `CueAir.app`  
**Verdict:** Native macOS Swift / SwiftUI Application with Modern Concurrency & Embedded MCP Engine

---

## 1. Runtime Framework Identification

Based on static analysis of Mach-O load commands (`LC_LOAD_DYLIB`), runtime metadata, and linked dynamic libraries:

| Subsystem | Framework / Library | Role & Observed Evidence |
|---|---|---|
| **UI Framework** | `SwiftUI.framework` + `AppKit.framework` | Pure declarative SwiftUI desktop interface with custom canvas controls, vector dials, and dark mode palette. |
| **Observation & State** | `libswiftObservation.dylib` | Swift 5.9+ `@Observable` macro state modeling for high-performance reactive UI updates without Combine overhead. |
| **Concurrency** | `libswift_Concurrency.dylib` | Modern Swift async/await actor model (`MainActor`, async task groups, isolated network loops). |
| **Audio & Device I/O** | `AVFAudio.framework`, `AVFoundation.framework` | Host audio monitoring, level metering, and audio session management. |
| **MIDI Transport** | `CoreMIDI.framework`, `libswiftCoreMIDI.dylib` | Hardware MIDI controller integration, MIDI clock, fader wing synchronization. |
| **Networking & Protocols** | `Network.framework` | Native NWConnection / NWListener for low-latency UDP OSC (Open Sound Control) messaging. |
| **AI & Natural Language** | `Speech.framework` | Local on-device dictation and voice speech-to-text for AI mixer prompt control. |
| **Security & Identity** | `CryptoKit.framework`, `Security.framework` | Preset signing, license verification, secure storage. |
| **Agent Automation** | Embedded `cueair-mcp` | Native MCP server providing programmatic mixer access for AI agents (Claude Code, Cursor, Antigravity). |

---

## 2. Comparison with FLOW 8 Architecture

| Dimension | CueAir (macOS Reference) | Current FLOW 8 Project (`flow888`) | Adaptation Strategy for FLOW 8 |
|---|---|---|---|
| **Language & Runtime** | Swift 6, macOS Sequoia (15+) | Python 3.14, Windows 11 (x64) | Maintain Python 3.14 runtime; adapt Swift architectural patterns to Python object model. |
| **UI Framework** | SwiftUI retained canvas | Tkinter CyberNeon vector canvas | Enhance Tkinter CyberNeon with CueAir's channel strip ergonomics, EQ curve overlays, and preset browser. |
| **Mixer Protocol** | UDP OSC (Behringer XR/X-Air `10023`) | Class-Compliant USB MIDI CC (WinMM) | Map CueAir parameter semantics (EQ, Dynamics, FX, Presets) to FLOW 8 MIDI CC (Channels 1-12). |
| **State Management** | Swift `@Observable` Actors | Reactive `Flow8StateModel` + Thread Lock | Both use thread-safe reactive models. Adapt CueAir's dirty-tracking and safety verification. |
| **History & Undo** | Local state snapshotting | `CommandLedger` with inverse execution | FLOW 8's ledger is already highly capable; integrate CueAir's multi-parameter preset undo. |
| **Channel Presets** | 50 curated `.cueairpreset` strips | Basic manual channel parameters | Port CueAir's 50 audio-engineered presets into FLOW 8's native parameter engine! |
| **Effects (FX)** | Multi-engine OSC starting points | Fixed FX 1 (Reverb) & FX 2 (Delay) | Implement CueAir-style FX starting points adapted to FLOW 8's FX1/FX2 parameter spaces. |
