# FLOW 8 Real-World Audit — Phase 0: Repository & Baseline Audit

**Document ID:** AUDIT-P0-BASELINE  
**Target Repository:** `https://github.com/tlckalasinchurch/flow888`  
**Target Branch:** `stage2-mixer-workstation`  
**Verified HEAD Commit:** `456fd5aef669612b786d94369bc7487c8c337698` (`456fd5a`)  
**Audit Date:** 2026-11-18  

---

## 1. Git Repository & Commit Verification

Independent inspection of the working tree and Git history confirms:

- **Current Branch:** `stage2-mixer-workstation`
- **Working Tree Status:** Clean (`nothing to commit, working tree clean` prior to audit artifacts)
- **Commit `456fd5a` Verified:** Present at `HEAD` (`456fd5aef669612b786d94369bc7487c8c337698`)

### Recent Commit History
| Commit Hash | Summary |
|---|---|
| `456fd5a` | `feat(stage-2): implement professional mixer workstation UX/UI, DSP controls, and provenance badges` |
| `d18a37c` | `feat(stage-1): implement 5-tier parameter provenance and exact-value undo/redo with rollback` |
| `6077b2b` | `checkpoint: verified Phase 8 baseline with physical hardware audit` |
| `cc8a59b` | `feat(ui): scene snapshot bar and thread-safe header connection controls (UI.2-T5)` |
| `0b1c243` | `fix(ui): recognise Ctrl+Z / Ctrl+Y by key code so they work on non-Latin layouts` |
| `8f039c5` | `fix(ui): keep every strip inside the window; move DEFAULT marker to the MIDI line` |
| `e14c5bf` | `feat(service,ui): wire undo/redo ledger and scene snapshots into Flow8Service` |
| `ca8238a` | `Merge origin/main (ledger and scene modules) into feat/ui2-t3-truthful-status-command-log` |

---

## 2. Application Entry Point & Architecture Map

### 2.1 Actual Application Entry Point
- **Primary Entry Point:** `flow8/ui/app.py` (`main()` at line 425, invoked via `python -m flow8.ui.app`).
- Launches `Flow8App(connect_hardware=True, show_placeholder=False)`, which initializes `Flow8Service(auto_connect=False)` and spawns a background daemon thread (`flow8-connect`) to open WinMM MIDI endpoints without blocking the Tkinter event loop.

### 2.2 Complete UI Component Hierarchy
```
tk.Tk (root) — Window: "FLOW 8 — Cyber Neon Workstation" (default 1600×900, minsize 1366×768)
├── Header (flow8/ui/components/header.py) [row=0, col=0, sticky="ew"]
│   ├── Identity Band ("FLOW 8 | CYBER NEON WORKSTATION | Behringer FLOW 8")
│   ├── Connection Controls ("CONNECT", "DISCONNECT", "RETRY")
│   └── Device Status Pill (Canvas dot + "MIDI PORTS CLOSED / OPEN / PARTIAL / ERROR")
├── Body Frame [row=1, col=0, sticky="nsew"]
│   ├── Navigation Rail (flow8/ui/components/navigation.py) [row=0, col=0, sticky="nsw"]
│   │   ├── "Mixer" (enabled=True)
│   │   ├── "Routing" (enabled=False, "NOT IMPLEMENTED")
│   │   ├── "FX" (enabled=False, "NOT IMPLEMENTED")
│   │   ├── "Scenes" (enabled=False, "NOT IMPLEMENTED")
│   │   └── "Recording" (enabled=False, "NOT IMPLEMENTED")
│   └── Workspace Frame [row=0, col=1, sticky="nsew"]
│       └── MixerConsole (flow8/ui/components/mixer_console.py)
│           ├── Console Banner Row
│           │   ├── Title ("FLOW 8 MIXER CONSOLE", "7 LOGICAL STRIPS + MAIN L/R MASTER")
│           │   ├── History Frame ("↶ UNDO", "↷ REDO")
│           │   ├── SceneBar (flow8/ui/components/scene_bar.py) — Slots 1..8, "CAPTURE", "RECALL"
│           │   └── Warning Label ("UNSYNCED · COMMAND VALUES ONLY")
│           ├── Middle Band (_middle)
│           │   ├── Strips Container (8 columns uniform="strip")
│           │   │   ├── Strip 1..7: ChannelStripWidget (Mic 1, Mic 2, Line 3, Line 4, Ch 5/6, Ch 7/8, USB/BT)
│           │   │   └── Strip 8: ChannelStripWidget (Main L/R Master)
│           │   └── ChannelDetailPanel (flow8/ui/components/channel_detail.py) [docks right when selected]
│           │       ├── Header ("CHANNEL DETAIL", "CLOSE ✕", Title, Subtitle)
│           │       ├── Preset Button ("★ ACOUSTIC PRESETS (CueAir)") -> opens PresetPickerDialog
│           │       ├── Tab Bar ("PREAMP", "EQ", "DYN", "SENDS")
│           │       ├── Tab 1: Preamp & +48V (+48V button -> PhantomPowerConfirmationDialog, Gain Preview slider)
│           │       ├── Tab 2: 4-Band Parametric EQ (Reset Flat button + 4 HorizontalSliders + EQ ProvenanceBadge)
│           │       ├── Tab 3: HPF & Dynamics (Low Cut UnipolarSlider + Bypass, Compressor UnipolarSlider + Bypass)
│           │       ├── Tab 4: Aux Sends (Mon 1, Mon 2, FX 1, FX 2 UnipolarSliders + Send ProvenanceBadge)
│           │       └── Footer (Legend + Error Label)
│           └── CommandLogPanel (flow8/ui/components/command_log.py)
│               ├── Heading ("COMMAND LOG", Legend badges, Connection Notice, Event Counter)
│               └── ttk.Treeview (8 columns: TIME, PARAMETER, CMD, OBSERVED, MIDI CH/CC·DATA, DISPATCH, HW APPLIED, ERROR)
└── StatusBar (flow8/ui/components/status_bar.py) [row=2, col=0, sticky="ew"]
    ├── Transport Fields (MIDI OUT, MIDI IN, MIDI ERROR, USB AUDIO, AUDIO TELEMETRY, HARDWARE OBSERVATION)
    └── Feedback Label (right-aligned, auto-truncating with ellipsis)
```

---

## 3. Backend & MIDI Transport Architecture

| Module | File | Role & Audit Findings |
|---|---|---|
| **Domain Model** | `flow8/domain_model.py` | Defines the 7 logical input channels (`1: Mic 1`, `2: Mic 2`, `3: Line 3`, `4: Line 4`, `5: Ch 5/6`, `6: Ch 7/8`, `7: USB/BT`) and maps them to 1-based MIDI channels `1..7`. |
| **MIDI Constants** | `flow8/midi_constants.py` | Defines WinMM error codes, MIDI channels `1..12`, CCs `1..17`, value limits, and endpoint names (`FLOW 8 MIDI IN`, `FLOW 8 MIDI OUT`). |
| **Parameter Mapping** | `flow8/parameter_mapping.py` | Pure functions converting between raw MIDI (`0–127`) and engineering units (`dB`, `%`, `Hz`, `bool`). |
| **State Model** | `flow8/state_model.py` | Thread-safe `Flow8StateStore` maintaining `ParameterState` records with 5-tier `ParameterProvenance` (`UNSYNCED`, `COMMANDED`, `OBSERVED`, `DISPATCH_FAILED`, `UNSUPPORTED`). |
| **Command Boundary** | `flow8/command_boundary.py` | Enforces `ACTIVE_ALLOWLIST` (85 parameter IDs), validates ranges/types, dispatches via `Flow8MidiOut.send_cc`, and appends `CommandLogEntry` records. |
| **Parameter Engine** | `flow8/parameter_engine.py` | High-level fluent API (`engine.channel(n).set_*`, `engine.set_main_*`, `engine.set_bus_fader`) converting engineering units and routing through `Flow8CommandBoundary`. |
| **Command Ledger** | `flow8/ledger.py` | 50-slot bounded undo/redo stack with gesture batching (`begin_batch`/`end_batch`), non-undoable unknown baselines, and compensating rollback on partial failure. |
| **Scene Manager** | `flow8/scenes.py` | In-memory 8-slot snapshot store (`ALLOWED_PARAMETERS = {"fader", "pan", "mute"}`). |
| **Presets** | `flow8/presets.py` | Curated CueAir-adapted channel presets (10 presets across 6 categories) and 6 reference FX profiles. |
| **Application Service** | `flow8/service.py` | `Flow8Service` facade coordinating connection lifecycle, outbound setter methods, inbound MIDI CC callback (`_on_midi_in_event`), presets, scenes, and undo/redo. |
| **MIDI Out / In** | `flow8/midi_out.py`, `flow8/midi_in.py` | `ctypes.windll.winmm` wrappers (`midiOutOpen`, `midiOutShortMsg`, `midiInOpen`, `midiInStart`). |

---

## 4. Hardware Parameter Support Matrix (Code vs. Protocol vs. UI)

| Parameter Family | Hardware / Protocol Support | Allowlisted in `CommandBoundary` | Exposed in `Flow8Service` | Exposed & Operational in UI |
|---|---|---|---|---|
| Input Faders (Ch 1–7, CC 7) | Yes (R/W with USB TX) | Yes (`ch1..7.fader`) | Yes (`set_fader`) | **Outbound Only** (Inbound UI sync broken — see Defect D-01) |
| Input Mute (Ch 1–7, CC 5) | Yes (R/W with USB TX) | Yes (`ch1..7.mute`) | Yes (`set_mute`) | **Outbound Only** (Inbound UI sync broken — see Defect D-01) |
| Input Pan/Bal (Ch 1–7, CC 10) | Yes (R/W with USB TX) | Yes (`ch1..7.pan`) | Yes (`set_pan`) | **Outbound Only** (Inbound UI sync broken — see Defect D-01) |
|Input Solo (Ch 1–7, CC 6) | Defined in `midi_constants.py` | **No** | **No** | **Missing from UI** |
| +48V Phantom (Ch 1–2, CC 12) | Yes (Write-only relay) | Yes (`ch1..2.phantom`) | Yes (`set_phantom`) | **Yes** (Behind confirmation dialog) |
| Preamp Gain (Ch 1–4, CC 8) | Yes (Write-only) | Yes (`ch1..4.gain`) | Yes (`set_gain`) | **No — Gated/Disabled in UI** (`PREVIEW ONLY`) |
| Low Cut HPF (Ch 1–4, CC 9) | Yes (Write-only) | Yes (`ch1..4.low_cut`) | Yes (`set_low_cut`) | **Yes** (In Inspector `DYN` tab) |
| 1-Knob Compressor (Ch 1–4, CC 11) | Yes (Write-only, 0–100) | Yes (`ch1..4.compressor`) | Yes (`set_compressor`) | **Yes** (In Inspector `DYN` tab) |
| 4-Band PEQ (Ch 1–7, CC 1–4) | Yes (Write-only) | Yes (`ch1..7.eq_*`) | Yes (`set_eq_band`) | **Yes** (In Inspector `EQ` tab) |
| Aux Sends (Ch 1–7, CC 14–17) | Yes (Write-only) | Yes (`ch1..7.send_*`) | Yes (`set_send`) | **Yes** (In Inspector `SENDS` tab) |
| Main L/R Fader & Bal (Ch 8, CC 7, 10) | Yes (R/W with USB TX) | Yes (`main.fader`, `main.balance`) | Yes (`set_fader`, `set_pan`) | **Outbound Only** (Inbound UI sync broken — see Defect D-01) |
| Bus Master Faders (MON 1/2, FX 1/2, Ch 9–12, CC 7) | Yes | Yes (`mon1..fx2.fader`) | **No** (In `ParameterEngine` only) | **Missing from UI** |
| Main/Mon 9-Band GEQ (Ch 8–10, CC 11–19) | Yes (`midi_out.py` line 250) | **No** | **No** | **Missing from UI** |
| FX Preset Selection & Tap Tempo | Program Change / CC | **No** | Reference profiles only | **Missing from UI** |
| Level Meters / Peak Telemetry | Not available over USB MIDI CC | N/A | N/A | Honest `NO TELEMETRY` status |
