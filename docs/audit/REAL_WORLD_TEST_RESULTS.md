# FLOW 8 Real-World Audit — Phase 6 & 7: Test Results & Verification Log

> **S1.1 EVIDENCE CORRECTION (2026-11-18) — historical document, the original text below is unchanged.** Statements in this document about hardware verification (the "Physical Hardware Tests ... PASS" rows and "Live 15-CC Hardware Sweep" (driver acceptance only)) are re-graded under the evidence ladder of `docs/product/FLOW8_EVIDENCE_REGISTER.md`. No raw evidence of a physical effect or of mixer-originated MIDI was found for them. The strongest evidence found is Windows driver acceptance (`midiOutShortMsg` returned 0), which is not hardware verification, DSP confirmation or USB delivery (see `FLOW8_PHASE_C2_IMPLEMENTATION.md`). Read "VERIFIED", "HARDWARE_TESTED" and "passed on physical hardware" here as **PROTOCOL SUPPORTED, driver accepted, not hardware verified**. No inbound telemetry was ever received (evidence E07, E08, E17). Per-claim table: `docs/product/S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

**Document ID:** AUDIT-P6-P7-TESTS  
**Target Branch:** `stage2-mixer-workstation` (`456fd5a`)  
**Total Automated Tests:** 351 (339 Passing + 7 Expected-Failure Defect Reproductions + 5 Hardware Opt-In Tests)  

---

## 1. Test Classification Breakdown (Unit vs. Integration vs. GUI vs. Hardware vs. Manual)

Per Phase 7 strict audit rules, we separate all tests by category and verification method:

| Test Category | Test Files | Test Count | Uses Real Tkinter DOM? | Uses Real `Flow8Service` & `CommandBoundary`? | Uses Physical FLOW 8 Hardware? | Result |
|---|---|---|---|---|---|---|
| **1. Unit Tests** | `test_parameter_mapping.py`, `test_domain_model.py`, `test_state_model.py`, `test_ledger.py`, `test_scenes.py`, `test_controls.py` | 112 | Partial (`test_controls.py`) | Yes (Isolated modules) | No | **112 / 112 PASS** |
| **2. Service & Boundary Integration Tests** | `test_command_boundary_integrity.py`, `test_service_ledger_scenes.py`, `test_state_and_undo_audit.py`, `test_cueair_preset_audit.py`, `test_midi_out_mocked.py` | 91 | No | Yes (Full `Service -> Engine -> Boundary` chain) | No (Offline / Mocked WinMM) | **91 / 91 PASS** |
| **3. GUI & AST Boundary Tests** | `test_app_shell.py`, `test_mixer_console.py`, `test_channel_detail.py`, `test_scene_ui.py`, `test_stage2_ui_controls.py`, `test_safety_dialogs.py` | 136 | **Yes (Real Tk widgets & geometry)** | **Yes (`Flow8Service(auto_connect=False)`)** | No (`ACCEPTED_OFFLINE`) | **136 / 136 PASS** |
| **4. Audit Defect Reproduction Tests** | `test_real_world_audit_defects.py` | 7 | **Yes (Real Tk widgets & geometry)** | **Yes** | No | **7 / 7 REPRODUCED (`expectedFailure`)** |
| **5. Physical Hardware Tests** | `test_hardware_midi_out.py` (`FLOW8_HW_TESTS=1 FLOW8_HW_TESTS_MUTATE=1`) + Live 15-CC Hardware Sweep | 5 (+15 live CCs) | No | **Yes** | **Yes (Physical Behringer FLOW 8)** | **5 / 5 PASS (`0.464s`)** |
| **6. Live GUI Scenario & Multi-Resolution Tests** | Live execution of `Flow8App` across `1600×900`, `1366×768`, `1280×720`, `1024×768` + Scenario B/C simulation | 4 resolutions + 14-step rehearsal | **Yes (Live mapped `Flow8App` + `Flow8Service.connect()`)** | **Yes** | **Yes (Connected `FLOW 8 MIDI OUT` ID 1 / `IN` ID 0)** | **Completed (Exposed Defects D-01..D-14)** |

> **Environmental Note on Screen Capture:** While `Flow8App` mapped its real `tk.Tk` window and computed full pixel geometry via Tk's window manager across all 4 resolutions, the current Windows execution session runs in a non-interactive desktop session where `.NET Graphics.CopyFromScreen` returns `Win32Exception: The handle is invalid`. We therefore recorded exact live Tk root coordinates (`winfo_rootx`, `winfo_width`, `winfo_reqwidth`, `winfo_height`, `winfo_reqheight`) directly from the live mapped widgets rather than fabricating screenshots.

---

## 2. Automated Test Suite Execution Evidence

### 2.1 Defect Reproduction Suite (`tests/test_real_world_audit_defects.py`)
```
$ python -m unittest -v tests/test_real_world_audit_defects.py
test_d01_inbound_midi_fader_updates_strip_widget ... expected failure
test_d02a_preset_apply_refreshes_open_inspector_sliders ... expected failure
test_d02b_undo_refreshes_open_inspector_sliders ... expected failure
test_d03_reset_eq_flat_records_single_atomic_undo_step ... expected failure
test_d04_scene_capture_includes_eq_dynamics_and_sends ... expected failure
test_d05_disconnect_invalidates_open_inspector_provenance_badges ... expected failure
test_d06_strips_not_clipped_at_1366x768_when_inspector_open ... expected failure
----------------------------------------------------------------------
Ran 7 tests in 1.293s

OK (expected failures=7)
```

### 2.2 Physical Hardware Test Suite (`tests/test_hardware_midi_out.py`)
```
$ $env:FLOW8_HW_TESTS="1"; $env:FLOW8_HW_TESTS_MUTATE="1"; python -m unittest tests/test_hardware_midi_out.py
.....
----------------------------------------------------------------------
Ran 5 tests in 0.464s

OK
```

### 2.3 Full Repository Discovery (`351` Total Tests)
- `339` unit/integration/GUI tests pass.
- `7` defect reproduction tests execute and confirm the exact P1 findings (`expected failures=7`).
- `5` physical hardware tests pass when `FLOW8_HW_TESTS=1 FLOW8_HW_TESTS_MUTATE=1` is set (and safely skip by default).


---

## 3. Stage 1 Re-run (after D-01 / D-02 / D-05 fixes)

Command: `python -m unittest discover -s tests -v` (Windows 10, Python 3.14, run this session).

| Category | Count |
|---|---|
| Ran | 366 |
| **Passed** | **358** (includes 15 new tests in `tests/test_stage1_state_sync.py`; the 4 former defect-reproduction tests D-01, D-02a, D-02b, D-05 are now plain passing tests) |
| **Failed / Errors** | 0 |
| **Skipped** | 5 (physical hardware tests, opt-in via `FLOW8_HW_TESTS=1`) |
| **Expected Failure** | 3 (D-03, D-04, D-06 — open defects, NOT counted as passed) |
| **Hardware tests** | **NOT RUN** this stage. No physical FLOW 8 test, no real unplug/replug, no real inbound telemetry was exercised. |

Before the change the same suite was 351 tests: OK, skipped=5, expected failures=7.

Pre-existing noise, unchanged: Tcl `invalid command name "...<lambda>"` messages on window teardown (defect D-14, not fixed).

### New tests (`tests/test_stage1_state_sync.py`)
- Inbound: strip update for fader/mute/pan on the correct strip only; Main fader -> master strip; no `midi_out.send_cc`, no command-log entry, no ledger record from inbound MIDI; missing telemetry stays UNSYNCED and a real `0` is OBSERVED; worker-thread event touches no widget and is applied on the Tk thread.
- Inspector: refresh after preset apply, undo, redo, service-level undo; no widget rebuild; preset dialog passes a refresh callback.
- Disconnect: observed + commanded cleared, history cleared; UI strips/badge/undo button reset; reconnect does not reuse undo; events queued before disconnect cannot resurrect stale values; listener removed on destroy.

### Visual verification
`docs/audit/stage1_screenshots/capture_stage1.py` drives the real `Flow8App` (offline `Flow8Service(auto_connect=False)`) and captures the Tk window with Win32 `PrintWindow` into PNG. 18 files exist: `<size>_{1_main,2_inspector,3_preset,4_undo,5_redo,6_reconnect_unsynced}.png` for `1600x900`, `1366x768`, `1280x720`. Caveats (VERIFIED from script output):
- Screen is 1536x864, so the 1600x900 window is larger than the display (captured offscreen via PrintWindow; image 1616x939 incl. frame).
- The app's minimum size clamps `1280x720` to the same 1382x807 window as `1366x768`; the 1280x720 images are therefore NOT a distinct resolution.
- "Reconnect state" = `service.disconnect()` on the offline service (runs the same reconcile path as connect/disconnect); not a physical unplug.
- The status bar still shows the last feedback text (e.g. "REDO COMMANDED — 4 CHANGES") after disconnect: limitation, not changed.
