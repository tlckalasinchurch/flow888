# Upgraded FLOW 8 Application Architecture

**Target Hardware:** Behringer FLOW 8 Digital Audio Mixer  
**Reference Application:** CueAir (cc.cuetone.cueair)  
**Host Environment:** Windows 11 (x64), Python 3.14.8, WinMM MIDI Subsystem  
**Status:** IMPLEMENTED & TESTED (315 Tests Green)

---

## 1. System Architecture Overview

The upgraded FLOW 8 mixer control workstation uses a strictly decoupled, 9-tier event-driven architecture combining native low-latency Windows MIDI dispatch with CueAir-adapted acoustic processing and safety gates:

```mermaid
flowchart TD
    subgraph Tier1["1. UI Presentation Layer (Tkinter / CyberNeon)"]
        Flow8App["Flow8App (flow8/ui/app.py)"]
        MixerConsole["MixerConsole (components/mixer_console.py)"]
        ChannelDetail["ChannelDetailPanel (components/channel_detail.py)"]
        PresetPicker["PresetPickerDialog (components/preset_picker.py)"]
        SceneBar["SceneBar (components/scene_bar.py)"]
        Header["Header (components/header.py)"]
        CommandLog["CommandLog (components/command_log.py)"]
        StatusBar["StatusBar (components/status_bar.py)"]
    end

    subgraph Tier2["2. Application Service & Orchestration"]
        Service["Flow8Service (flow8/service.py)"]
    end

    subgraph Tier3["3. Acoustic Preset Engine (CueAir Adapted)"]
        Presets["PresetCatalog (flow8/presets.py)"]
        LevelGuard["LevelPreservationGuard (preserveLevels=True)"]
    end

    subgraph Tier4["4. Session & Safety Ledger"]
        Ledger["CommandLedger (flow8/ledger.py - Undo/Redo)"]
        Scenes["SceneManager (flow8/scenes.py - Snapshots)"]
        SafetyGates["SafetyGates (PhantomPower / AnalogGain)"]
    end

    subgraph Tier5["5. Mixer Domain & Parameter Engine"]
        Domain["Hardware Domain Model (flow8/domain_model.py)"]
        ParamEngine["Flow8ParameterEngine (flow8/parameter_engine.py)"]
        Mapping["ParameterMapping (flow8/parameter_mapping.py)"]
    end

    subgraph Tier6["6. Safety Command Boundary"]
        Boundary["Flow8CommandBoundary (flow8/command_boundary.py)"]
        Allowlist["Phase C Allowlist (Active Sanctioned CCs)"]
    end

    subgraph Tier7["7. Hardware State Store"]
        StateStore["Flow8StateStore (flow8/state_model.py)"]
    end

    subgraph Tier8["8. Windows Native MIDI Transport (WinMM)"]
        MidiOut["Flow8MidiOut (midiOutShortMsg - ctypes)"]
        MidiIn["Flow8MidiIn (midiInOpen Callback - ctypes)"]
    end

    subgraph Tier9["9. Physical Hardware"]
        MixerHW["Behringer FLOW 8 Digital Mixer (USB MIDI)"]
    end

    Flow8App --> MixerConsole & ChannelDetail & SceneBar & Header & CommandLog & StatusBar
    ChannelDetail --> PresetPicker
    MixerConsole & ChannelDetail & PresetPicker & SceneBar & Header --> Service
    Service --> Presets & LevelGuard
    Service --> Ledger & Scenes & SafetyGates
    Service --> ParamEngine & StateStore
    ParamEngine --> Domain & Mapping & Boundary
    Boundary --> Allowlist & StateStore & MidiOut
    MidiIn --> Service
    MidiOut --> MixerHW
    MixerHW --> MidiIn
```

---

## 2. Invariant Safety Guarantees

1. **Decoupled UI:** UI components never assemble or transmit raw MIDI bytes directly. All interactions flow through `Flow8Service` $\to$ `Flow8ParameterEngine` $\to$ `Flow8CommandBoundary`.
2. **Level Preservation:** Ported from CueAir's `preserveLevels: true` architecture. Invoking any of the 12 curated audio presets sculpts parametric EQ, low cut, and compressor dynamics while leaving faders, balance, and analog preamp gain untouched.
3. **Hardware State Integrity:** Start-up defaults are classified as unconfirmed app assumptions. Only verified software commands (`commanded_raw_midi`) or incoming physical observations (`observed_raw_midi`) can be captured into scenes or used as undo targets.
4. **Relay Isolation:** +48V phantom power is excluded from the undo ledger and scenes to prevent automated scripts from energizing high-voltage rails without user intent.
