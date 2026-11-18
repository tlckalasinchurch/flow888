# S1.1 Regression Test Plan

Date: 2026-11-18. Stage S1.1, planning only. **No test file was written, no source changed, no MIDI sent.** The cases below protect the safety rules in `FLOW8_SAFETY_POLICY.md` and the fixes in `S1_1_SAFETY_HARDENING_PLAN.md`.

## 1. Principles

1. **Red first.** Each guard test is written before the fix and must fail on today's code for the stated reason (or be marked as a guard that already passes).
2. **No hardware.** Every test uses an offline `Flow8Service(auto_connect=False)` or a mocked port. A counter on `midi_out.send_cc` (and on the driver call in the harness) must stay at zero for refused commands. Tests never open a real port and never set `FLOW8_HW_TESTS*`.
3. **Count the driver call, not the return value.** A refusal is proven by "the driver function was never called", not by an exception message alone.
4. **Layer coverage.** The same forbidden command is tried at every layer: UI, service, engine, boundary, ledger replay, low-level port, harness.
5. **Migration, not deletion.** Tests that today rely on gain or phantom dispatch are migrated (`S1_1_SAFETY_HARDENING_PLAN.md` §5).
6. **Categories reported separately** at each run: passed, failed, skipped, expected failure, hardware tests.

## 2. Test cases

"Today" is the expected result on the current code. FAIL entries are backed by offline experiments E-A and E-B (hardening plan §1); the others are reasoned from the code reads cited in the plan and are labelled ASSUMPTION until the test exists and runs.

### A. Gain (gap G-01)

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-01 | Boundary | `execute_command("ch1.gain", v)` for ch 1–4, several values and units | Raises `Flow8CommandRejectedError`; log entry `dispatch_status == REJECTED`, `raw_midi_sent is None`; `send_cc` counter 0; state store unchanged | **FAIL** (E-A: accepted) |
| T-02 | Service | `service.set_gain(ch, v)` | Raises; counter 0; no ledger record | **FAIL** (E-A) |
| T-03 | Engine | `engine.channel(n).set_gain(...)` | Raises; counter 0 | **FAIL** (E-A) |
| T-04 | Undo/redo | Seed the ledger with a gain record (`CommandLedger.push(make_record("gain", 1, 10, 20))`) then `service.undo()` and `redo()` | The replay is refused; `send_cc` counter 0; the step stays in the stack or the call raises without sending; no other parameter is sent as a side effect | **FAIL** (E-A: replayed `ch1.gain`) |
| T-04b | Undo/redo | Batch containing a fader step and a gain step | Undo does not send the gain part; the whole batch is refused or rolled back (existing compensation path) | ASSUMPTION: fails today |
| T-20 | UI | Open the Inspector for ch 1–4; drive the gain preview slider, Apply, Cancel | `service.set_gain` and the boundary receive zero calls; `send_cc` counter 0; the Apply button is disabled | Guard (passes today: `test_gain_dispatch_is_gated_when_unverified`, button disabled) |

### B. Phantom (gap G-02)

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-05 | Boundary | `execute_command("ch1.phantom", True)` without authorization | Rejected; counter 0 | **FAIL** (E-B) |
| T-06 | Service | `service.set_phantom(1, True)` without authorization | Raises; counter 0 | **FAIL** (E-B) |
| T-07 | Token | Forged object, token consumed once already, token for the other channel, expired token, revoked token, `None` | All refused at the boundary; counter 0; each token valid exactly once | Partly passes today at the gate level (`test_safety_dialogs.py`); **FAIL** at boundary level |
| T-07b | Direction | OFF path | Behaviour matches owner decision D1 and is tested explicitly | decision pending |
| T-09 | Ledger/scenes | `set_phantom` (authorized) then undo, redo, scene capture, scene recall | Phantom never recorded, never captured, never replayed; counter shows only the explicit calls | Guard (passes today: `test_set_phantom_is_never_recorded`, `test_undo_never_touches_phantom`) |
| T-21 | UI end to end | Dialog → confirm with a mocked port | A valid token produces exactly one CC 12 with value 127 on the right channel; a second confirm produces none | Guard (passes today) |

### C. Boundary and low-level refusal (gaps G-01…G-04)

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-08 | Port | `Flow8MidiOut.send_cc` with CC 8 on ch 1–4 and CC 12 on ch 1–2, no boundary marker | Refused before the driver call | **FAIL** (accepted, E-C dry-run) |
| T-15 | Allow-lists | For all 16 × 128 (channel, CC) pairs on an unopened port | Pairs accepted by `send_cc` equal allowlisted pairs minus blocked pairs (today 37 extra) | **FAIL** (37 extra pairs) |
| T-26 | Boundary | Allowlist structure | Every entry has `message_type == CONTROL_CHANGE`; import fails when a non-CC type is added | not yet testable (field absent) |

### D. Message types and reset (gap G-03)

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-10 | Validator | Exhaustive loop over status 0x80–0xFF with every data1 and data2 in {0, 1, 15, 16, 17, 64, 127} on every channel through `validate_outbound` | Only `0xB0–0xBF` allowlisted messages accepted; Program Change, Note On/Off, SysEx, system messages all refused | not yet testable; `send_cc` alone passes (CC-only by construction) |
| T-11 | Reset | Try to construct a Program Change 16 on channel 16 by every public API (`send_cc`, helpers, boundary, harness) | Impossible or refused; driver counter 0 | Guard (no sender exists) |
| T-12 | Source scan | AST/grep over `flow8/` and root scripts | `midiOutShortMsg`/`midiOutLongMsg` appear only in `flow8/midi_out.py` and the (restricted) harness; no status literal for Program Change, Note or SysEx outside the policy constants | Guard (passes in `flow8/` today; **FAIL** for the harness, which calls `midiOutShortMsg`) |
| T-13 | Channel 16 | `send_cc(16, cc, v)` for all cc | Refused (channel 16 is not a CC channel for this app) | Guard (passes today) |
| T-14 | Numbering | Any future Program Change helper must take raw data bytes and refuse 16 on channel 16 and values above 15 for snapshots | Written when a sender is approved; until then asserts none exists | placeholder |

### E. Harness and logger (gaps G-05, G-07)

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-16 | Harness | `send_short_msg` with Program Change 16 on channel 16, Note On, SysEx start, gain, phantom, unlisted CC (driver function mocked) | Raises before the driver call; counter 0 | **FAIL** (sends arbitrary bytes) |
| T-17 | Harness | Run `__main__` logic with default arguments and a mocked driver | Sends nothing unless the explicit write flag is given | **FAIL** (sends its test list) |
| T-18 | Harness/logger | Run twice in a temporary directory | Two distinct log files; the first is byte-identical afterwards; no repository evidence file is opened for writing | **FAIL** (overwrites) |

### F. Presets, scenes and hardware tests

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-24 | Presets | Apply every channel preset to every allowed channel with a recording port | Only CC 1–4, 9, 11 are emitted; no CC 5, 6, 7, 8, 10, 12, 14–17 | Guard (passes by construction) |
| T-24b | Presets | Preset dataclass | Cannot carry level, balance, gain, phantom or send fields (structural, for S2) | S2 |
| T-25 | Ledger | `CommandLedger.push` of a record with an unknown or forbidden `parameter_type` | `_replay` raises `ValueError`/refuses; nothing sent | Partly passes (unknown types raise); gain **FAIL** (T-04) |
| T-27 | Scenes | `SceneManager.ALLOWED_PARAMETERS` and `REVERSIBLE_PARAMETERS` | Contain no gain, phantom or program-change entries | Guard |
| T-30 | Hardware tests | AST scan of `tests/test_hardware_midi_out.py` and any opt-in test | No gain, phantom or non-CC call; tests remain skipped unless the opt-in variables are set | Guard (today the mutating tier sends pan, EQ low, mute on ch 1 only) |

### G. UI honesty (gap G-06)

| ID | Layer | Test | Assertion | Today |
|---|---|---|---|---|
| T-22 | UI | EQ band labels | No numeric frequency without the qualifier chosen in decision D5 | **FAIL** (labels show 80 Hz, 400 Hz, 2.5 kHz, 10 kHz) |
| T-23 | UI | Fader/gain readouts derived from unconfirmed curves | Carry the approximate marker; raw value shown | Partly (gain preview is labelled "Approx./UNVERIFIED"); fader readout not |
| T-28 | UI | No widget text says "hardware verified", "read from hardware" or "synced" for COMMANDED or UNSYNCED values | Text scan of all label constants | Guard (passes today: "HW APPLIED: UNKNOWN") |

## 3. Bypass matrix (every route to a forbidden command must be covered)

| Route | Gain | Phantom | PC / Note / SysEx | Reset |
|---|---|---|---|---|
| UI | T-20 | T-21 | no widget (T-28) | T-11 |
| Service | T-02 | T-06 | none (T-12) | T-11 |
| Engine | T-03 | T-05 (engine variant) | none | T-11 |
| Boundary | T-01 | T-05 | T-26 | T-11 |
| Ledger replay (undo/redo/scene) | T-04, T-04b | T-09 | T-25 | T-11 |
| Low-level `send_cc` | T-08 | T-08 | T-10 | T-13 |
| Harness | T-16 | T-16 | T-16 | T-16 |
| Presets | T-24 | T-24 | T-24 | T-24 |
| Automated hardware tests | T-30 | T-30 | T-30 | T-30 |

## 4. Test seams needed (design, not implemented)

- A recording fake for `midi_out.send_cc` (a `mock.Mock` suffices); no fake MIDI telemetry is introduced.
- To establish a gain baseline for the preset-preservation tests without sending gain: `state_store.set_commanded_value("ch1.gain", 24, EventSource.LOCAL_HOST, raw_midi_value=…)` in test code only.
- A valid phantom authorization for tests: obtained through the real gate (`issue_token`), not a bypass flag in production code.

## 5. Run protocol

1. Run the complete suite before the change and record passed/failed/skipped/expected-failure counts (baseline at the last run: 366 run, 358 passed, 0 failed, 5 skipped, 3 expected failures).
2. Add the red tests; confirm each fails for the stated reason; record.
3. Implement fix by fix; after each, run the safety subset and then the full suite.
4. Final report lists the categories separately; hardware tests stay NOT RUN; a result that could only be obtained with hardware is reported BLOCKED, not passed.

## 6. Exit criteria for the hardening stage

- Every route in the bypass matrix has at least one passing test.
- No forbidden command increments the driver counter in any test.
- No test is deleted; migrated tests keep their intent.
- The documents state which tests are guards that already passed and which were red first.
