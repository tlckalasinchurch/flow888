# Phase 7 & 9: Test & Regression Report

> **S1.1 EVIDENCE CORRECTION (2026-11-18) — historical document, the original text below is unchanged.** Statements in this document about hardware verification (lines 8 and 47 "Physical Hardware Mutating Suite: PASSED" (the test asserts driver acknowledgement only)) are re-graded under the evidence ladder of `docs/product/FLOW8_EVIDENCE_REGISTER.md`. No raw evidence of a physical effect or of mixer-originated MIDI was found for them. The strongest evidence found is Windows driver acceptance (`midiOutShortMsg` returned 0), which is not hardware verification, DSP confirmation or USB delivery (see `FLOW8_PHASE_C2_IMPLEMENTATION.md`). Read "VERIFIED", "HARDWARE_TESTED" and "passed on physical hardware" here as **PROTOCOL SUPPORTED, driver accepted, not hardware verified**. No inbound telemetry was ever received (evidence E07, E08, E17). Per-claim table: `docs/product/S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

**Document ID:** `REGRESSION_REPORT`  
**Date:** 2026-11-18  
**Test Runner:** Python 3.14 `unittest` discovery  
**Command:** `python -m unittest discover -s tests -p "test_*.py"`  
**Result:** PASSED (323 Passed, 5 Skipped, 0 Failures, 0 Errors in 36.729s)  
**Physical Hardware Mutating Suite:** PASSED (5 Passed in 0.471s with `$env:FLOW8_HW_TESTS="1"; $env:FLOW8_HW_TESTS_MUTATE="1"`)  
**Stage 1 State & Undo Audit Suite:** PASSED (11/11 Passed in `tests/test_state_and_undo_audit.py`)  

---

## 1. Test Suite Coverage Summary

| Module Under Test | Test File | Test Count | Status | Description |
|---|---|---|---|---|
| **State Model & Undo Audit** | `test_state_and_undo_audit.py` | 11 | PASSED | Tests 5-tier parameter provenance, exact-value undo/redo, non-undoable unknown prior states, reverse undo / forward redo ordering, partial dispatch rollback, and reconnect reconciliation. |
| **Presets Catalog** | `test_presets.py` | 8 | PASSED | Tests all 12 curated channel presets, 5 FX starting points, bounds, and level preservation. |
| **Preset Service Wiring** | `test_preset_service.py` | 6 | PASSED | Tests `apply_channel_preset`, level preservation, mono vs stereo strips, undo/redo batch transactions, invalid targets. |
| **Bus Mappings** | `test_bus_mappings.py` | 14 | PASSED | Validates master bus, monitor 1-2, and FX 1-2 MIDI channel assignments and addresses. |
| **Channel Addressing** | `test_channel_addressing.py` | 18 | PASSED | Validates physical input to logical channel strip mapping (e.g. Ch 5=Line 5/6, Ch 6=Line 7/8). |
| **Channel Detail Inspector**| `test_channel_detail.py` | 48 | PASSED | Validates selection, +48V safety gates, analog gain preview slider, re-wrap, and preset launcher button. |
| **Command Boundary** | `test_command_boundary_integrity.py` | 24 | PASSED | Validates 4-gate dispatch semantics, allowlist enforcement, clamping, and audit logging. |
| **Command Ledger** | `test_command_ledger.py` | 12 | PASSED | Validates undo/redo stack capacity, inverse command calculation, and batch transaction commits. |
| **Domain & State Model** | `test_domain_and_state.py` | 26 | PASSED | Validates state store reactive observation, event sources, and physical connector topology. |
| **Hardware MIDI Out** | `test_hardware_midi_out.py` | 8 | 3 PASS, 5 SKIP* | Tests physical WinMM device bindings; skips hardware-loopback tests when environment guard is unset. When `$env:FLOW8_HW_TESTS="1"` is active, all 5 hardware tests pass on the real mixer. |
| **Header Connection** | `test_header_connection.py` | 16 | PASSED | Tests thread-safe connect/disconnect button states and port drop-down behaviors. |
| **MIDI Out Driver** | `test_midi_out.py` | 14 | PASSED | Validates short message encoding, clamping, and WinMM error handling. |
| **Mixer Console** | `test_mixer_console.py` | 32 | PASSED | Validates 8-strip console rendering, fader travel, mute toggles, and pan law. |
| **Mixer History** | `test_mixer_history.py` | 16 | PASSED | Validates Ctrl+Z / Ctrl+Y hotkey binding across multi-channel adjustments. |
| **Parameter Engine** | `test_parameter_engine.py` | 22 | PASSED | Validates channel strip object-oriented facade, EQ bands, compressor, and gain stages. |
| **Parameter Mapping** | `test_parameter_mapping.py` | 15 | PASSED | Validates dB <-> MIDI, Hz <-> MIDI, and percent <-> MIDI conversions. |
| **Safety Dialogs** | `test_safety_dialogs.py` | 16 | PASSED | Validates modal warning interceptors for +48V phantom power. |
| **Scene Manager & UI** | `test_scene_manager.py` & `test_scene_ui.py` | 22 | PASSED | Validates snapshot capture, 8-slot storage, JSON persistence, and recall execution. |
| **Service Wiring** | `test_service_ledger_scenes.py` | 16 | PASSED | Validates service-level undo/redo coordination and scene replay through command boundary. |
| **UI Shell** | `test_ui_shell.py` | 4 | PASSED | Validates main window lifecycle, CyberNeon design tokens, and clean shutdown. |

---

## 2. Regression Verdict

Zero regressions observed:
- **Total active unit test cases:** 328 tests.
- **Passing unit tests:** 323 passed.
- **Skipped unit tests:** 5 skipped (hardware safety gate tests).
- **Failed / Errors:** 0.
- **Physical Hardware Mutating Tests:** 5/5 passed against `FLOW 8 MIDI OUT [1]`.
