# S1.2 Safety Hardening: Implementation Plan

Date: 2026-11-18. Stage S1.2 is **preparation only**. No source code was modified, no MIDI sent, no hardware opened, nothing committed, no evidence deleted or overwritten. Read-only checks this session: source reads, searches, and offline `Flow8Service(auto_connect=False)` experiments with ports verified closed.

Companions: `S1_2_FILE_CHANGE_MAP.md`, `S1_2_SAFETY_TEST_SPEC.md`, `S1_2_REGRESSION_MIGRATION_PLAN.md`, `S1_2_ACCEPTANCE_CRITERIA.md`. Background: `S1_1_SAFETY_HARDENING_PLAN.md`, `FLOW8_SAFETY_POLICY.md`, `FLOW8_UNRESOLVED_CONFLICTS.md`.

Objective: the safety policy must be **enforced on every application call path**, not merely hidden in the UI.

## 1. Owner decisions and what they mean in code

| Decision | Requirement | Design consequence |
|---|---|---|
| **D1** | +48 V ON needs explicit authorization and direct user confirmation; OFF is allowed without a token; presets, undo/redo and automation never enable it; OFF always available | The boundary refuses `chN.phantom` with a true value unless a gate-issued, user-confirmed authorization is active for that channel (consumed once). OFF is never refused. Presets, undo/redo and scenes are unable to obtain an authorization (no import path, tested) |
| **D2** | Gain: absolute block; no runtime override, no environment variable, no hidden development bypass | The block is a constant table in the shared safety module, read by every layer. No `os.environ`, `sys.argv`, debug flag or setter exists, and a source scan proves it. Lifting it later means a reviewed code change |
| **D3** | Move the headless phantom policy out of `flow8/ui/`; shared module for Service and Boundary; keep a re-export at the old path | New `flow8/safety.py` (standard library only). `flow8/ui/safety_dialogs.py` re-exports the same objects so `from flow8.ui.safety_dialogs import PhantomPowerSafetyGate` still works |
| **D4** | Move or isolate the harness under `tools/` after checking references; app code cannot reach arbitrary MIDI sending; no arbitrary MIDI by default; never Program Change reset; never overwrite historical logs; unique output files; preserve evidence | `tools/` directory, harness validated by `flow8.safety.validate_outbound`, explicit allow flag, exclusive-create output files with timestamp and process id, a guard that `flow8/` never imports `tools/` |
| **D5** | EQ labels become Band 1–4; spec figures not shown as verified centres | `EQ_BANDS` labels changed; a historical-correction note is added |
| **G-04** | Audit the 37 pairs; do not expand the boundary; keep unresolved pairs blocked | Section 5: all 37 stay blocked; `send_cc` derives its accepted set from one policy table |
| **G-07** | Audit every script that writes evidence; unique files or an explicit directory; never overwrite | Section 6 |

## 2. Call graphs (read from the code this session)

### 2.1 Gain (today)

```
UI Inspector gain slider ──> AnalogGainSafetyGate.stage_preview()            (no dispatch)
UI Apply button ───────────> disabled; commit_gain() raises, never sends     (safety_dialogs.py:343)

Any other caller:
  Flow8Service.set_gain(ch, v)                      service.py (public)
    └─ _known_value("gain")                         previous value
    └─ _dispatch_and_notify(engine.channel(n).set_gain, v)
         └─ Flow8ChannelStrip.set_gain             parameter_engine.py:118  (rejects ch 5-7 only)
              └─ Flow8CommandBoundary.execute_command("chN.gain", v)       command_boundary.py
                   └─ allowlist check (gain ch1-4 present) -> convert -> bounds
                   └─ Flow8MidiOut.send_cc(n, 8, raw)                      midi_out.py:214
                        └─ midiOutShortMsg                                 midi_out.py:269
    └─ _record("gain", ...)  -> ledger entry (when a previous value exists)

Undo / redo:
  Flow8Service.undo() -> CommandLedger.undo() -> _apply() -> executor = Flow8Service._replay
    └─ parameter_type == "gain" -> Flow8Service.set_gain(...)  -> (same chain as above)
Direct:   service.command_boundary.execute_command("chN.gain", v)
          service.parameter_engine.channel(n).set_gain(v)
          service.midi_out.send_cc(n, 8, v)
Not paths: apply_channel_preset (EQ, low cut, compressor only), scenes (fader, pan, mute only), UI widgets.
```

### 2.2 Phantom (today)

```
UI request ON:  ChannelDetailPanel.request_phantom -> PhantomPowerSafetyGate.issue_token(ch)
                  -> PhantomPowerConfirmationDialog (user clicks CONFIRM) -> on_confirm(token)
                  -> PhantomPowerSafetyGate.confirm_and_dispatch(service, ch, token)   [validate, consume]
                  -> service.set_phantom(ch, True)                                      <- no token check below this line
UI request OFF: PhantomPowerSafetyGate.disable_and_dispatch(service, ch) -> service.set_phantom(ch, False)
service.set_phantom(ch, en) -> _dispatch_and_notify(engine.channel(ch).set_phantom, en)
   -> Flow8ChannelStrip.set_phantom -> boundary.execute_command("chN.phantom", en) -> send_cc(ch, 12, 0|127)
Not a path today: ledger (phantom is never recorded, ledger refuses "phantom_power"), scenes, presets.
Unprotected: service.set_phantom, engine, boundary, send_cc called directly.
```

### 2.3 Target (after S1.2)

```
                              flow8/safety.py  (standard library only; imports nothing from flow8/ui)
                              ├─ POLICY table: blocked / gated / allowed per (channel, CC) and per parameter type
                              ├─ gain:   BLOCKED absolutely
                              ├─ phantom ON: needs an active user-confirmation grant (one use, channel-bound)
                              ├─ validate_outbound(status, d1, d2): control change only, allowed pairs only
                              └─ PhantomPowerSafetyGate, PhantomPowerConfirmationToken (moved here)

UI  -> gate.confirm_and_dispatch -> [grant for ch] -> service.set_phantom(ch, True)
Service / Engine -> Boundary.execute_command ──(1) safety.check(param_id, value)  refuse gain; refuse phantom ON without grant
                                              ──(2) existing allowlist and value validation
                                              ──(3) consume grant, open one-shot permit
                                              ──(4) Flow8MidiOut.send_cc  ──(5) safety.validate_outbound again; phantom ON needs the permit
Ledger replay -> service._replay -> same chain; ledger also refuses to record "gain"
Harness (tools/) -> safety.validate_outbound before any driver call; control change only; allowlisted pairs; gain, phantom, reset refused
```

Defence in depth: **boundary** (primary), **`send_cc`** (second layer, derived from the same table), **ledger** (never records gain), **service** (`set_gain` fails early with a clear error before computing previous values), **harness** (own validation). Python cannot make attributes private; the structural tests in `S1_2_SAFETY_TEST_SPEC.md` ensure no other module touches the driver or the grant machinery.

## 3. Dependencies and imports

Current: `flow8/service.py` → `command_boundary`, `parameter_engine`, `midi_out`, `ledger`; `command_boundary` → `midi_out`, `state_model`, `parameter_mapping`; `midi_out` → `midi_constants`, `parameter_mapping`; `ui/components/channel_detail.py` → `ui/safety_dialogs.py`; tests import the gates from `flow8.ui.safety_dialogs` (`test_safety_dialogs.py:7`, `test_channel_detail.py:28`).

Target: `flow8/safety.py` imports only the standard library and `midi_constants`. New edges: `midi_out` → `safety`, `command_boundary` → `safety`, `ledger` → `safety`, `service` → `safety`, `ui/safety_dialogs` → `safety`. No cycle: `safety` imports none of them. `tkinter` stays in `ui/safety_dialogs.py` (the dialog widget). `main.py`/PyInstaller spec (`FLOW8-CyberNeon.spec`, `Analysis(['main.py'])`) need no change; `tools/` is not bundled.

## 4. Design details

### 4.1 `flow8/safety.py` (new)

- `BLOCKED_PARAMETER_TYPES = {"gain": "SR-05"}` (constant `frozenset`/mapping; no setter).
- `PHANTOM_ON_GATED` rule and the moved classes `PhantomPowerConfirmationToken`, `_PhantomPendingRequest`, `PhantomPowerSafetyGate` (unchanged behaviour: `validate_channel`, `issue_token`, `revoke_token`, `confirm_and_dispatch`, `disable_and_dispatch`).
- Authorization mechanism: `confirm_and_dispatch` validates and consumes the token, then calls `service.set_phantom(ch, True)` **inside a one-shot grant bound to that channel** (a `contextvars.ContextVar` set and reset around the call). The boundary asks `safety.consume_phantom_grant(channel)`; no grant means `Flow8CommandRejectedError`. The service signature stays `set_phantom(channel, enabled)`, so `set_phantom.assert_called_once_with(1, True)` in existing tests still holds. An explicit keyword argument was considered and rejected because it would break those assertions (`test_safety_dialogs.py:29,112`, `test_channel_detail.py:293`).
- `validate_outbound(status, data1, data2)`: accepts only a control change (`0xB0–0xBF`) whose (channel, CC) is in `ALLOWED_PAIRS`; refuses every other status byte (Program Change, Note, SysEx, system messages), refuses channels 13–16, refuses gain pairs always, refuses phantom ON without the boundary's one-shot permit, and names the rule that refused.
- `ALLOWED_PAIRS` is derived from the boundary allowlist at import (single source), not copied by hand.
- Exports are limited by `__all__`; the grant and permit functions are underscore-private.
- No `os`, `sys.argv`, `environ`, `getenv` or debug-flag code in this module (tested).

### 4.2 `flow8/command_boundary.py`

At the start of `execute_command`, before value conversion: `safety.check_parameter(param_id, value)`. A refusal is logged exactly like an allowlist refusal (`DispatchStatus.REJECTED`, `command_accepted=False`, `raw_midi_sent=None`) and raises `Flow8CommandRejectedError` with the rule id. Phantom OFF skips the gate. After a successful value validation the boundary consumes the grant (phantom ON only), opens the one-shot permit around `send_cc`, and closes it in `finally`.

### 4.3 `flow8/midi_out.py`

Replace the hard-coded verified set in `send_cc` (lines 230–250) with `safety.validate_outbound`, so the low-level accepted set equals the allowlist minus blocked pairs (G-04). Phantom ON through `send_cc` needs the permit. The seven `set_*` helpers keep working (fader, mute, pan are allowed pairs).

### 4.4 `flow8/service.py`, `flow8/ledger.py`

- `Flow8Service.set_gain`: first statement raises the same rejection (clear message, no state touched). `_replay` for `"gain"` therefore raises; the ledger refuses to record gain (`CommandRecord.undoable` false for `gain`, next to the existing phantom rule), so no gain record can exist.
- `Flow8Service.set_phantom`: unchanged signature; enabling relies on the boundary check.

### 4.5 UI

`flow8/ui/safety_dialogs.py`: import the moved classes from `flow8.safety` and re-export (`__all__` preserved). `AnalogGainSafetyGate.is_verified_mapping_available()` returns the policy constant (False). `channel_detail.py`: EQ labels (D5). No widget gains a new dispatch path.

### 4.6 `tools/`

`tools/flow8_midi_harness.py` and `tools/flow8_midi_in_logger.py` (moved; section 6). `tools/README.md` states the restrictions. The application package never imports `tools` (tested).

## 5. G-04: audit of the 37 channel/CC pairs accepted by `send_cc` but not authorised by the boundary

Method: the 37 pairs were produced by the dry-run of all 16 × 128 pairs on an unopened `Flow8MidiOut` (no port opened). Each pair was checked against the manufacturer chart (E01, Quick Start Guide V 1.0, PDF p. 8) and the capability matrix. **No pair is added to the boundary.** All 37 remain blocked; the reason is recorded per pair. Important distinction: on channels 8–10, CC 8 is the **bus limiter** and CC 12 is **9-band EQ 125 Hz**; they are unrelated to input **gain** (CC 8 on channels 1–6) and **phantom** (CC 12 on channels 1–2). A policy keyed on the CC number alone would confuse them, so every rule is keyed on (channel, CC).

| # | (MIDI ch, CC) | Function (chart, E01 p. 8) | Purpose | Safety level | Capability class | Why blocked | Decision |
|---|---|---|---|---|---|---|---|
| 1 | (1, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 2 | (2, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 3 | (3, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 4 | (4, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 5 | (5, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 6 | (6, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 7 | (7, 6) | SOLO (input channel) | Solo switch for the channel (guide item 23 mentions SOLO mode) | NORMAL (semantics unresolved) | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Solo behaviour (pre/post fader, effect on phones, main or monitors) is not documented in the sources I have; not implemented in the boundary | **BLOCKED** |
| 8 | (8, 8) | BUS LIMITER (MAIN L/R) | Output limiter threshold, -30..0 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Changes output dynamics of a live bus; curve unconfirmed (C-12); not implemented. NOT input gain | **BLOCKED** |
| 9 | (8, 11) | 9-BAND EQ 62 Hz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 10 | (8, 12) | 9-BAND EQ 125 Hz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); 62 vs 62.5 Hz label conflict (C-11); not implemented. NOT phantom | **BLOCKED** |
| 11 | (8, 13) | 9-BAND EQ 250 Hz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 12 | (8, 14) | 9-BAND EQ 500 Hz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 13 | (8, 15) | 9-BAND EQ 1 kHz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 14 | (8, 16) | 9-BAND EQ 2 kHz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 15 | (8, 17) | 9-BAND EQ 4 kHz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 16 | (8, 18) | 9-BAND EQ 8 kHz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 17 | (8, 19) | 9-BAND EQ 16 kHz (MAIN L/R) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 18 | (9, 8) | BUS LIMITER (MON 1) | Output limiter threshold, -30..0 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Changes output dynamics of a live bus; curve unconfirmed (C-12); not implemented. NOT input gain | **BLOCKED** |
| 19 | (9, 11) | 9-BAND EQ 62 Hz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 20 | (9, 12) | 9-BAND EQ 125 Hz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); 62 vs 62.5 Hz label conflict (C-11); not implemented. NOT phantom | **BLOCKED** |
| 21 | (9, 13) | 9-BAND EQ 250 Hz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 22 | (9, 14) | 9-BAND EQ 500 Hz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 23 | (9, 15) | 9-BAND EQ 1 kHz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 24 | (9, 16) | 9-BAND EQ 2 kHz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 25 | (9, 17) | 9-BAND EQ 4 kHz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 26 | (9, 18) | 9-BAND EQ 8 kHz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 27 | (9, 19) | 9-BAND EQ 16 kHz (MON 1) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 28 | (10, 8) | BUS LIMITER (MON 2) | Output limiter threshold, -30..0 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Changes output dynamics of a live bus; curve unconfirmed (C-12); not implemented. NOT input gain | **BLOCKED** |
| 29 | (10, 11) | 9-BAND EQ 62 Hz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 30 | (10, 12) | 9-BAND EQ 125 Hz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); 62 vs 62.5 Hz label conflict (C-11); not implemented. NOT phantom | **BLOCKED** |
| 31 | (10, 13) | 9-BAND EQ 250 Hz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 32 | (10, 14) | 9-BAND EQ 500 Hz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 33 | (10, 15) | 9-BAND EQ 1 kHz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 34 | (10, 16) | 9-BAND EQ 2 kHz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 35 | (10, 17) | 9-BAND EQ 4 kHz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 36 | (10, 18) | 9-BAND EQ 8 kHz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |
| 37 | (10, 19) | 9-BAND EQ 16 kHz (MON 2) | Output graphic EQ band, +/-15 dB | ELEVATED | DOCUMENTED, not implemented, not verified, read-back unconfirmed | Up to +15 dB on a live bus (feedback risk); curve unconfirmed (C-12); not implemented | **BLOCKED** |


Result: 37 of 37 pairs documented in the chart, none implemented, none verified, none read-back. Classification: solo NORMAL-but-unresolved, limiter and GEQ ELEVATED. Decision: **BLOCKED**. Unlocking any group would need its own approved stage (C-11 for GEQ labelling, C-12 for curves, solo semantics undocumented).

## 6. G-07: scripts that write files (audit)

Searched all Python in the repository (excluding `cueair_extracted/`) and the PowerShell scripts for file writes.

| Script | Writes | Overwrite risk | Plan |
|---|---|---|---|
| `flow8_midi_harness.py:196,239` | `FLOW8_PHASE1_RAW_MIDI_LOG.md` in the working directory, mode `w` | **Overwrites historical evidence** | Move to `tools/`; output through `open(..., "x")` into a new file `tools/output/harness_<UTC timestamp>_<pid>.md`; refuse to write into any existing file; never the historical name |
| `flow8_midi_in_logger.py:16,49` | default `FLOW8_PHASE2B_RAW_MIDI_LOG.md`, mode `w` | **Overwrites historical evidence** | Same; require an explicit output directory or default to `tools/output/` |
| `docs/audit/stage1_screenshots/hw_verify_stage1.py:27` (this project, Stage 1 hardware attempt) | `docs/audit/hw_stage1/{mode}_events.jsonl`, mode `w`; screenshots with fixed names | **Overwrites** `d01_events.jsonl` and screenshots on rerun | Move under `tools/`; timestamped names; exclusive create; the existing `docs/audit/hw_stage1/` files are never opened for writing |
| `docs/audit/stage1_screenshots/capture_stage1.py` | fixed PNG names `1366x768_1_main.png` ... in its own folder | **Overwrites** earlier screenshots | Same; add a run-id suffix |
| `extract_and_analyze_dlls.py:20,83` | extracted DLLs and `native_analysis.json` into a **Mixing Station** analysis directory outside this repository | Overwrite of research artifacts of another product | Out of FLOW 8 MIDI-evidence scope; flagged to the owner, not changed |
| `dump_msi.ps1:84` | `Out-File` to a Mixing Station analysis path | same | flagged, not changed |
| `flow8/` package, `tests/` | no file writes (searched) | none | Test: assert none |

Rules for every writer: (1) never open an existing file for writing; (2) unique name with UTC timestamp and process id; (3) output directory explicit or `tools/output/`; (4) a test that the historical evidence files keep their SHA-256 after running the tools against a mocked driver. The current SHA-256 values of all evidence files are recorded before implementation (see `S1_2_SAFETY_TEST_SPEC.md` E-06 and its appendix).

Harness reference check (D4): the file name appears in documents only (`FLOW8_PHASE1_MIDI_TEST_RESULTS.md`, `FLOW8_PHASE2A_IMPLEMENTATION.md`, `FLOW8_PHASE_UI1_REPOSITORY_AUDIT.md`, `docs/product/*`) and in its own class name; no Python imports it; the PyInstaller spec bundles only `main.py`. Moving it therefore breaks no code. The documents that link to the old path get an errata line (links were already absolute paths to another folder).

## 7. Order of work (after approval)

| Step | Work | Gate before the next step |
|---|---|---|
| 0 | Record baseline: full test run (categories), SHA-256 of every evidence file and every file to be modified; create the rollback copies (section 9) | Baseline recorded |
| 1 | Add the new safety tests (red) and the no-hardware guard; confirm each fails for the stated reason | Red list matches `S1_2_SAFETY_TEST_SPEC.md` |
| 2 | Create `flow8/safety.py` with the moved gate classes and the policy table; re-export from `ui/safety_dialogs.py`; no behaviour change yet | Full suite identical to baseline |
| 3 | Boundary gates (gain block, phantom ON grant) + ledger rule + `set_gain` early failure | Gain/phantom tests green |
| 4 | `send_cc` derives from policy (G-04) | 37-pair test green |
| 5 | Migrate existing tests (section of the migration plan) | No test deleted; counts reconciled |
| 6 | Harness/logger moved and restricted (D4, G-07) | Evidence hashes unchanged |
| 7 | EQ labels (D5) + correction notes | Label tests green, screenshots |
| 8 | Full regression with categories reported separately; hardware tests NOT RUN | Acceptance criteria |

Each step ends with a run of the full suite; any step that turns an unrelated test red is paused and reported.

## 8. Backward-compatibility risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Existing tests that dispatch gain or phantom directly now fail | Certain (intended) | Migration plan: real gate path for phantom ON, rejection assertions for gain; none deleted |
| `set_phantom.assert_called_once_with(1, True)` assertions | Avoided | Ambient grant keeps the signature |
| Third-party code importing `flow8.ui.safety_dialogs` classes | Possible | Re-export keeps names and identity (`is` equality tested) |
| `PhantomPowerSafetyGate._pending` is class-level state | Moved as is | Same object after the move; tests clear nothing new |
| Contextvar grant not visible across threads | Real | The grant wraps the synchronous call chain in one thread; a worker thread cannot reuse it; tested |
| Offline tests that count driver calls | Possible | Counters read the same `send_cc` |
| `send_cc` now refuses 37 pairs and gain | Intended | T-15 |
| Harness moved: scripts calling it by path | None found | Documents get errata |
| EQ label text asserted in tests | None found (search of `tests/` for "80 Hz", "LOW (" returned nothing) | Add new label tests |

## 9. Rollback strategy (no Git reset, no destructive operations)

1. Before any edit, copy every file that will be modified into `docs/product/rollback_s1_2/<UTC timestamp>/` keeping relative paths, and write `MANIFEST.sha256` (hash of each original). This also protects the uncommitted Stage 1 work.
2. All new files are additions (nothing overwritten). Moves are done as **copy first**; the originals stay at their old paths until the owner approves removal, with a one-line stub comment left only if the owner asks.
3. Rollback = copy the saved originals back over the modified files after saving the current state into a **new** timestamped folder (so a rollback is itself reversible), then delete nothing. Verification: hashes equal the manifest; full test run equals the baseline.
4. No `git reset`, `git checkout --`, `git stash drop`, `git clean`, or history rewriting. Commits remain forbidden unless the owner asks.
5. Rollback triggers: any failure in a safety test that cannot be fixed within the step; any change to an evidence file hash; any physical-port open attempt in a test.

## 10. Risks and open items

- The grant mechanism relies on contextvars and an unexported function; a determined in-process caller can still import it. The structural tests restrict where it may be referenced.
- Issuing a token is a programmatic call (`issue_token`); "direct user confirmation" is enforced by the dialog flow and by tests that only the dialog and the Inspector reference it. A script that calls `issue_token` itself would still produce a valid token. Recommendation for the owner: accept this as a residual in-process risk, or require the dialog object to mint tokens (small extra change, listed as option O1 in the file map).
- No parameter is verified on hardware by this work; gain stays unverified (C-12).
- Hardware investigation of inbound telemetry (C-02) remains paused.

## 11. Decision requested

Approve implementation of steps 0–8, or amend. Option O1 (dialog-minted tokens) needs a yes or no.
