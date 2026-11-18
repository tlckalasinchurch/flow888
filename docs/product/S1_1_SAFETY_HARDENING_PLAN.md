# S1.1 Safety Hardening Plan

Date: 2026-11-18. Stage S1.1, analysis only. **No source code was changed, no MIDI sent, no hardware opened.** Evidence below comes from reading the code and from offline experiments on a `Flow8Service(auto_connect=False)` whose ports were verified closed before and after (`midi_out.is_connected == False`, `midi_in.is_connected == False`), so nothing could be transmitted.

Related: `FLOW8_SAFETY_POLICY.md` (rules SR-01…SR-12), `S1_1_REGRESSION_TEST_PLAN.md` (test cases T-xx named below), `S1_1_CAPABILITY_MAPPING_AUDIT.md`, `FLOW8_UNRESOLVED_CONFLICTS.md`.

## 1. Summary

| Gap | Priority | One-line finding | Verified by |
|---|---|---|---|
| **G-01 Gain** | 1 | Gain is blocked only in the UI. Service, engine, boundary and **undo/redo** all accept and replay it | Offline experiment E-A |
| **G-02 Phantom** | 2 | +48 V is confirmation-gated only in the UI. Service, engine and boundary accept it with no token | Offline experiment E-B |
| **G-03 PC / SysEx / Note** | 3 | The application command API has no such message type, but this holds only by absence of code; nothing declares or tests it, and the raw driver handle is reachable | Code reads, E-C |
| **G-04 Allow-list mismatch** | 4 | `send_cc` accepts 37 (channel, CC) pairs the boundary does not allow | Dry-run, `S1_1_CAPABILITY_MAPPING_AUDIT.md` §3 |
| **G-05 Harness** | 4 | `Flow8MidiHarness.send_short_msg(status, b1, b2)` sends any three bytes; running it overwrites an evidence log | Code read |
| **G-06 Unsourced UI numbers** | 5 | EQ frequency labels and dB readouts have no source | Code read |
| G-07 (new) Evidence overwrite | 4 | Two scripts write over repository evidence files when run | Code read |

Offline experiments (executed this session, nothing transmitted):
- **E-A:** `service.set_gain(1, 10)` and `(1, 20)`, `boundary.execute_command("ch2.gain", 30)`, `engine.channel(3).set_gain(40)` all returned accepted entries (`command_accepted=True`, `dispatch_status=ACCEPTED_OFFLINE`). After the second `set_gain`, `ledger.can_undo` was True and `service.undo()` replayed `('ch1.gain', raw 10)` through the boundary.
- **E-B:** `service.set_phantom(1, True)` and `execute_command("ch2.phantom", True)` were accepted (`ACCEPTED_OFFLINE`). Phantom is not ledgered (`can_undo` stays False after phantom-only commands).
- **E-C:** `Flow8MidiOut` public callables: `open`, `close`, `find_device_id`, `send_cc` and seven `set_*` helpers (all call `send_cc`). `_winmm` and `_handle` are reachable attributes on the service's `midi_out`.

## 2. Gap analysis

### G-01 Preamp gain not closed at the command boundary

- **Root cause:** The gate (`AnalogGainSafetyGate`) lives in `flow8/ui/safety_dialogs.py:299-356`. The command boundary has no notion of a blocked or gated parameter: `_build_phase_c_allowlist` adds `chN.gain` for channels 1–4 unconditionally, and `execute_command` validates the value and dispatches.
- **Source files:** `flow8/command_boundary.py` (allowlist; `execute_command`), `flow8/parameter_engine.py:118` (`set_gain`), `flow8/service.py` (`set_gain`; `_record("gain", …)`; `_replay` branch `parameter_type == "gain"` at about line 540), `flow8/midi_out.py:214-262` (`send_cc` accepts CC 8 on channels 1–4).
- **Affected call paths:**
  1. `Flow8Service.set_gain(ch, value)` (public).
  2. `service.parameter_engine.channel(n).set_gain(...)` (public attribute).
  3. `service.command_boundary.execute_command("chN.gain", v)` (public attribute).
  4. **Undo/redo:** `set_gain` records a ledger entry once a previous value exists; `undo()`/`redo()` then call `_replay("gain")` → `set_gain` → boundary. This is a path that sends gain without any UI action.
  5. `service.midi_out.send_cc(n, 8, v)` (public attribute).
  6. `flow8_midi_harness.py` (arbitrary bytes, see G-05).
  Not a path today: presets (`apply_channel_preset` writes EQ, low cut, compressor only), scenes (`SceneManager.ALLOWED_PARAMETERS = {fader, pan, mute}`), the UI (the Apply button is disabled and `commit_gain` never sends).
- **Risk:** Up to +60 dB of preamp gain reachable by any script or future feature, and replayable through undo. Feedback or speaker damage. Not hardware verified, curve unknown (C-12). Severity: **High**.
- **Proposed fix (needs approval):** The boundary refuses `*.gain` with `Flow8CommandRejectedError` and logs `dispatch_status=REJECTED` with the reason "gated by policy SR-05", before any conversion. The refusal is data in one table (`BLOCKED_PARAMETER_TYPES = {"gain": "SR-05"}`) so lifting it later is a reviewed one-line change. Because the refusal happens at the boundary, `set_gain`, the engine, `_replay` (undo/redo) and direct `execute_command` all inherit it; no ledger record is created for a rejected command (the existing `set_gain` raises before `_record`). Defence in depth: `Flow8MidiOut.send_cc` also refuses CC 8 on channels 1–4 unless called with the boundary's private capability marker (a barrier against accidents, not a security boundary: Python cannot prevent deliberate access).
- **Regression tests:** T-01, T-02, T-03, T-04 (boundary, service, engine, undo/redo), T-20 (UI cannot reach gain), T-08 (low-level).
- **Acceptance criteria:** (a) every call path above raises or is rejected with no `send_cc` call (counter-mock asserts zero); (b) the rejection is logged with status REJECTED and `raw_midi_sent=None`; (c) a pre-existing gain ledger record cannot be replayed (undo raises and sends nothing); (d) the UI gain preview still works and still sends nothing; (e) existing gain tests are migrated (see §5), not deleted.

### G-02 Phantom power not closed at the command boundary

- **Root cause:** The confirmation token and single-use registry exist only in `flow8/ui/safety_dialogs.py:49-160` (`PhantomPowerSafetyGate`). `confirm_and_dispatch` consumes the token and then calls `service.set_phantom(ch, True)`; the service, engine and boundary do not check for a token. OFF has a separate token-free path (`disable_and_dispatch`, which states "OFF needs no warning").
- **Source files:** `flow8/ui/safety_dialogs.py`, `flow8/service.py:317-332` (`set_phantom`), `flow8/parameter_engine.py:228` (`set_phantom`), `flow8/command_boundary.py` (allowlist entry for `ch1.phantom`, `ch2.phantom`), `flow8/midi_out.py` (`send_cc` accepts CC 12 on channels 1–2).
- **Affected call paths:** `service.set_phantom`; `engine.channel(n).set_phantom`; `boundary.execute_command("chN.phantom", True)`; `send_cc(1|2, 12, 127)`; harness. Not paths today: undo/redo (phantom is never ledgered: E-B), scenes, presets.
- **Risk:** +48 V energised onto a ribbon or unbalanced source by any non-UI caller. Severity: **High** (equipment damage). The relay effect has never been observed.
- **Proposed fix (needs approval):**
  1. Move the headless `PhantomPowerSafetyGate` and `PhantomPowerConfirmationToken` from `flow8/ui/safety_dialogs.py` into a non-UI module (for example `flow8/safety.py`) and re-export them from the UI module so existing imports and tests keep working. A boundary must not import the UI layer.
  2. The boundary treats `*.phantom` as GATED: enabling requires an `authorization` argument that the gate validates and consumes (single use, channel bound, expiry); without it the boundary raises `Flow8CommandRejectedError` (status REJECTED). `Flow8Service.set_phantom(ch, enabled, authorization=None)` passes it through.
  3. Owner decision D1: whether **disabling** (OFF) also needs authorization. Today OFF is token-free by design. Options: (A) keep OFF token-free (de-energising is the safer direction); (B) require authorization for both.
  4. `send_cc` refuses CC 12 on channels 1–2 without the boundary's private marker (defence in depth).
- **Regression tests:** T-05 (boundary refuses without token), T-06 (service), T-07 (forged, consumed, wrong-channel, expired token), T-09 (never ledgered, never in scenes/presets), T-21 (UI path still works end to end with a valid token), T-08.
- **Acceptance criteria:** (a) no call path sends CC 12 with value ≥ 1 without a valid token (counter-mock zero); (b) a token is single use; (c) the dialog flow still enables phantom in a mocked-port test; (d) OFF follows decision D1; (e) automated hardware tests cannot enable phantom (T-30).

### G-03 Program Change, SysEx and Note cannot be sent through the application command API: make it structural

- **Root cause:** There is no explicit rule. The only outbound primitive is `Flow8MidiOut.send_cc`, which builds `0xB0 | (ch-1)`; the boundary's allowlist entries carry no message type. The property "no Program Change/SysEx/Note, so no reset" holds by absence of code and would be lost silently if someone added a sender. The raw handle (`_winmm`, `_handle`) is reachable on `service.midi_out`.
- **Source files:** `flow8/midi_out.py`, `flow8/command_boundary.py`, `flow8/midi_constants.py`, `flow8/service.py`.
- **Affected call paths:** none sends such a message today (search of `flow8/` for Program Change, `0xC0`, `0x90`, `0xF0`, `midiOutLongMsg`: none; only `midiOutShortMsg` in `midi_out.py:269`). The risk is future change and direct use of `_winmm`.
- **Risk:** A Program Change 16 on channel 16 resets the mixer (chart: "Loading #16 = RESET!"). Numbering is unresolved (C-01). Severity: **High if introduced, currently latent**.
- **Proposed fix (needs approval):** (1) Declare the policy in code: a `MessageType` with only `CONTROL_CHANGE` permitted; each allowlist spec carries it and `_validate_allowlist` fails at import if any other type appears; constants `FORBIDDEN_MESSAGES` (Program Change 16 on channel 16) and `DISABLED_MESSAGE_TYPES` (Program Change, Note On/Off, SysEx). (2) A pure function `validate_outbound(status, data1, data2)` used by `send_cc` and the harness: it accepts only CC status bytes (`0xB0–0xBF`) with an allowlisted (channel, CC) and refuses everything else, including channel 16 and any status `0xC0–0xFF`. (3) Structural tests: only `midi_out.py` may mention `midiOutShortMsg`/`midiOutLongMsg`; no module under `flow8/` may contain status literals for Program Change, Note or SysEx outside the policy constants; the reset message cannot be constructed.
- **Regression tests:** T-10, T-11, T-12, T-13, T-14.
- **Acceptance criteria:** (a) `validate_outbound` refuses every status byte other than `0xB0–0xBF` and every channel-16 message; (b) an exhaustive loop over all 3-byte messages finds no accepted Program Change, Note or SysEx; (c) the import-time check fails if a non-CC spec is added; (d) the source scan passes for `flow8/` and the harness.

### G-04 Two allow-lists disagree

- **Root cause:** `Flow8MidiOut.send_cc` carries its own hard-coded set of "verified" (channel, CC) pairs (`midi_out.py:230-250`); the boundary has the allowlist. They were written separately.
- **Source files:** `flow8/midi_out.py`, `flow8/command_boundary.py`.
- **Affected call paths:** direct `send_cc` calls and the seven `set_*` helpers.
- **Risk:** 37 pairs (solo on channels 1–7; bus limiter and the nine GEQ bands on channels 8–10) are accepted at the low level but not by the boundary. All are documented in the chart, so this is an inconsistency, not undocumented traffic. Severity: **Medium**.
- **Proposed fix:** One source of truth: `send_cc` derives its accepted set from the allowlist/policy table, so adding or blocking a parameter happens in one place.
- **Regression tests:** T-15 (set equality: pairs accepted by `send_cc` = allowlisted pairs minus blocked), T-08.
- **Acceptance criteria:** the dry-run of all 16 × 128 pairs accepts exactly the allowlisted, non-blocked pairs.

### G-05 Standalone harness can send arbitrary bytes

- **Root cause:** `flow8_midi_harness.py:136-160` `send_short_msg(status, b1, b2, param_name)` packs any three bytes into `midiOutShortMsg`. It imports nothing from `flow8/`, so no policy applies. Its `__main__` block sends a fixed safe list but also opens the real ports and overwrites `FLOW8_PHASE1_RAW_MIDI_LOG.md` in the working directory.
- **Source files:** `flow8_midi_harness.py`; related read-only logger `flow8_midi_in_logger.py` (see G-07).
- **Affected call paths:** anyone importing `Flow8MidiHarness` or editing its test list.
- **Risk:** Program Change 16, gain or phantom sent by hand or by a modified script, with no log restriction. Severity: **High** (misuse), currently latent.
- **Proposed fix (needs approval):** Keep the script (no deletion) but route it through `validate_outbound` (G-03): refuse non-CC messages and anything not allowlisted or blocked (gain, phantom); require an explicit `--allow-write` flag and print the exact message list before sending; write logs to a new timestamped file, never overwriting an existing one. Decision D4: restrict in place, or move it under a `tools/` directory with a read-only default.
- **Regression tests:** T-16, T-17, T-18 (harness refuses the forbidden list; refuses by default; never overwrites a file).
- **Acceptance criteria:** (a) calling `send_short_msg` with Program Change, Note, SysEx, channel 16, gain or phantom raises before any driver call (driver mocked, counter zero); (b) without the explicit flag the script sends nothing; (c) an existing log file is never opened for writing.

### G-06 Unsourced numbers shown in the UI

- **Root cause:** `channel_detail.py:153-158` `EQ_BANDS` labels (80 Hz, 400 Hz, 2.5 kHz, 10 kHz) have no source (C-04). Fader readouts use `format_db` (`mixer_console.py:46`) with unity at raw 101 (C-05). Gain preview shows "Approx. dB" (already labelled).
- **Affected call paths:** display only.
- **Risk:** Misleads the operator about what a control does. Severity: **Medium**.
- **Proposed fix (needs approval; decision D5):** Show EQ bands as LOW, LOW-MID, HI-MID, HIGH with no frequency, or show the manufacturer specification figures with the label "from the Behringer specification; behaviour unconfirmed". Prefix derived dB readouts with "≈" and keep the raw value primary.
- **Regression tests:** T-22 (no frequency label without the "unconfirmed" qualifier), T-23 (derived readouts carry the approximate marker).
- **Acceptance criteria:** the tests pass; screenshots from the running app at 1366×768.

### G-07 Evidence files can be overwritten by scripts (new)

- **Root cause:** `flow8_midi_harness.py` writes `FLOW8_PHASE1_RAW_MIDI_LOG.md`; `flow8_midi_in_logger.py` `__main__` writes `FLOW8_PHASE2B_RAW_MIDI_LOG.md` by default, both in place.
- **Risk:** Loss of historical evidence. Severity: **Medium**. (I avoided this in this project by passing a different log path to the logger class.)
- **Proposed fix:** Refuse to write over an existing file; default to a timestamped name; tests T-18.
- **Acceptance criteria:** running either script twice produces two files and never modifies the first.

## 3. Owner decisions required before implementation

| ID | Decision | Options |
|---|---|---|
| D1 | Does disabling +48 V need authorization? | A: OFF stays token-free (existing behaviour); B: both directions need authorization |
| D2 | Is the gain block absolute? | A: hard block with no runtime override (recommended until gain is hardware verified); B: block with an owner-controlled flag that tests can set |
| D3 | May the headless phantom gate move out of `flow8/ui/` (re-exported from the old path)? | Yes (recommended) / No: then the boundary cannot validate tokens |
| D4 | Harness: restrict in place, or move under `tools/`? | Restrict in place (smaller change) / move |
| D5 | EQ band labels | No frequencies / specification figures labelled unconfirmed |

## 4. Implementation order (after approval; not started)

1. Tests first (red): T-01…T-23 added so that they fail on today's code for the right reason (§ of the test plan lists which fail now).
2. Policy data and `validate_outbound` (G-03, G-04).
3. Boundary gates: gain block, phantom authorization (G-01, G-02), with the test-seam changes in §5.
4. `send_cc` derived from policy (G-04) and defence-in-depth markers.
5. Harness and logger restrictions (G-05, G-07).
6. UI labels (G-06).
7. Full regression run with categories reported separately; hardware tests not run.

## 5. Existing tests that depend on today's behaviour (must be migrated, not deleted)

| File | Lines | Dependence | Migration |
|---|---|---|---|
| `tests/test_parameter_engine.py` | 67–74, 219–221 | `set_gain(...)` succeeds on channels 1–4 | Assert the boundary rejects it; keep the channel-restriction checks for 5–7 |
| `tests/test_bus_mappings.py` | 162 | `set_gain(-20 dB)` succeeds | Same |
| `tests/test_preset_service.py` | 15, 26, 69 | Establishes a gain baseline with `service.set_gain` to prove presets leave gain unchanged | Establish the baseline through `state_store.set_commanded_value` (test-only seam), keep the "unchanged" assertions |
| `tests/test_parameter_engine.py` | 101–112 | `set_phantom(True)` succeeds | Use a valid authorization; add the refusal cases |
| `tests/test_service_ledger_scenes.py` | 138–145 | `service.set_phantom` | Same |
| `tests/test_mixer_history.py` | 178 | `service.set_phantom(1, True)` | Same |
| `tests/test_command_boundary_integrity.py` | 133–140, 228 | phantom scope; ch5 gain rejected | Phantom: authorized path; the ch5 rejection stays true |
| `tests/test_safety_dialogs.py`, `tests/test_channel_detail.py` | gate tests | Must keep passing unchanged after the gate moves (re-export) | none |

## 6. Residual risks after the plan

Python cannot make `_winmm` private: a determined caller can still call `midiOutShortMsg` through the handle. Mitigation is the structural test (only `midi_out.py` may call it), review discipline, and the harness restrictions. The plan also does not verify any parameter on hardware; gain stays unverified (C-12).

## 7. S1.1 acceptance

S1.1 (this analysis) is complete when the four documents exist and no source or hardware state changed. Verified: `git diff --stat -- flow8 tests` equals the pre-S1 value (five Stage 1 files, 151 insertions, 12 deletions); `git log -1` is still `456fd5a`; ports were closed in every experiment.
