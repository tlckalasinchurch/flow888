# S1.2 File Change Map

Date: 2026-11-18. Preparation only: **nothing in this list has been changed.** Line numbers refer to the files as read this session (before any S1.2 edit; the Stage 1 edits are already in the working tree). Design: `S1_2_IMPLEMENTATION_PLAN.md`. Tests: `S1_2_SAFETY_TEST_SPEC.md`, `S1_2_REGRESSION_MIGRATION_PLAN.md`.

## 1. New files

| File | Content | Imports | Notes |
|---|---|---|---|
| `flow8/safety.py` | Policy constants (`BLOCKED_PARAMETER_TYPES`, allowed pairs derived from the boundary allowlist), `check_parameter`, `validate_outbound`, moved `PhantomPowerConfirmationToken`, `_PhantomPendingRequest`, `PhantomPowerSafetyGate`, private grant and permit helpers | stdlib (`contextvars`, `dataclasses`, `time`), `flow8.midi_constants` | No tkinter. No `os`/`sys.argv`/environment access. `__all__` excludes grant and permit helpers |
| `tools/__init__.py` | empty | — | marks the directory; excluded from the PyInstaller bundle (spec bundles `main.py` only) |
| `tools/README.md` | Restrictions: read-only by default, no arbitrary MIDI, unique output files | — | |
| `tools/flow8_midi_harness.py` | Copy of the harness with `send_short_msg` guarded by `validate_outbound`, explicit `--allow-write`, exclusive-create output | `flow8.safety` (tools → flow8 only) | Original stays at its old path until the owner approves removal (see §3) |
| `tools/flow8_midi_in_logger.py` | Copy of the read-only logger with unique output | `flow8.midi_in` | same |
| `tools/hw_verify_stage1.py`, `tools/capture_stage1.py` | Copies of the Stage 1 scripts with unique names and exclusive create | `flow8.*` | originals under `docs/audit/stage1_screenshots/` stay (evidence of how the data was produced) |
| `tools/run_tests_no_hw.py` | Runs `unittest` discovery with `Flow8MidiOut.open` and `Flow8MidiIn.open` patched to fail loudly; prints the number of attempted opens | `unittest`, `flow8` | proves "no test opens a physical MIDI port" for the whole suite |
| `tests/_no_hardware.py` | Module-level guard used by safety tests (patches the two `open` methods and the `winmm.midiOutOpen` / `midiInOpen` lookups to raise) | `unittest.mock` | |
| `tests/_safety_helpers.py` | `authorize_phantom_on(service_or_engine, channel)` that goes through the **real** gate (`issue_token` → `confirm_and_dispatch`) with a duck-typed adapter; `record_driver_calls(service)` | `flow8.safety` | no bypass flag; reused by migrated tests |
| `tests/test_s12_safety_boundary.py` | gain block, phantom grant, ledger, undo/redo, presets, scenes | see spec | |
| `tests/test_s12_safety_messages.py` | message-type policy, 37 pairs, reset, structural scans | see spec | |
| `tests/test_s12_tools_evidence.py` | harness/logger/capture scripts, evidence hashes, unique files | see spec | |
| `docs/product/rollback_s1_2/<timestamp>/` | Copies of files about to change plus `MANIFEST.sha256` | — | created in step 0; also protects uncommitted Stage 1 work |

## 2. Modified files

| # | File | Location | Change | Risk | Covered by |
|---|---|---|---|---|---|
| 1 | `flow8/command_boundary.py` | `import` block (line 22–35); `execute_command` at 258: new step before "1. Allowlist Validation" (line 275) and around the dispatch at 403–409 | `safety.check_parameter(param_id, value)` raising `Flow8CommandRejectedError` and logging REJECTED for gain and for phantom ON without grant; after value validation consume the grant and open the one-shot permit around `send_cc`; close in `finally`. **Allowlist (`_build_phase_c_allowlist`, line 123) is not extended** | High: central path; every command passes here | B-01…B-08, M-03 |
| 2 | `flow8/midi_out.py` | `send_cc` at 214; the hard-coded set at 234–254 | Replace by `safety.validate_outbound(0xB0\|(ch-1), cc, value)` (accepted set = allowlist minus blocked); phantom ON requires the permit; keep error type `Flow8ValidationError`; keep the seven helpers | High: low-level; one allow-list instead of two | M-02, M-04 |
| 3 | `flow8/service.py` | `set_gain` at 334; `_replay` at 531; imports at 20–29 | `set_gain` raises the policy rejection as its first statement; `_replay` unchanged (it reaches the same refusal); `set_phantom` (322) unchanged | Medium | B-02, B-05 |
| 4 | `flow8/ledger.py` | `CommandRecord.undoable` at 30–36 | Add `gain` next to `phantom_power` so no gain record can be created | Low | B-06 |
| 5 | `flow8/ui/safety_dialogs.py` | classes at 25–160 (`PhantomPowerConfirmationToken`, `_PhantomPendingRequest`, `PhantomPowerSafetyGate`) | Remove the definitions, `from flow8.safety import PhantomPowerConfirmationToken, PhantomPowerSafetyGate` and re-export (`__all__`); keep `PhantomPowerConfirmationDialog` and `AnalogGainSafetyGate`; `is_verified_mapping_available()` (323) returns the policy constant | Medium: identity must be preserved for tests | M-06, existing `test_safety_dialogs.py` |
| 6 | `flow8/ui/components/channel_detail.py` | import at 41; `EQ_BANDS` at 153–158 (title used at 552) | Import path may stay (re-export); labels become "BAND 1", "BAND 2", "BAND 3", "BAND 4" (D5) | Low | L-01, L-02 |
| 7 | `flow8_midi_harness.py` (repo root) | whole file | Not modified in place. Original kept until the owner approves its removal; a notice comment is **not** added in step 6 so the evidence-era file remains bit-identical. The safe copy lives in `tools/` | Low | E-01…E-04 |
| 8 | `flow8_midi_in_logger.py` (repo root) | same | same | Low | E-05 |
| 9 | Documents that reference the old harness path (`FLOW8_PHASE1_MIDI_TEST_RESULTS.md`, `FLOW8_PHASE2A_IMPLEMENTATION.md`, `FLOW8_PHASE_UI1_REPOSITORY_AUDIT.md`) | top of file | Errata block only (original text unchanged) | Low | doc check |
| 10 | `docs/product/FLOW8_SAFETY_POLICY.md`, `FLOW8_CAPABILITY_MATRIX.md`, `FLOW8_UNRESOLVED_CONFLICTS.md`, `S1_ACCEPTANCE_REPORT.md` | enforcement tables | Update the enforcement-state columns after the tests pass (SR-05, SR-06, G-01…G-07) | Low | acceptance |

## 3. Files deliberately not changed

| File | Reason |
|---|---|
| `flow8/parameter_engine.py` | Its `set_gain` and `set_phantom` already route through the boundary; the boundary is the single choke point. Editing it would add a second place to maintain |
| `flow8/scenes.py` | `ALLOWED_PARAMETERS = {fader, pan, mute}` already excludes gain and phantom; a test guards it |
| `flow8/presets.py` | Writes only EQ, low cut, compressor; structural preset rules belong to S2 |
| `flow8/command_boundary._build_phase_c_allowlist` | Owner: do not expand the boundary |
| `flow8/midi_in.py`, `flow8/state_model.py`, `flow8/parameter_mapping.py` | No safety change; mapping approximations stay (C-05, C-12) |
| Evidence files (`FLOW8_PHASE1_RAW_MIDI_LOG.md`, `FLOW8_PHASE2B_RAW_MIDI_LOG.md`, `docs/audit/hw_stage1/*`, `docs/product/sources/*`) | Never opened for writing; hashes recorded |
| `FLOW8-CyberNeon.spec`, `main.py` | No change: packaging bundles `main.py` and its imports only |

## 4. Import graph delta

```
before:  ui/channel_detail ─> ui/safety_dialogs        service ─> command_boundary ─> midi_out
after:   ui/safety_dialogs ─> safety  <─ command_boundary, midi_out, ledger, service
         ui/channel_detail ─> ui/safety_dialogs (re-export, unchanged import line)
         tools/*           ─> safety, flow8.*          (flow8/ never imports tools/)
         safety imports: stdlib + midi_constants only (no cycles)
```

A circular-import check (`python -c "import flow8.safety, flow8.midi_out, flow8.command_boundary, flow8.ledger, flow8.service, flow8.ui.safety_dialogs"`) is a step-2 gate.

## 5. Move strategy for `tools/` (references checked)

| Reference | Kind | Action |
|---|---|---|
| Python imports of `flow8_midi_harness` or `flow8_midi_in_logger` | none found (search of all `.py`) | none |
| Documents naming the harness | 3 historical + product documents | errata block, no text change |
| PyInstaller spec | bundles `main.py` only | none |
| `python flow8_midi_in_logger.py` run by hand (used on 2026-11-18 through a wrapper) | operator habit | `tools/README.md` gives the new command |

Original root files stay until the owner approves removal, so no evidence-era file disappears.

## 6. Option O1 (decision for the owner)

Token minting only by the dialog: `PhantomPowerSafetyGate.issue_token` would require a `_DialogProof` object that only `PhantomPowerConfirmationDialog` creates, so a script cannot mint a valid token without opening the dialog. Cost: one extra private class and an adapter for the Inspector path (`channel_detail.py` calls `issue_token` itself before opening the dialog, lines near 926 of the file as read). Benefit: closes the "script mints its own token" route. Default if the owner does not answer: **not included**; the residual risk is documented.

## 7. Change size estimate

New code: about 250 lines in `flow8/safety.py` (mostly moved), about 120 lines of edits across the four core files, about 60 lines in the UI files, tests about 600 lines, tools about 300 lines (copies with guards). Estimates only (ASSUMPTION).

## Deviations from this map found during implementation (2026-11-18)

- `flow8/safety.py` derives its (channel, CC) tables **lazily** from the boundary allowlist (an import inside a function) because the boundary imports `safety`; no cycle exists at import time.
- `authorize_command` treats only `True` or integer `1` as +48V ON (anything else is OFF or fails value validation first), so out-of-range phantom values keep raising `Flow8ValidationError`.
- `flow8/ledger.py` imports `NEVER_LEDGERED` from `flow8.safety` (`gain`, `phantom`, `phantom_power`).
- Stage 1 script copies in `tools/` expose only the passive `d01` mode; the DSP-sending modes of the original were not carried over.
- `tools/test_inventory.py` and `tools/run_tests_no_hw.py` were added as planned.
