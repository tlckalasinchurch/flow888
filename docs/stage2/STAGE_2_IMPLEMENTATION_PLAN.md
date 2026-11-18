# FLOW 8 Stage 2: Implementation Plan
**Document ID:** STAGE2-PLAN-01  
**Project:** Behringer FLOW 8 Digital Mixer Workstation  
**Harness:** Antigravity Engineering Agent  
**Branch:** `stage2-mixer-workstation`  
**Status:** Executed & Verified  

---

## 1. Executive Summary & Objectives

The Stage 2 mission elevates the Behringer FLOW 8 desktop controller into a professional digital audio mixing workstation. Following the completion of Stage 1 (which established a 5-tier state provenance model and exact-value undo/redo with rollback), Stage 2 implements the full UX/UI control surface, adds missing channel DSP controls (4-Band Parametric EQ, Low Cut HPF, 1-Knob Dynamics Compressor, 4 Aux Sends), visual parameter provenance feedback, and dedicated console history controls.

### Core Objectives
1. **Full DSP Control Surface in Channel Inspector:**
   - 4-Band Parametric EQ (Low, Low-Mid, Hi-Mid, High) with dB readouts and "Reset Flat" button.
   - Low Cut Filter / HPF (20–600 Hz) with Bypass button (Channels 1–4).
   - 1-Knob Dynamics Compressor (0–100%) with Bypass button (Channels 1–4).
   - 4 Aux Sends (Mon 1, Mon 2, FX 1, FX 2) with dB readouts (Channels 1–7).
2. **Visual Parameter Provenance & Confidence Badges:**
   - Visual badges for `● OBS`, `▲ CMD`, `○ UNSYNC`, `✕ FAIL`, `— N/A`, and `⚠ WARN`.
   - Clear distinction between hardware-observed telemetry and commanded software state.
3. **Console-Level History Controls:**
   - Dedicated visual Undo (`↶ UNDO`) and Redo (`↷ REDO`) buttons in the console banner row.
   - Dynamic activation based on transaction ledger availability (`ledger.can_undo` / `ledger.can_redo`).
4. **Ergonomic Pro-Mixer Navigation & Responsive Layout:**
   - Tabbed inspector subsections: `[PREAMP & +48V]`, `[4-BAND EQ]`, `[HPF & COMP]`, `[AUX SENDS]`.
   - Guaranteed zero-clipping layout compliance down to 1366×768 resolution.
   - 100% preservation of all Stage 1 state provenance and exact-value undo invariants.

---

## 2. Work Breakdown Structure (WBS) & Milestones

| Phase | Description | Deliverables | Verification |
|---|---|---|---|
| **Phase 0** | System & Baseline Audit | `STAGE_2_EXISTING_SYSTEM_AUDIT.md` | Codebase inspection & test suite audit |
| **Phase 1** | Design System Definition | `STAGE_2_DESIGN_SYSTEM.md` | Token hierarchy, palette, typography |
| **Phase 2** | UI Component Architecture | Controls upgrade (`UnipolarSlider`, `ProvenanceBadge`) | Unit tests in `test_controls.py` |
| **Phase 3** | Channel Inspector Overhaul | Tabbed DSP controls in `ChannelDetailPanel` | Regression & AST tests in `test_channel_detail.py` |
| **Phase 4** | Mixer Console & Master Section | History buttons, strip badges, layout tuning | `test_mixer_console.py`, `test_scene_ui.py` |
| **Phase 5** | Stage 2 Automated Test Suite | `tests/test_stage2_ui_controls.py` (16 tests) | 16/16 unit tests passing |
| **Phase 6** | Hardware Verification | Real hardware tests on physical FLOW 8 | `tests/test_hardware_midi_out.py` passing |
| **Phase 7** | Documentation & Reporting | Architectural, test, and verification reports | Documentation suite in `docs/stage2/` |

---

## 3. Scope & Boundary Enforcement

### Strictly In-Scope
- Implementation of presentation widgets in `flow8/ui/components/` routing exclusively through `Flow8Service`.
- 4-Band Parametric EQ on Channels 1–7 (Low: CC 1, Low-Mid: CC 2, Hi-Mid: CC 3, High: CC 4).
- Low Cut Filter on Channels 1–4 (CC 9, 20–600 Hz, raw 0–127).
- 1-Knob Dynamics Compressor on Channels 1–4 (CC 11, 0–100%, raw 0–100).
- Aux Sends on Channels 1–7 (Mon 1: CC 14, Mon 2: CC 15, FX 1: CC 16, FX 2: CC 17).
- Tabbed inspector organization to guarantee responsive layout without vertical clipping.
- Automated tests covering every new widget, command path, and state transition.

### Strictly Out-of-Scope (Forbidden)
- Bypassing `Flow8Service`, `Flow8ParameterEngine`, or `Flow8CommandBoundary`.
- Calling WinMM or MIDI driver APIs directly from UI components.
- Simulating or fabricating hardware-observed telemetry when physical USB TX is unobserved.
- Permitting unsupported hardware operations (e.g. EQ or sends on Main L/R, phantom on channels 3–8).
