# S1.1 Historical Evidence Corrections

Date: 2026-11-18. Stage S1.1. Corrects documents that state or imply hardware verification without raw evidence. **Original text was kept**: every corrected document received an "S1.1 EVIDENCE CORRECTION" block directly under its title, and nothing was deleted or rewritten. Source code and hardware were not touched; nothing was committed.

## 1. Rule applied (evidence ladder, `FLOW8_EVIDENCE_REGISTER.md` §1)

| Level | Evidence | Allowed wording |
|---|---|---|
| L1 | Described in a manufacturer document | DOCUMENTED |
| L2 | L1 plus implemented in the app | PROTOCOL SUPPORTED |
| L3 | Windows driver accepted the message (`midiOutShortMsg` returned 0) | "driver accepted" (still PROTOCOL SUPPORTED) |
| **L4** | **Physical effect observed and recorded** | **HARDWARE VERIFIED** |
| **L5** | **Mixer-originated bytes received** | read-back confirmed |

A claim is corrected when it uses "verified", "HARDWARE_TESTED", "passed on physical hardware", "OBSERVED" or similar and the repository holds no L4 or L5 evidence for it.

## 2. Evidence search (what raw evidence exists)

Searched the repository for raw logs, captures and recordings (file names `*raw*log*`, `*.jsonl`, `*capture*`, `*recording*`, `*.wav`, `*.flac`; `cueair_extracted/` excluded) and read the documents that cite them:

| File | Content | Level |
|---|---|---|
| `FLOW8_PHASE1_RAW_MIDI_LOG.md` (2026-11-09) | 13 outbound short messages (3 main fader, 3 ch 1 fader, 4 mute, 3 pan) with `MMSYSERR_NOERROR`, microsecond dispatch times; "Zero inbound MIDI packets" | L3 only |
| `FLOW8_PHASE2B_RAW_MIDI_LOG.md` (2026-11-09) | "Total Events Captured: 0" in all four listening stages | no L5 (negative result, **E17**) |
| `docs/audit/hw_stage1/d01_events.jsonl` and `d01_isolated_logger_*` (2026-11-18) | 0 inbound bytes; 0 outbound messages | no L5 (negative result, E07, E08) |
| Audio recordings, operator observation notes, panel photographs, relay evidence | **none found** | no L4 |

Result: **no L4 and no L5 evidence exists in the repository for any parameter.** Everything labelled "verified on hardware" rests on L3 or on nothing located. The project's own Phase C.1 audit (F-04) and Phase C.2 re-grading already reached this for the four initial parameters (`FLOW8_PHASE_C2_IMPLEMENTATION.md` lines 85–109); the documents below were not updated at that time.

## 3. Documents corrected

Errata blocks were inserted in these 18 documents (the original line numbers below refer to the file before insertion):

| # | Document | Claims | Evidence found | Corrected reading |
|---|---|---|---|---|
| 1 | `docs/testing/HARDWARE_VERIFICATION_MATRIX.md` | "CONNECTED & VERIFIED"; "VERIFIED ON REAL HARDWARE" (about 24 occurrences: faders, mute, pan, EQ, gain, low cut, compressor, phantom, sends); preset table "dispatched ... exact undo restored"; "OBSERVED" columns | L3 for ch 1 fader/pan/mute/EQ/low cut/comp/sends, main balance (E04, E05); none for gain, phantom, ch 2–7 | PROTOCOL SUPPORTED, driver accepted; presets: dispatched only (the mixer cannot be read back, so "restored" is unprovable); no OBSERVED |
| 2 | `docs/testing/FLOW8_HARDWARE_INTEGRATION_REPORT.md` | line 9 "VERIFIED ON REAL HARDWARE"; §2 "Real Physical Hardware Dispatch Verification" | L3 | driver accepted |
| 3 | `docs/testing/RELEASE_ACCEPTANCE_REPORT.md` | line 15 "live hardware verification"; §3; line 63 "Atomic Undo & Redo verified on physical hardware" | L3 at most; undo restores app-side values, effect on the mixer unobserved | driver accepted |
| 4 | `docs/testing/REGRESSION_REPORT.md` | lines 8, 47 "Physical Hardware Mutating Suite: PASSED (5)" | The mutating test is named `test_dispatch_is_api_acknowledgement_only` | driver accepted; the tests assert acknowledgement only |
| 5 | `docs/testing/UNDO_REDO_VERIFICATION.md` | line 35 "verified driver success, undone back to baseline" | L3 | driver accepted |
| 6 | `docs/stage2/STAGE_2_HARDWARE_VERIFICATION.md` | line 7 "Verified on Physical Hardware"; lines 27–30 "Physical Mixer Observed ... OBSERVED" | None: no inbound byte ever received (E07, E08, E17) | not observed; read-back UNCONFIRMED |
| 7 | `docs/stage2/STAGE_2_IMPLEMENTATION_REPORT.md` | lines 30, 47 "5 hardware tests ... passed on physical FLOW 8" | L3 | driver accepted |
| 8 | `FLOW8_ARCHITECTURE_ALIGNMENT.md` | lines 107, 118, 119, 123 HARDWARE_TESTED (118–119 are planned, unbuilt audio features; 123 telemetry that was never received) | none | not tested; planned features are not tested at all |
| 9 | `FLOW8_GATEWAY_API_SPEC.md` | lines 188, 194 example `verification_level: HARDWARE_TESTED` | no parameter holds that level since Phase C.2 | illustrative only |
| 10 | `FLOW8_HARDWARE_DOMAIN_MODEL.md` | lines 230–261 HARDWARE_TESTED for topology, ch 1 fader/mute/pan, Main, MIDI In telemetry ("unobserved"), audio capture ("verified via PnP and driver property store") | L3 for the four parameters; audio items are Windows enumeration (E09), no stream was captured | topology and audio: enumerated; parameters: driver accepted; telemetry: not received |
| 11 | `FLOW8_PHASE2A_IMPLEMENTATION.md` | lines 39–42 "Hardware-Verified"; line 108 "verified against the physical driver" | L3 | driver accepted |
| 12 | `FLOW8_PHASE2A_TEST_RESULTS.md` | group "Hardware-Verified (Physical FLOW 8)" H1–H8 | Endpoint lifecycle and driver acceptance | driver accepted |
| 13 | `FLOW8_PHASE_B_IMPLEMENTATION.md` | line 85 HARDWARE_TESTED for the initial four parameters | withdrawn in Phase C.2 | withdrawn |
| 14 | `FLOW8_PHASE_B_TEST_RESULTS.md` | line 32 same | withdrawn in Phase C.2 | withdrawn |
| 15 | `FLOW8_SPECIFICATION_GAP_ANALYSIS.md` | lines 69, 72, 83–85, 93 HARDWARE_TESTED (USB control, USB audio, 10-channel capture, sampling resolution, main layer) | L3 for control; audio: enumeration and registry only | enumerated / driver accepted |
| 16 | `FLOW8_USB_MIDI_PROTOCOL.md` | §6 "VERIFIED" column | chart reading | means "read from a chart" |
| 17 | `docs/audit/REAL_WORLD_HARDWARE_AUDIT.md` | "Audit Status: VERIFIED" for EQ, low cut, compressor, sends, phantom | dispatch log with `HW_Applied=None` (E05) | driver accepted |
| 18 | `docs/audit/REAL_WORLD_TEST_RESULTS.md` | "Physical Hardware Tests ... PASS", "Live 15-CC Hardware Sweep" | L3 | driver accepted |

## 4. Specific corrections of fact

| Original statement | Correct statement | Basis |
|---|---|---|
| "Atomic Undo & Redo verified on physical hardware" | Undo/redo replays commands through the same boundary; the effect on the mixer was never observed | no L4; mixer has no read-back |
| "restoring ... back to neutral flat baselines" (undo) | The app re-sends its recorded previous values; "neutral" is not read from the mixer | `_known_value` design; Stage 1 provenance rules |
| "5 hardware tests passed on physical FLOW 8" | 5 tests passed; the mutating test asserts only that the driver acknowledged | `tests/test_hardware_midi_out.py:156` |
| "Physical Mixer Observed ... OBSERVED" | Never observed | E07, E08, E17 |
| "HARDWARE_TESTED: USB MIDI In Inbound Telemetry" | Never received; the same line says "unobserved" | E17 |
| "Multi-channel capture streams verified" | Endpoints enumerated; no sample read | E09 |
| Planned Phase 3A items graded HARDWARE_TESTED | Not built | `FLOW8_ARCHITECTURE_ALIGNMENT.md` itself |

## 5. Not changed (and why)

- `FLOW8_PHASE_C1_AUDIT.md`, `FLOW8_PHASE_C2_*.md`, `FLOW8_PHASE_C_IMPLEMENTATION.md`, `FLOW8_PARAMETER_VERIFICATION_MATRIX.md`: these already contain the correction (they say "driver acceptance is not hardware verification").
- `PHASE_0_5_SUMMARY.md`, `FLOW8_HARDWARE_DOMAIN_MODEL.md`, `FLOW8_SPECIFICATION_GAP_ANALYSIS.md`, `FLOW8_ARCHITECTURE_ALIGNMENT.md`: already carry the S0 errata for MIDI channels; the S1.1 block was added above it where needed.
- Documents that assert the "USB TX: ON" premise without claiming verification (`BIDIRECTIONAL_STATE_MODEL.md`, `KNOWN_LIMITATIONS.md`, parts of `docs/stage2/`): registered as conflict C-02; not corrected here because they make no verification claim.
- Documents in `docs/product/`: written after the evidence rules; they state HARDWARE VERIFIED = 0.
- Source code comments and tests: not touched (stage rule). The 5 opt-in hardware tests still exist and are skipped by default.

## 6. Limits

- I identified claims by searching for phrases ("VERIFIED ON REAL HARDWARE", "Hardware-Verified", "HARDWARE VERIFIED", "Physical Mixer Observed", "HARDWARE_TESTED", "relay click", "Live Hardware Loopback", "verified on physical", "passed on physical") and by reading the documents that mention physical hardware tests. A claim phrased differently, in a document outside these searches, may remain.
- "No raw evidence found" means none exists in the repository I could search. The owner may hold evidence elsewhere (notes, recordings). If produced, it can raise a claim to L4 through the register without editing these blocks.
