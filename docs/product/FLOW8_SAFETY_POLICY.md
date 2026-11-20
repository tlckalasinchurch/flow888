# FLOW 8 Safety Policy

Date: 2026-11-18. Stage S1, documentation only. This document states the rules and the **current enforcement state read from the code this session**. It enforces nothing by itself and changes no code.

## 1. Safety levels (used in `FLOW8_PARAMETER_MAPPING.md`)

| Level | Meaning | Rule |
|---|---|---|
| NORMAL | Reversible tone or routing change | Allowed through the command boundary, labelled COMMANDED |
| ELEVATED | Can change loudness or the whole mix (faders, sends, bus levels, bus limiter, GEQ) | Allowed; user-initiated only; never changed by presets (S2) |
| GATED | Equipment-damage or large-gain risk | Needs a verified mapping **and** explicit confirmation; never automated |
| DISABLED | No sender may exist or be enabled | Enabling needs a written decision and hardware evidence |
| FORBIDDEN | Must never be transmitted by this application | No code path, no UI, no test may send it |

## 2. Rules

| ID | Rule |
|---|---|
| SR-01 | **No Program Change sender may exist or be enabled** (any channel) until approved with evidence. |
| SR-02 | **Program Change 16 on MIDI channel 16 (mixer reset) is FORBIDDEN.** It may not be sent by the application, a test, a script or the diagnostic harness. |
| SR-03 | FX Program Change (ch 13 / 14) is DISABLED. |
| SR-04 | Snapshot recall (ch 16, Program Change 1–15) is DISABLED until the numbering conflict C-01 is resolved with evidence. |
| SR-05 | Preamp gain is GATED: no dispatch from the UI until the mapping is verified on hardware and the owner lifts the gate. |
| SR-06 | +48 V is GATED and never automated: no preset, scene, undo, redo, macro, test or script may energise it. Hardware tests never enable it. |
| SR-07 | No UI control for a parameter that is not DOCUMENTED in the manufacturer chart. No control for UNCONFIRMED, UNSUPPORTED, DISABLED or FORBIDDEN rows. |
| SR-08 | The app must never claim it reads a value from the hardware without a mixer-originated message. A driver return code is not DSP confirmation, not USB delivery and not a physical effect. |
| SR-09 | A value may be labelled HARDWARE VERIFIED only with recorded physical evidence (operator observation with a protocol, or a measurement). |
| SR-10 | CueAir content is never used as evidence of a FLOW 8 capability. |
| SR-11 | Unknown stays unknown: no default is shown as a current hardware value; after a disconnect all values return to UNSYNCED. |
| SR-12 | Presets and plans may write only parameters that are DOCUMENTED and NORMAL/ELEVATED, never gain, phantom, Program Change or Note messages (S2). |

## 3. Enforcement state today (read from the code, not tested on hardware)

| Rule | State | Evidence (this session) |
|---|---|---|
| SR-01 | **Holds in the application**: the only outbound path is `Flow8MidiOut.send_cc`; no Program Change, Note or SysEx function exists in `flow8/` | Read of `midi_out.py` (methods: `send_cc` plus seven Phase 2A helpers for Main fader, Channel 1 fader, mute and pan, all calling `send_cc`); search of `flow8/` for Program Change / `0xC0` found none |
| SR-02 | Holds in the application: reset cannot be constructed because `send_cc` builds only `0xB0|ch` messages and rejects channels 13–16. **Not guaranteed for `flow8_midi_harness.py`**, a standalone script whose `send_short_msg(status, b1, b2)` accepts arbitrary bytes (it is only called from its own fixed test list today) | Read of `midi_out.py:214-262` and `flow8_midi_harness.py:136-160` |
| SR-03 / SR-04 | Hold in the application (no sender); no explicit "disabled" flag exists, only absence of code | same |
| SR-05 | **Partially holds.** The UI's `AnalogGainSafetyGate.is_verified_mapping_available()` returns `False` and `commit_gain` never sends; the Apply button is disabled. **But `Flow8Service.set_gain()` and the command boundary allow `chN.gain` (ch 1–4)**, so any non-UI caller can send gain | `safety_dialogs.py:299-356`; `service.py` `set_gain`; `command_boundary.py` allowlist |
| SR-06 | **Partially holds.** The UI routes +48 V through a single-use confirmation token. Presets, scenes, undo and redo exclude phantom (`service.set_phantom` is not ledgered; scenes capture fader, pan, mute only). **But `Flow8Service.set_phantom()` and the boundary allowlist accept `ch1/ch2.phantom` with no gate**, so a script or future code can bypass the dialog | `safety_dialogs.py:49-100`; `service.py:317-332`; `command_boundary.py:173` |
| SR-07 | **Violated in details**, not by missing controls: EQ band labels show frequencies with no source; fader dB readouts and the gain preview show derived numbers (labelled "approx"/"UNVERIFIED" only for gain) | `channel_detail.py:153-158`; `parameter_mapping.py` |
| SR-08 | Holds in labels: the UI shows "HW APPLIED: UNKNOWN" and never "hardware verified"; no parameter carries the `HARDWARE_TESTED` level in code | search of `flow8/ui/` and `state_model.py` |
| SR-09 | Holds in code; **violated in earlier documents** (conflict C-10) | register |
| SR-10 | Holds in this stage's documents | — |
| SR-11 | Holds after the Stage 1 work (offline tests); not tested on hardware | Stage 1 tests |
| SR-12 | Holds for the 13 existing presets (EQ, low cut, compressor only); not structurally enforced | `presets.py` |

## 4. Enforcement gaps to close later (not implemented in S1)

| Gap | Risk | Proposed control (needs approval, S2 or later) |
|---|---|---|
| G-01 `service.set_gain` ungated | Gain up to +60 dB reachable outside the UI | Block `gain` in the boundary behind a capability-table flag; test that dispatch raises |
| G-02 `service.set_phantom` ungated | Phantom relay reachable outside the dialog | Require the confirmation token inside the boundary; test with a forged call |
| G-03 No explicit disabled flag for Program Change, Note, SysEx | A future change could add a sender silently | Capability table marks them DISABLED/FORBIDDEN; boundary refuses any non-CC message type; test asserts reset cannot be constructed |
| G-04 `midi_out.send_cc` accepts solo, bus limiter and GEQ though the boundary does not allow them | Inconsistent allow-lists | Align the low-level allow-list with the capability table |
| G-05 Diagnostic harness can send any bytes | Reset or phantom could be sent by hand | Mark the script restricted in its header; require a reviewed message list |
| G-06 Unsourced numbers in UI | Misleading values | Label or remove (S2) |

## 5. Hardware test rules (when hardware work resumes, with owner approval)

1. Phantom: never enabled in any automated test.
2. Gain and reset: never sent.
3. Before a write test: record the mixer's current panel state by hand (there is no read-back); after: the owner restores it. No claim of "restored" can be made from software.
4. Evidence needed for HARDWARE VERIFIED: operator observation protocol or measurement, recorded with the command log.
5. Evidence for read support: raw bytes from `FLOW 8 MIDI IN` while the owner moves a named control, recorded with timestamps.

## 6. S1.2 enforcement update (2026-11-18, verified by tests; the tables above are kept as the earlier state)

| Rule | State after S1.2 | Evidence |
|---|---|---|
| SR-01 / SR-03 / SR-04 | **Enforced in code**: `flow8.safety.validate_outbound` refuses every message that is not an allowlisted control change; channel 16 refused | tests M-01, M-04, M-05 |
| SR-02 | **Enforced**: `validate_outbound(0xCF, 16, ...)` raises with rule SR-02; no sender exists | M-06, E-01 |
| SR-05 gain | **Enforced at every layer**: boundary, service (`set_gain`), engine, ledger (gain is never recorded), `send_cc`, harness. No environment, runtime or development override exists (tested) | B-01…B-08 |
| SR-06 phantom | **Enforced**: +48V ON needs a one-shot, thread-bound grant created only by `PhantomPowerSafetyGate.confirm_and_dispatch`; OFF needs none; presets, undo/redo and scenes cannot enable it | P-01…P-13 |
| G-01, G-02 | Closed | as above |
| G-03 | Closed (structural policy and tests) | M-01, M-05, M-06 |
| G-04 | Closed: `send_cc` accepts exactly the allowlist minus gain (93 pairs for value 0); the 37 pairs are refused | M-02, M-03 |
| G-05, G-07 | Closed for the repository tools: restricted copies under `tools/`; originals kept unchanged as evidence | E-01…E-09 |
| G-06 | EQ labels are BAND 1–4 with an "unconfirmed" note; fader dB readouts still derived (C-05) | L-01, L-02 |

Residual risks: an in-process caller can still reach `flow8.safety` internals or `_winmm` (Python has no private members); a script can mint its own phantom token with `issue_token` (option O1 was not approved); the original root-level `flow8_midi_harness.py` still exists unchanged and still sends arbitrary bytes if run.

## 7. Owner decision 2026-11-20: bus limiter / GEQ and FX engines opened

The owner approved, in this session, opening the bus limiter, the 9-band GEQ and the FX engines ("อนุมัติเปิด GEQ, Limiter และ FX"). All are DOCUMENTED in E01 (MIDI chart, printed p. 14–15) and shown in the FLOW app (E21). None is hardware-verified.

| Rule | Change | Enforced by |
|---|---|---|
| SR-01 | **Narrow exception:** Program Change data bytes 1–16 on MIDI channels 13 and 14 (FX 1 / FX 2 preset select) may be sent. Every other Program Change, every Note, SysEx and system message is still refused. | `validate_outbound` (Program Change branch reads the allowlist's two `program_change` entries); `Flow8MidiOut.send_program_change` is the only sender | 
| SR-02 | Unchanged. Program Change 16 on channel 16 raises SR-02. | M-06, M-09 |
| SR-03 | **Lifted** for FX preset select within the SR-01 exception above. | M-01, M-09 |
| SR-04 | Unchanged. Channel 16 stays closed, so FX mute (ch 16 CC 1) and tap tempo (ch 16 Note 0) are **not** opened; the UI shows them locked (`fxMute`, `tap`). | M-06, inspector tests |
| SR-07 | The allowlist grows from 97 to 133 entries: limiter (CC 8) and GEQ bands 1–9 (CC 11–19) on MAIN, MON 1, MON 2 (ch 8–10); FX engine parameter 1 (CC 1) and parameter 2 (CC 2) on ch 13–14; FX preset select (Program Change 1–16) on ch 13–14. Limiter and GEQ are not opened on the FX buses (chart: "NOT on FX1/2 BUS"). | M-02, M-08, `test_bus_mappings`, `test_bus_dsp_fx` |
| SR-08 / SR-11 | Unchanged. The mixer reports none of these values; the UI shows `--` / UNSYNCED until this app sends one, then COMMANDED. | `test_bus_dsp_fx` |

Not changed: gain (SR-05), +48 V (SR-06), presets and change plans (SR-12; the new parameters are not in `REVERSIBLE_PARAMETERS`, so they are not part of scenes or plans). The new parameters are undoable through the ledger. Over BLE they are refused (BLE writes faders only); in hybrid mode they go over USB MIDI.

Program Change numbering (C-01) for FX presets: the app sends data byte N for preset N, following the chart text "Program Change 0 & 17–127 = ignored". Whether the mixer counts from 0 or 1 is unverified; a wrong guess selects a neighbouring preset, never a reset (channel 16 is refused).
