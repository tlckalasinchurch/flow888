# S1.2 Implementation Report

Date: 2026-11-18. Steps 0–8 of `S1_2_IMPLEMENTATION_PLAN.md` were implemented as approved (option O1, dialog-minted tokens, **not** included). Nothing was committed. No MIDI was sent, no port opened, no mixer state changed. S2 was not started.

Labels: **VERIFIED** = command output from this session. **NOT RUN** = not executed.

## 1. Results (VERIFIED)

Command: `python -m tools.run_tests_no_hw` (full discovery with the real `midiOutOpen`/`midiInOpen` replaced by counters that raise; it refuses to start if the hardware opt-in variables are set).

| Category | Count |
|---|---|
| Ran | 405 (baseline 366 + 39 new) |
| **Passed** | **397** |
| **Failed / errors** | **0 / 0** |
| **Skipped** | 5 (the opt-in hardware tests) |
| **Expected failures** | 3 (open defects D-03, D-04, D-06; not counted as passed) |
| Unexpected successes | 0 |
| **Hardware tests** | **NOT RUN** |
| **Attempted physical port opens** | **0** |

`python -m tools.test_inventory`: baseline 366, now 405, **missing 0**, added 39. A scan of the `tests/` diff found no added `skip`/`expectedFailure` line and no removed `def test_` line. Assertion counts of the 17 migrated tests: 70 before, 85 after (none fewer). Evidence hashes: test E-06 compares 31 files (historical logs, Stage 1 hardware captures, source PDFs, screenshots, the original harness and logger, the Stage 1 scripts) with `docs/product/evidence_baseline.sha256`: all identical.

## 2. What changed

New files: `flow8/safety.py`; `tools/` (`_output.py`, `flow8_midi_harness.py`, `flow8_midi_in_logger.py`, `capture_stage1.py`, `hw_verify_stage1.py`, `run_tests_no_hw.py`, `test_inventory.py`, `README.md`, `__init__.py`); tests `tests/_no_hardware.py`, `_safety_helpers.py`, `test_s12_safety_boundary.py`, `test_s12_safety_messages.py`, `test_s12_tools_evidence.py`, `test_s12_labels.py`; support files `docs/product/test_inventory_before.txt`, `evidence_baseline.sha256`, `rollback_s1_2/<timestamp>/` (19 original files with `MANIFEST.sha256`).

Modified: `flow8/command_boundary.py` (policy check and one-shot permit), `flow8/midi_out.py` (`send_cc` uses `validate_outbound`; the hard-coded allow-set is gone), `flow8/service.py` (`set_gain` fails first), `flow8/ledger.py` (gain never recorded), `flow8/ui/safety_dialogs.py` (re-export; gain gate reads policy), `flow8/ui/components/channel_detail.py` (BAND 1–4 labels and note). Not modified: `parameter_engine.py`, `scenes.py`, `presets.py`, the allowlist (still 97 entries), the original root harness and logger, `main.py`, the PyInstaller spec.

## 3. Decisions and acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| D1 phantom ON needs authorization | **Met.** Refused at boundary, engine, service and `send_cc` without a grant; one confirmed ON sends exactly one CC 12 value 127; the grant is single use, channel bound and thread bound; no leak after an exception | P-01, P-02, P-03, P-05, P-06 |
| D1 OFF without a token | **Met** | P-04 |
| D1 presets, undo/redo, scenes, automation never enable phantom | **Met** (behavioural tests plus a source scan restricting the token machinery to `safety.py`, the dialog module and the Inspector) | P-07…P-10 |
| D2 gain absolute block, no override | **Met.** Refused at boundary, service, engine, ledger, `send_cc` and harness; no environment, argv or unlock identifiers in production code; the block table is read-only | B-01…B-08 |
| Undo/redo cannot replay gain | **Met** (gain is never recorded; an injected record is refused with zero CC 8) | B-04, B-05, B-06 |
| D3 shared module with re-export | **Met.** `flow8.safety` imports no tkinter or `flow8.ui`; old import path gives the same objects; existing gate tests pass unmodified | P-11, P-12, `test_safety_dialogs` |
| D4 harness isolated, no arbitrary MIDI, unique output | **Met for the `tools/` copies**; originals kept unchanged (open decision O2) | E-01…E-09 |
| D5 EQ labels | **Met.** Bands are labelled BAND 1–4 with "Band frequencies and Q are unconfirmed" | L-01, L-02; screenshots in `tools/output/stage1/` (1600×900, 1366×768; the 1280×720 request is clamped to the same window as 1366×768) |
| G-04 the 37 pairs | **Met.** All refused by `send_cc` and `validate_outbound`; accepted set = allowlist minus gain (93 for value 0, 91 for value 127); the boundary was not expanded | M-02, M-03 |
| G-07 evidence writers | **Met for repository tools**; the two Mixing Station scripts are out of scope | E-03…E-09 |
| Program Change, SysEx, Note cannot pass | **Met** (exhaustive validator over about 115,000 messages) | M-01, M-04, M-05 |
| Reset cannot be constructed or sent | **Met** (rule SR-02) | M-06, E-01 |
| No test opens a physical port | **Met** (0 attempts across the whole suite) | H-01 |
| No test silently deleted | **Met** | inventory, diff scan |

## 4. Deviations and discoveries

- Two more tests than planned needed migration (17, not 15): a structural test that expected the phantom setter in `ui/safety_dialogs.py`, and the "every allowlist entry enforces min and max" test. Both kept their names and gained assertions (`S1_2_REGRESSION_MIGRATION_PLAN.md` addendum).
- The grant is ambient (a context variable around the single synchronous call) so `set_phantom(channel, enabled)` keeps its signature.
- +48V ON detection is strict (`True` or `1`) so invalid values keep raising `Flow8ValidationError`.
- `flow8/safety.py` builds its tables lazily from the allowlist to avoid an import cycle.

## 5. Remaining limitations (honest list)

1. **No hardware verification** of any parameter; D-01, D-02, D-05 remain BLOCKED or NOT TESTED on hardware; inbound telemetry still UNCONFIRMED.
2. Python has no private members: an in-process caller can still reach `flow8.safety` internals or the driver handle `_winmm`. The structural tests limit where they may be referenced; they cannot prevent a deliberate bypass.
3. A script can still mint its own phantom token with `issue_token` (O1 declined); "direct user confirmation" is enforced by the dialog flow, not cryptographically.
4. The original root-level `flow8_midi_harness.py` and `flow8_midi_in_logger.py` and the Stage 1 scripts under `docs/audit/stage1_screenshots/` remain unchanged and unrestricted. Open decisions: **O2** remove the root originals once you are satisfied; **O3** the same for the Stage 1 scripts.
5. Derived readouts (fader dB, gain preview) still come from unconfirmed curves (C-05, C-12). Presets are still labelled "CueAir" in the UI button; that is outside S1.2.
6. The three expected failures (D-03, D-04, D-06) and the Tcl teardown warnings (D-14) are unchanged.

## 6. Rollback

Copies of every modified file taken before the first edit are in `docs/product/rollback_s1_2/20261118T121823Z/` with `MANIFEST.sha256`. To roll back: save the current files into a new timestamped folder, copy the originals back, verify hashes against the manifest and rerun `python -m tools.run_tests_no_hw`. No Git reset or deletion is needed. The new `test_s12_*` modules would then show the unresolved gaps as failures.

## 7. Git summary (nothing committed)

`git diff --stat -- flow8 tests`: 16 modified files, 308 insertions, 214 deletions (includes the earlier uncommitted Stage 1 work). New untracked: `flow8/safety.py`, `tools/`, six test modules and helpers, `docs/product/`, `docs/audit/`.

## 8. Stop

Implementation of S1.2 is complete and reported. S2 is not started. Awaiting your decisions on O2 and O3 and your approval before any further stage.
