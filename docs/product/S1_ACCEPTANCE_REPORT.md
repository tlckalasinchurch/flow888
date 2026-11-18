# S1 Acceptance Report: Capability Architecture

Date: 2026-11-18. Stage S1 was analysis and documentation only. This report states, criterion by criterion, what is met, partly met and not met, with the checks that were actually run.

Labels: **VERIFIED** = command output or file read this session. **ASSUMPTION** = believed, not checked. **BLOCKER** = stops progress. **NEXT** = one action.

## 1. Deliverables

| # | Document | State |
|---|---|---|
| 1 | `docs/product/FLOW8_CAPABILITY_MATRIX.md` | Written |
| 2 | `docs/product/FLOW8_PARAMETER_MAPPING.md` | Generated, 167 rows, 18 columns (all fields requested) |
| 3 | `docs/product/FLOW8_SAFETY_POLICY.md` | Written, with enforcement state read from the code |
| 4 | `docs/product/FLOW8_EVIDENCE_REGISTER.md` | Written, 16 evidence items, evidence ladder L0–L5 |
| 5 | `docs/product/FLOW8_UNRESOLVED_CONFLICTS.md` | Written, 12 conflicts (all seven you listed plus five more) |
| 6 | `docs/product/S1_ACCEPTANCE_REPORT.md` | This file |

## 2. Checks run (VERIFIED)

A read-only script (`check_s1.py`, in the session scratchpad, not in the repository) parsed the generated mapping and the registers:

| Check | Result |
|---|---|
| Rows with the wrong number of columns | 0 |
| Empty cells | 0 |
| Rows without source or status | 0 |
| Every id of the code's `ACTIVE_ALLOWLIST` (97) present in the mapping | yes, none missing |
| Rows with status HARDWARE VERIFIED | **0** |
| "Hardware verification" cells claiming verified | 0 |
| Rows where a UI control is offered although the status is not PROTOCOL SUPPORTED | 0 |
| Rows at safety level DISABLED or FORBIDDEN that allow a UI | 0 |
| Gain and phantom rows at PROTOCOL SUPPORTED that are not GATED | 0 |
| Conflict ids or evidence ids referenced but not defined | 0 |
| Status counts | PROTOCOL SUPPORTED 97, DOCUMENTED 55, UNSUPPORTED 8, UNCONFIRMED 7 |

`git diff --stat -- flow8 tests` is unchanged from before S1 (the same five files from the earlier approved Stage 1 work: 151 insertions, 12 deletions). `git log -1` is still `456fd5a`; nothing was committed. No MIDI port was opened and no message was sent in S1; the only runtime actions were importing the allowlist and parsing text files.

## 3. Acceptance criteria

| # | Criterion | Result | Basis |
|---|---|---|---|
| 1 | Every parameter has a status and a source | **MET** | 167 of 167 rows; check above |
| 2 | No parameter that the UI can show as hardware verified without evidence | **MET for the current UI, with a documentation caveat** | `flow8/ui/` shows "HW APPLIED: UNKNOWN" and "NOT VERIFIED"; no code assigns `HARDWARE_TESTED` to a parameter (search of `flow8/`). Earlier documents still say "VERIFIED ON REAL HARDWARE" (conflict C-10, not edited) |
| 3 | No Reset command that can be sent | **MET for the application; NOT guaranteed for the harness** | The application's only outbound path is `send_cc`, which builds Control Change messages only and rejects channels 13–16. `flow8_midi_harness.py` can send arbitrary bytes if someone edits or calls it (gap G-05). Reset is FORBIDDEN in policy and in the mapping |
| 4 | No unconfirmed mapping in use | **NOT MET (cannot be met in a documentation-only stage)** | The app already sends 97 PROTOCOL SUPPORTED mappings that have no hardware verification, and it derives dB and Hz readouts from unconfirmed curves (fader unity at raw 101, linear gain/low cut, EQ labels). The documents now classify all of them honestly. Actions that would reduce this (labels, gating) are listed as gaps G-01…G-06 for a later, separately approved stage. Rows that are UNCONFIRMED (ch 5/6 and 7/8 gain/low cut/compressor, USB MIDI telemetry) are **not** used by the app |
| 5 | The documents contain no contradiction without a conflict entry | **PARTLY MET** | Contradictions known to me are registered (C-01 … C-12). Older documents outside `docs/product/` still contain over-claims and the "USB TX: ON" premise; they are registered as C-10 and C-02 but not corrected (S1 limited edits to `docs/product/`). I did not read every document in the repository, so unknown contradictions may remain |
| 6 | Clear statement of what can be controlled, read and not done | **MET** | `FLOW8_CAPABILITY_MATRIX.md` §3: controllable (implemented), documented-but-not-implemented, forbidden, readable (**nothing confirmed**), not possible |

## 4. Safety rules requested

| Rule | State |
|---|---|
| Program Change sender disabled | No Program Change sender exists in `flow8/` (VERIFIED by reading `midi_out.py` and searching). "Disabled" is by absence of code, with no explicit flag (gap G-03) |
| Program Change reset forbidden | Policy SR-02; mapping row FORBIDDEN |
| FX Program Change disabled | Policy SR-03; mapping rows DISABLED |
| Preamp gain gated | Gated in the UI only. **Not gated at the service and boundary layers** (gap G-01) |
| Phantom gated, no automation | Dialog and single-use token in the UI; excluded from presets, scenes, undo. **Not gated at the service layer** (gap G-02) |
| No UI for a parameter without enough evidence | No control exists for UNCONFIRMED, UNSUPPORTED, DISABLED, FORBIDDEN rows. Unsourced numeric labels exist (EQ frequencies, dB readouts) and are listed for S2 |
| No claim that the app reads real values | The app decodes incoming messages but none ever arrived; the documents state read-back is UNCONFIRMED |
| CueAir not used as evidence | Observed; CueAir is listed as excluded (E15) |

## 5. Findings worth your attention

1. **HARDWARE VERIFIED is zero.** Every earlier "VERIFIED ON REAL HARDWARE" rests on driver acceptance or on raw evidence I could not find. This is the largest change in how the project describes itself.
2. **Gain and phantom are gated only by the UI.** Any other caller of `Flow8Service.set_gain()` or `set_phantom()` bypasses the gates (G-01, G-02). Nothing today calls them outside the UI, but the policy cannot yet be called enforced.
3. **The harness can send any byte**, including a Program Change 16, if misused (G-05).
4. The 13 existing presets are structurally safe today (EQ, low cut, compressor only) but nothing forbids a future preset from carrying other fields (S2).

## 6. Limits of this stage

- No hardware evidence was produced; USB MIDI telemetry remains BLOCKED (E07, E08).
- The manufacturer chart was read by machine extraction; a human check of PDF page 8 is advised before S2.
- Forum statements were known only through search summaries.
- I read the code paths named in the safety policy, not the whole code base.

## 7. Decision requested

I have stopped. S2 (Preserve Levels) is not started. Items that need your decision before or during S2: whether to approve enforcement of G-01 to G-06, whether to correct the over-claiming earlier documents (C-10), and whether the hardware investigation of C-02 resumes.

## S1.2 follow-up (2026-11-18)

Criterion 3 (no reset can be sent) now holds for the application **and** the repository tools: `tools/flow8_midi_harness.py` validates every message and sends nothing by default. Criterion 4 (no unconfirmed mapping in use) remains partly open: the app still sends the 93 PROTOCOL SUPPORTED, not hardware verified pairs and derives some readouts from unconfirmed curves; gain is now blocked and the unsourced EQ frequency labels are gone. Details: `S1_2_IMPLEMENTATION_REPORT.md`.
