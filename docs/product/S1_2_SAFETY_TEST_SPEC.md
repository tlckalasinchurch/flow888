# S1.2 Safety Test Specification

Date: 2026-11-18. Preparation only: **no test was written or run, no source changed, no MIDI sent.** Design: `S1_2_IMPLEMENTATION_PLAN.md`. File locations: `S1_2_FILE_CHANGE_MAP.md`. Existing tests that must change: `S1_2_REGRESSION_MIGRATION_PLAN.md`.

"Before" = expected on today's code. FAIL entries for gain and phantom are backed by the offline experiments E-A and E-B in `S1_1_SAFETY_HARDENING_PLAN.md` §1 (accepted at every layer, undo replayed gain). Other entries are reasoned from code reads and are labelled ASSUMPTION until the test exists. "After" = required result once the implementation is complete.

## 1. Ground rules for every test

1. **No physical port.** Safety test modules import `tests/_no_hardware.py`, which patches `Flow8MidiOut.open`, `Flow8MidiIn.open` and the `winmm.midiOutOpen` / `midiInOpen` lookups to raise `AssertionError("physical port open attempted")`. Services are `Flow8Service(auto_connect=False)`. A fake "open" port for byte-level checks is built by setting the object's internals to a `MagicMock` driver (no real handle exists).
2. **Count the driver call.** A refusal is proven by `midiOutShortMsg` mock call count 0 (and `send_cc` call count 0 where the layer is above it), plus an exception or REJECTED log entry. A returned value or message text alone proves nothing.
3. **Real gate only.** No test unlocks phantom through a flag. Authorised ON goes through `PhantomPowerSafetyGate.issue_token` and `confirm_and_dispatch` (helper `authorize_phantom_on`).
4. **No gain unlock exists**, so no test can enable gain. Tests that need a gain baseline write it to the state store (`state_store.set_commanded_value`), which sends nothing.
5. **Names preserved.** Migrated tests keep their names (see migration plan); new tests use the `test_s12_*` modules.
6. **Reports** list passed, failed, skipped, expected failures and hardware tests separately.

## 2. Gain (decision D2)

| ID | Test | Steps | Expected after | Before |
|---|---|---|---|---|
| B-01 | Boundary refuses gain | For ch 1–4 and ch 5–7: `execute_command("chN.gain", v, unit)` with raw 0, 64, 127 and dB −20, 0, 60 | Raises `Flow8CommandRejectedError`; log entry `dispatch_status == REJECTED`, `command_accepted False`, `raw_midi_sent None`; `send_cc` count 0; state store unchanged | **FAIL** (E-A) |
| B-02 | Service refuses gain | `service.set_gain(ch, v, unit)` for ch 1–4 | Raises before any state is read or written; no ledger record; count 0 | **FAIL** (E-A) |
| B-03 | Engine refuses gain | `engine.channel(n).set_gain(...)` | Raises; count 0 | **FAIL** (E-A) |
| B-04 | Undo cannot replay gain | (a) `ledger.push(make_record("gain", 1, 10, 20))`; (b) white-box: `ledger._undo.append(record)` then `service.undo()` and `redo()` | (a) `push` returns False. (b) the replay raises with count 0 and no CC 8 is ever emitted; other records unaffected | **FAIL** (E-A: `ch1.gain` replayed) |
| B-05 | Mixed batch | Inject a group (fader step + gain step with the same transaction id), call `undo()` | No CC 8 emitted; if the fader half was applied before the refusal, the existing compensation restores it; final fader equals the pre-undo value | ASSUMPTION: fails (gain would replay) |
| B-06 | Ledger never records gain | `CommandLedger.push(make_record("gain", ...))` | Returns False; `can_undo` False | **FAIL** (ledger accepts gain today) |
| B-07 | No override exists | AST/regex scan of `flow8/` production files for `environ`, `getenv`, `sys.argv`, `FLOW8_`, `os.environ`; names containing `unlock`, `bypass`, `override`, `allow_gain`, `enable_gain`; attempt to mutate `BLOCKED_PARAMETER_TYPES` | No match; mutation raises `TypeError`; `AnalogGainSafetyGate.is_verified_mapping_available()` is False | Partly passes (no env use today); mutation test not yet testable |
| B-08 | UI cannot send gain | Open the Inspector on ch 1–4, move the preview slider, press Apply (disabled), press Cancel | `service.set_gain` call count 0; driver count 0; Apply stays disabled | Guard (passes today) |

## 3. Phantom (decision D1)

| ID | Test | Steps | Expected after | Before |
|---|---|---|---|---|
| P-01 | ON needs authorization at every layer | `execute_command("ch1.phantom", True)`; `engine.channel(1).set_phantom(True)`; `service.set_phantom(1, True)`; `send_cc(1, 12, 127)`; same for ch 2 | Each raises; REJECTED logged where the boundary is reached; driver count 0; state unchanged | **FAIL** (E-B) |
| P-02 | Authorised ON works exactly once | `authorize_phantom_on(service, 1)` with a fake-open port | One message: status `0xB0`, CC 12, value 127; the state store shows commanded True; then `service.set_phantom(1, True)` without a token is rejected | ASSUMPTION: first part passes today; second part fails |
| P-03 | Token abuse | Forged token, consumed token, token for the other channel, expired token, revoked token, `None`, wrong type | Each refused; driver count 0; each valid token succeeds exactly once | Gate-level passes today (`test_safety_dialogs.py`); boundary-level **FAIL** |
| P-04 | OFF needs no authorization | With no token ever issued: `service.set_phantom(1, False)`, `engine.channel(2).set_phantom(False)`, `execute_command("ch1.phantom", False)` | Exactly one message each: CC 12, value 0, correct channel; state commanded False | Passes today (intended behaviour kept) |
| P-05 | Grant is one-shot and leak-free | After `confirm_and_dispatch`, including when the service raises | No grant remains active (a following unauthorised ON is rejected) | not yet testable |
| P-06 | Grant is thread-bound | Obtain a grant in thread A; call `set_phantom(1, True)` from thread B | Thread B is rejected | not yet testable |
| P-07 | Presets cannot enable phantom | `apply_channel_preset` for every preset on channels 1–7 with a recording fake-open port, phantom initially OFF and initially ON | No CC 12 emitted; phantom state unchanged | Guard (passes by construction) |
| P-08 | Undo and redo cannot enable phantom | Authorised ON, then several fader and pan changes, then undo/redo repeatedly; also `ledger.push(make_record("phantom_power", ...))` | Only the initial CC 12 exists; push returns False | Guard (passes today: existing tests) |
| P-09 | Scenes cannot enable phantom | Capture and recall scenes with phantom ON and OFF | No CC 12 on recall; stored scene contains no phantom key | Guard (passes today) |
| P-10 | "Automation" has no route | AST scan: `issue_token`, `confirm_and_dispatch`, the grant and permit helpers are referenced only from `flow8/safety.py`, `flow8/ui/safety_dialogs.py`, `flow8/ui/components/channel_detail.py`; `presets.py`, `scenes.py`, `ledger.py`, `service.py`, `parameter_engine.py`, `command_boundary.py` (except consuming the grant) contain no call that passes `True` to `set_phantom` | Scan passes | not yet testable |
| P-11 | Compatibility re-export | `flow8.ui.safety_dialogs.PhantomPowerSafetyGate is flow8.safety.PhantomPowerSafetyGate`; same for the token; `flow8.safety` imports no `tkinter` | Identity holds; no tkinter | not yet testable |
| P-12 | Existing gate tests unchanged | Run `tests/test_safety_dialogs.py` and the phantom tests of `tests/test_channel_detail.py` unmodified | All pass | Pass today |

## 4. Message types, reset and the 37 pairs (G-03, G-04)

| ID | Test | Steps | Expected after | Before |
|---|---|---|---|---|
| M-01 | Exhaustive validator | `validate_outbound` for every status 0x80–0xFF × data1 0–127 × data2 in {0, 1, 15, 16, 17, 64, 127} (about 114,000 cases) | Accepts only `0xB0–0xBF` messages whose (channel, CC) is in the allowed pairs and not gain; phantom ON only with the permit; every other case refused with a rule id | not yet testable |
| M-02 | `send_cc` accepted set | All 16 × 128 (channel, CC) with value 0 and with value 127 on an unopened port | Value 0: exactly the allowlisted pairs minus the 4 gain pairs (93). Value 127: those minus the 2 phantom pairs (91). Nothing else | **FAIL** (accepts 134; E-C and dry-run) |
| M-03 | The 37 pairs | Explicit list in the test file: (1..7, 6); (8, 9, 10) × {8, 11, 12, 13, 14, 15, 16, 17, 18, 19}. For each: `send_cc` refuses, `validate_outbound` refuses with the rule id, fabricated ids (`chN.solo`, `main.limiter`, `main.geq_1` …) are refused by the boundary as not allowlisted | 37 of 37 refused; a second check recomputes the difference from the frozen chart table and asserts it equals the explicit list | **FAIL** (all 37 accepted by `send_cc`) |
| M-04 | Only control change leaves the app | Fake-open port with a `MagicMock` driver; send every accepted message; record the DWORD | Every low byte is `0xB0–0xBF`; data bytes < 128; no other status ever | Passes today (CC-only by construction) |
| M-05 | No Program Change, Note or SysEx API | Introspect public callables of `Flow8MidiOut`, `Flow8CommandBoundary`, `Flow8ParameterEngine`, `Flow8Service`: no parameter named `status`; scan `flow8/` for `midiOutShortMsg` and `midiOutLongMsg` (only `flow8/midi_out.py`); scan for status literals `0x80–0xFF` outside `safety.py` constants | Pass | Guard passes in `flow8/` today |
| M-06 | Reset cannot be built or sent | `validate_outbound(0xCF, 16, 0)`, `(0xCF, 15, 0)`, `(0xBF, c, v)` for all `c`, `v`; `send_cc(16, c, v)`; harness (E-01) | All refused; driver count 0; the constant for the forbidden message exists once in `safety.py` | Guard (no sender); validator part not yet testable |
| M-07 | Positive regression | Offline boundary with a fake-open port: every allowlisted non-blocked parameter, min, middle, max | Exactly one message per call with the expected bytes; gain refused; phantom ON refused without a grant; no change to existing behaviour (compare with the baseline dispatch table) | Passes today except gain and phantom |

## 5. Evidence protection and the harness (D4, G-07)

| ID | Test | Steps | Expected after | Before |
|---|---|---|---|---|
| E-01 | Harness refuses forbidden messages | Import `tools.flow8_midi_harness` with its driver (`ctypes.windll.winmm`) replaced by a mock; call `send_short_msg` with Program Change 16 on channel 16, Program Change on any channel, Note On/Off, SysEx start, system real-time, gain, phantom ON, an unlisted CC | Each raises before the driver call; mock count 0 | **FAIL** on the root script (sends any bytes) |
| E-02 | No arbitrary MIDI by default | Run the script's main with default arguments and mocked driver | Sends nothing, says how to allow a listed write | **FAIL** (root script sends its test list) |
| E-03 | Cannot overwrite | Output path equal to a copy of an existing evidence file in a temporary directory | Raises `FileExistsError`; the copy's SHA-256 unchanged | **FAIL** (opens with mode `w`) |
| E-04 | Unique outputs | Two runs in one second, same output directory | Two different files (UTC timestamp and process id; exclusive create) | **FAIL** |
| E-05 | Logger same rules | Same as E-03/E-04 against `tools/flow8_midi_in_logger.py` with `Flow8MidiIn` mocked | pass | **FAIL** |
| E-06 | Hash invariance | Before the run: SHA-256 manifest of `FLOW8_PHASE1_RAW_MIDI_LOG.md`, `FLOW8_PHASE2B_RAW_MIDI_LOG.md`, `docs/audit/hw_stage1/*`, `docs/product/sources/*.pdf`, `docs/audit/stage1_screenshots/*.png`; after the full suite and all tool tests: compare | Identical | Passes today (nothing runs them) |
| E-07 | Isolation | AST scan: `flow8/` and `main.py` never import `tools` | Pass | Guard |
| E-08 | Import safety | Importing each `tools/*.py` opens nothing and writes nothing | Pass | not yet testable |
| E-09 | Stage 1 scripts | `tools/hw_verify_stage1.py` and `tools/capture_stage1.py` produce run-id suffixed files and refuse to write existing ones | Pass | **FAIL** on the originals |

## 6. No physical port, whole suite (acceptance requirement)

| ID | Test | Expected |
|---|---|---|
| H-01 | `python tools/run_tests_no_hw.py` runs the full discovery with `Flow8MidiOut.open`, `Flow8MidiIn.open` and the `winmm` open functions patched to fail loudly, counts attempts, and refuses to start when `FLOW8_HW_TESTS` or `FLOW8_HW_TESTS_MUTATE` is set | Attempted opens = 0; the 5 hardware tests stay skipped; exit status reports categories |
| H-02 | Each `test_s12_*` module asserts in `setUp` that `service.midi_out.is_connected` and `service.midi_in.is_connected` are False | pass |

## 7. UI labels (decision D5)

| ID | Test | Expected after | Before |
|---|---|---|---|
| L-01 | `ChannelDetailPanel.EQ_BANDS` titles | Exactly "BAND 1", "BAND 2", "BAND 3", "BAND 4" for keys low, low_mid, hi_mid, hi; no digit followed by Hz/kHz in any title | **FAIL** (80 Hz, 400 Hz, 2.5 kHz, 10 kHz) |
| L-02 | Rendered EQ tab text | No frequency figure; a note states band frequencies are unconfirmed | **FAIL** |
| L-03 | Screenshots of the running app (offline service) at 1600×900 and 1366×768 | Labels visible; saved to unique files | n/a |

## 8. No silent deletion (acceptance requirement)

| ID | Test | Expected |
|---|---|---|
| N-01 | `tools/test_inventory.py` writes the sorted list of all test ids to `docs/product/test_inventory_before.txt` (baseline, step 0) and again after implementation | Every baseline id still exists afterwards; new ids may be added; counts reconcile (`before + new = after`); the report lists additions and migrations |
| N-02 | No `skip` or `expectedFailure` is added to an existing test | Scan of the diff of `tests/` shows none |

## 9. Mapping to the owner's acceptance statements

| Owner requirement | Tests |
|---|---|
| Gain blocked at Service and Command Boundary | B-01, B-02, B-03 |
| Undo/Redo cannot replay Gain | B-04, B-05, B-06 |
| Phantom ON requires valid authorization | P-01, P-02, P-03, P-05, P-06 |
| Phantom OFF works without authorization | P-04 |
| Preset and Automation cannot enable Phantom | P-07, P-08, P-09, P-10 |
| Program Change, SysEx, Note cannot pass through the app MIDI API | M-01, M-04, M-05 |
| Reset cannot be constructed or sent | M-06, E-01 |
| All 37 unauthorised pairs rejected | M-02, M-03 |
| Harness cannot overwrite historical evidence | E-03, E-04, E-05, E-06 |
| No test opens a physical MIDI port | H-01, H-02 |
| No existing feature or test silently deleted | N-01, N-02, P-12, M-07 |
| No runtime, environment or hidden gain bypass | B-07 |
| EQ labels | L-01, L-02, L-03 |

## 10. Expected suite numbers (estimate, ASSUMPTION)

Baseline at the last run: 366 run, 358 passed, 5 skipped, 3 expected failures. The S1.2 work adds roughly 40 new test cases (the exhaustive cases count as one test each). No baseline test is removed. The hardware tests (5) stay skipped and are reported as NOT RUN.

## Appendix: evidence baseline (SHA-256, computed 2026-11-18 before any S1.2 work)

Test E-06 compares these values after the suite and the tool tests. Files under `docs/audit/stage1_screenshots/*.png` and `docs/audit/hw_stage1/*` are included.

```text
321cfcce34de959f91012af4d9eaeda7fd6b67d8ab0b6aa1988a1466536f63da  FLOW8_PHASE1_RAW_MIDI_LOG.md
814d1eabe38f3eb7cfc59a08892a03118ad9081492421a0e3fd1e83b5d4cca6b  FLOW8_PHASE2B_RAW_MIDI_LOG.md
f6371231348665bd767e75d4ca71746e3098b90317b2eb65c4c6f101e76ddaaf  docs/audit/hw_stage1/d01_after.png
1c27fff0e683f4a1c8bccad52cfd4d26f310f732ef3db36cb63a9bb8c264bd51  docs/audit/hw_stage1/d01_before.png
7e9f74f41e31eb2053ff8ef600acee38a58e675a2e37bb438784c9a9c328ead7  docs/audit/hw_stage1/d01_events.jsonl
4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945  docs/audit/hw_stage1/d01_isolated_logger_events.json
d3339373669367237e9792b34a905a394d7c3b871a034deb64d6cde694555cb9  docs/audit/hw_stage1/d01_isolated_logger_report.md
cfe98d5cfd298d77c7a919bb7ef87c8207ec4a9cc6a8227db2e1a79a298f5d29  docs/product/sources/behringer_flow8_quick_start_guide_V1.0_thomann-copy_505388.pdf
f4469ea36e27c85ac52ada932a7f1092ea084326072f64ef85ba424ea36e3c7f  docs/product/sources/manuals-plus_mirror_flow8_user_guide_BEFLOW8K2.pdf
0c6f3c3c3915da1adc6b0684a378a680b69a9e27abb7f5605b8e0ceaa9026a04  docs/audit/stage1_screenshots/1280x720_1_main.png
6b6b7ea9f352ecf869b1545682bd269e941760ed1525890126674973c1ef1d51  docs/audit/stage1_screenshots/1280x720_2_inspector.png
b223053537bfd846c0d632341d2757ca77ad8b7aa3ec7214542da457f5a2e89a  docs/audit/stage1_screenshots/1280x720_3_preset.png
bb84802645a6f48b98d7e11d1874f9dccf4bbdbb8b2339cda39e1081ff8d19ad  docs/audit/stage1_screenshots/1280x720_4_undo.png
79d6d228670a88a1c8dc0a79bb6808ae0a11fbd1d28d18f6c7f4b8112762cebe  docs/audit/stage1_screenshots/1280x720_5_redo.png
41d9883651a94bf004437c5a4b51a6a5399b7222d15f5749e4dedff03a87974a  docs/audit/stage1_screenshots/1280x720_6_reconnect_unsynced.png
d92768dc42b495d4ef733c1d1268f16b000940fd11fd25fb8d5aad1fb8949f69  docs/audit/stage1_screenshots/1366x768_1_main.png
fb3f89fef71b06e6c46537ae49c20e2094553bef48b576b5710727623d0b6dd2  docs/audit/stage1_screenshots/1366x768_2_inspector.png
7e818a847cac4a6d7de69376848baa1626362ffe282c8581c1766573678240ea  docs/audit/stage1_screenshots/1366x768_3_preset.png
fc10e8391960896d8ded7581d01ead74f11066fff63c847c70276897e9e3765e  docs/audit/stage1_screenshots/1366x768_4_undo.png
ef9099df0106a544283247d76a43dc713b9dc9bd75c4daae8f80b8325d72dbc4  docs/audit/stage1_screenshots/1366x768_5_redo.png
35abbdd6a8d2fee0f72b5d087565ea68c8ce34fb27cf5ab2743ec7902ae51f1a  docs/audit/stage1_screenshots/1366x768_6_reconnect_unsynced.png
5d93b5e3ba44ba41e3c85f11bf2d4bc267487944d506837a017c1bf3e5dfcbbe  docs/audit/stage1_screenshots/1600x900_1_main.png
b6dac83c1d9ac855b9715f04e98e83874d4ed1dbf4ab85b71e3498b4e9212181  docs/audit/stage1_screenshots/1600x900_2_inspector.png
a0e1f19cd5421d14b7a35a273874bd034e65cd757e2dbc1c9b9ebbd59c01d82c  docs/audit/stage1_screenshots/1600x900_3_preset.png
db3ef452f4020b94b4366096d707e8062e5a14b47f257138a1a0cd6e12bc1b4f  docs/audit/stage1_screenshots/1600x900_4_undo.png
edadbd4ec01dd9fd5654bff48895acc810946d2f7b99b89bb2f0e8b65c9749a9  docs/audit/stage1_screenshots/1600x900_5_redo.png
1d9798960c011032ecbaa6b8a18ee1f93295a9cad225d7995f5fcace148deb74  docs/audit/stage1_screenshots/1600x900_6_reconnect_unsynced.png
```
