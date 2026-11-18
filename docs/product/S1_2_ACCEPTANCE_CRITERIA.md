# S1.2 Acceptance Criteria

Date: 2026-11-18. These are the criteria the implementation must meet before S1.2 is reported done. Nothing has been implemented yet. Plan: `S1_2_IMPLEMENTATION_PLAN.md`; tests: `S1_2_SAFETY_TEST_SPEC.md`; migration: `S1_2_REGRESSION_MIGRATION_PLAN.md`; files: `S1_2_FILE_CHANGE_MAP.md`.

Objective restated: the safety policy is **enforced on every application call path**; disabling a UI control is not sufficient.

Evidence rule: a criterion is met only when the named test passes in a run whose output is recorded (command, counts by category). A criterion that needs hardware is reported BLOCKED or NOT RUN, never passed.

## 1. Decision criteria

| ID | Requirement | Pass condition | Tests |
|---|---|---|---|
| AC-D1a | +48 V ON requires explicit authorization from direct user confirmation | At the boundary, engine, service and `send_cc`, ON without a valid grant is refused with zero driver calls; ON through the real gate (token issued, user confirmation path) sends exactly one CC 12 value 127 on the confirmed channel; the grant is single use, channel bound, thread bound, and does not leak after an exception | P-01, P-02, P-03, P-05, P-06 |
| AC-D1b | +48 V OFF allowed without a token | OFF sends exactly one CC 12 value 0 with no token ever issued | P-04 |
| AC-D1c | Presets, undo, redo, scenes and automation never enable phantom | No CC 12 value > 0 is emitted by any of them in any test; no module other than the gate, the dialog and the Inspector references the token or grant machinery | P-07, P-08, P-09, P-10 |
| AC-D2a | Gain is blocked at Service and Command Boundary (and engine, ledger, `send_cc`) | Every gain attempt (ch 1–7, raw and dB) is refused at each layer with zero driver calls and a REJECTED log entry where the boundary is reached | B-01, B-02, B-03, M-02 |
| AC-D2b | Undo/redo cannot replay gain | A forged or injected gain record neither records nor replays; no CC 8 is ever emitted by `undo()`/`redo()` | B-04, B-05, B-06 |
| AC-D2c | No runtime, environment or hidden development override for gain | Scans find no environment, argv, debug-flag or unlock/bypass identifiers in production code; the block table cannot be mutated | B-07 |
| AC-D3 | Shared safety module, compatibility re-export, nothing broken | `flow8/safety.py` imports no `tkinter` and no `flow8.ui`; `flow8.ui.safety_dialogs` names are the same objects; existing gate tests pass unmodified | P-11, P-12 |
| AC-D4a | Harness isolated under `tools/`; app code cannot reach it | `flow8/` and `main.py` never import `tools`; no Python file imported the old harness (checked); documents referencing it carry errata | E-07 |
| AC-D4b | No arbitrary MIDI by default; reset never allowed | Harness with a mocked driver sends nothing by default; refuses Program Change (including 16 on channel 16), Note, SysEx, system messages, gain, phantom ON and unlisted CC before any driver call | E-01, E-02, M-06 |
| AC-D4c | Never overwrite historical logs; unique output | Writers use exclusive create with UTC timestamp and process id; an attempt on an existing file raises; SHA-256 of all evidence files unchanged after the whole suite | E-03, E-04, E-05, E-06, E-09 |
| AC-D5 | EQ labels are Band 1–4 | Titles are exactly BAND 1–4; no frequency text in the EQ tab; correction note recorded; screenshots from the running app | L-01, L-02, L-03 |
| AC-G04 | The 37 pairs stay blocked | All 37 refused by `send_cc` and `validate_outbound`; the boundary allowlist still has the same 97 ids; accepted set equals allowlist minus gain (and minus phantom ON without permit); the per-pair audit table exists with purpose, evidence, safety level and decision | M-02, M-03, plan §5 |
| AC-G07 | Every evidence writer is audited and safe | Audit table in the plan covers all writers found; tests prove unique output and no overwrite for each repository tool | E-03…E-09 |

## 2. Owner safety acceptance list

| # | Owner statement | Pass condition | Tests |
|---|---|---|---|
| 1 | Gain is blocked at the Service and Command Boundary | AC-D2a | B-01, B-02 |
| 2 | Undo/Redo cannot replay Gain | AC-D2b | B-04, B-05 |
| 3 | Phantom ON requires valid authorization | AC-D1a | P-01…P-06 |
| 4 | Phantom OFF works without authorization | AC-D1b | P-04 |
| 5 | Preset and Automation cannot enable Phantom | AC-D1c | P-07…P-10 |
| 6 | Program Change, SysEx and Note cannot pass through the application MIDI API | Validator refuses all non-control-change messages; no public API accepts a status byte; only `midi_out.py` touches the driver | M-01, M-04, M-05 |
| 7 | Reset cannot be constructed or sent | Validator, `send_cc`, harness and source scans find no way to produce Program Change 16 on channel 16 | M-06, E-01 |
| 8 | All 37 unauthorised pairs are rejected | AC-G04 | M-02, M-03 |
| 9 | The standalone harness cannot overwrite historical evidence | AC-D4c | E-03, E-06 |
| 10 | No test opens a physical MIDI port | `tools/run_tests_no_hw.py` reports 0 attempted opens for the whole suite; hardware opt-in tests stay skipped; the runner refuses to start when the opt-in variables are set | H-01, H-02 |
| 11 | No existing feature or test is silently deleted | Test inventory before is a subset of after; no skip or expectedFailure added; migrated tests keep names and do not lose assertions | N-01, N-02 |

## 3. Non-regression criteria

| ID | Requirement | Pass condition |
|---|---|---|
| AC-R1 | Complete suite | Baseline 366 run (358 passed, 5 skipped, 3 expected failures) is preserved: every baseline test passes, skips or fails-as-expected exactly as before after migration; new tests all pass; categories reported separately |
| AC-R2 | Existing safe parameters still work | M-07: every allowlisted non-blocked parameter dispatches the same bytes as before |
| AC-R3 | Stage 1 behaviour intact | `tests/test_stage1_state_sync.py` and the defect tests pass |
| AC-R4 | App starts | Offline app construction and the Inspector open for ch 1–7 without error |
| AC-R5 | Packaging unaffected | `main.py` imports; `tools/` not referenced by the spec |
| AC-R6 | Allowlist unchanged | The 97 ids and their (channel, CC) are identical to the frozen list |
| AC-R7 | Public interfaces | `set_phantom(channel, enabled)` signature unchanged; gate classes importable from the old path |

## 4. Documentation criteria

1. `FLOW8_SAFETY_POLICY.md`, `FLOW8_CAPABILITY_MATRIX.md`, `FLOW8_UNRESOLVED_CONFLICTS.md` and `S1_ACCEPTANCE_REPORT.md` enforcement tables updated to the verified state (with run outputs), keeping the earlier text visible as history where changed.
2. Errata blocks on documents that reference the moved harness; a correction note for the EQ labels (historical documents keep their original text).
3. A final S1.2 report with: files changed, tests added, migrated tests with before/after assertion counts, full suite categories, hardware tests NOT RUN, evidence hash comparison, remaining limitations, and the git diff summary. No commit is made unless the owner asks.

## 5. Definition of done

All AC-D*, AC-G*, AC-R* criteria and the eleven owner statements pass with recorded output; the red set from the migration plan is empty; evidence hashes are unchanged; no hardware port was opened; the rollback copies and manifest exist. Anything not proven is listed as BLOCKED or NOT VERIFIED.

## 6. Stop conditions (pause and report, do not push on)

- Any test outside the expected red set fails.
- Any evidence file hash changes.
- Any attempt to open a physical port is detected.
- A migration would require weakening an assertion.
- A design question not covered by the owner decisions appears (for example, how to treat the option O1 in the file map).

## 7. Open decisions

| ID | Question | Default if unanswered |
|---|---|---|
| O1 | Tokens minted only by the dialog (closes "a script mints its own token") | Not included; residual risk documented |
| O2 | Remove the original root-level harness and logger after the `tools/` copies pass | Keep originals until you approve removal |
| O3 | Remove or keep the old Stage 1 scripts under `docs/audit/stage1_screenshots/` after the `tools/` copies pass | Keep (they document how the Stage 1 evidence was made) |
