# Phase 0: Project Baseline Report

**Date:** 2026-11-18  
**Target Hardware:** Behringer FLOW 8 Digital Mixer (Firmware 11739+)  
**Reference Binary:** CueAir.dmg  
**Host Platform:** Windows 11 Enterprise (x64), Python 3.14.8  
**Repository:** `c:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888`  
**Status:** COMPLETE & VERIFIED

---

## 1. Reference Artifact Verification

- **Target File:** `C:\Users\Administrator\Downloads\03 - Software & Installers\CueAir.dmg`
- **File Size:** 80,728,658 bytes (~77.0 MB)
- **Last Modified:** 2026-11-18 10:05:02 (UTC+7)
- **SHA-256 Hash:**
  `1D0F9E0DD87A38877204592FC08DC72E6AA76A62C76E85E98021B6A6CDEA41EC`
- **Integrity Status:** Verified intact, original file preserved read-only.

---

## 2. Existing Repository State

- **Root Directory:** `c:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888`
- **VCS:** Git
- **Current Branch:** `main` (tracking `origin/main`, up to date)
- **Current Commit:** `cc8a59b` (`feat(ui): scene snapshot bar and thread-safe header connection controls (UI.2-T5)`)
- **Working Tree Cleanliness:** Clean working tree with 1 untracked file (`rea_setup_output.json`). No staged or unstaged modifications to tracked files.
- **Recent Git Log:**
  1. `cc8a59b` - `feat(ui): scene snapshot bar and thread-safe header connection controls (UI.2-T5)`
  2. `0b1c243` - `fix(ui): recognise Ctrl+Z / Ctrl+Y by key code so they work on non-Latin layouts`
  3. `8f039c5` - `fix(ui): keep every strip inside the window; move DEFAULT marker to the MIDI line`
  4. `e14c5bf` - `feat(service,ui): wire undo/redo ledger and scene snapshots into Flow8Service`
  5. `ca8238a` - `Merge origin/main (ledger and scene modules) into feat/ui2-t3-truthful-status-command-log`

---

## 3. Existing Python Architecture & Inventory

The repository contains an established, production-grade Python/Tkinter application (`flow8`) implementing a decoupled architecture for the Behringer FLOW 8 mixer:

### Source Tree (`flow8/`)
- `flow8/__init__.py`: Package metadata, exports.
- `flow8/domain_model.py`: Formal specification of FLOW 8 physical and logical topology (connectors, strips 1-7, master bus 8, aux monitors 9-10, FX send buses 11-12, preamp gain, low cut, 4-band EQ, compressor, phantom power).
- `flow8/midi_constants.py`: WinMM API return codes, callback constants, 12 MIDI channels (0xB0..0xBB), CC 1..17 definitions.
- `flow8/midi_out.py`: Low-latency ctypes-based WinMM `midiOutOpen` / `midiOutShortMsg` / `midiOutClose` wrapper with Windows thread safety.
- `flow8/midi_in.py`: WinMM `midiInOpen` / `midiInStart` callback handler with event buffering and lock-free queueing.
- `flow8/parameter_mapping.py`: Validated mathematical mapping functions, clamp boundaries (0..127), dB/Hz/gain conversions.
- `flow8/parameter_engine.py`: Object-oriented facade for channel-level and bus-level control.
- `flow8/command_boundary.py`: Command validation, rate-limiting, exception containment, audit logging.
- `flow8/state_model.py`: Reactive in-memory state tree representing all channels, buses, faders, mutes, EQs, dynamics, and FX.
- `flow8/ledger.py`: Multi-level undo/redo transaction ledger with inverse-command execution.
- `flow8/scenes.py`: Scene snapshot manager with JSON serialization, slot recall (1..8), and safety diffing.
- `flow8/service.py`: Central coordination service (`Flow8Service`) binding MIDI I/O, domain model, parameter engine, state model, ledger, and scenes.

### UI Subsystem (`flow8/ui/`)
- `flow8/ui/app.py`: Main `Flow8App` Tkinter window with CyberNeon dark design system.
- `flow8/ui/theme.py`: Design tokens, colors (#0F111A, #1A1D2E, #00F0FF neon cyan, #FF0055 neon pink, #7928CA purple), fonts, spacing.
- `flow8/ui/safety_dialogs.py`: Confirmation dialogs for dangerous operations (e.g. +48V Phantom Power activation, loud level jumps).
- `flow8/ui/status.py`: Application state indicators and connection banners.
- `flow8/ui/components/header.py`: Connection controls, MIDI port selector, status badge.
- `flow8/ui/components/mixer_console.py`: 8-strip console (7 input channels + Main bus), motorized fader emulation, mutes, pan, send toggles.
- `flow8/ui/components/channel_detail.py`: Detailed parametric EQ curves, 1-knob compressor controls, preamps, send matrix.
- `flow8/ui/components/controls.py`: Custom vector-styled rotary knobs, toggle buttons, faders.
- `flow8/ui/components/scene_bar.py`: Snapshot store/recall toolbar with visual slot status.
- `flow8/ui/components/command_log.py`: Live MIDI transaction inspector.
- `flow8/ui/components/status_bar.py`: Real-time system latency, buffer status, active port.

---

## 4. Test Suite Baseline

- **Framework:** `unittest` (Python 3.14 standard library)
- **Test Discovery:** `python -m unittest discover -s tests -p "test_*.py"`
- **Total Test Cases:** 303 tests
- **Results:**
  - **Passed:** 298
  - **Skipped:** 5 (hardware-dependent tests requiring physical WinMM loopback or attached USB port)
  - **Failed:** 0
  - **Errors:** 0
  - **Execution Time:** ~37.1s

---

## 5. Scope & Boundary Protection

1. **Original files:** CueAir.dmg will remain uncorrupted and unmodified in its source directory.
2. **Implementation directory:** All modifications will be strictly confined to `flow888` repository.
3. **No destructive replacements:** Existing working business logic (WinMM driver, command boundary, ledger, parameter mappings) is preserved. Any capability adapted from CueAir will enrich and upgrade this foundation.
