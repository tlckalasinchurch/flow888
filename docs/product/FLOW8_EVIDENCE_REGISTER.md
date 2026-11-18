# FLOW 8 Evidence Register

Date: 2026-11-18. Stage S1, documentation only. Lists every piece of evidence used by the capability documents, what it proves, and what it does **not** prove. Nothing here was produced by sending MIDI or opening hardware in S1.

## 1. Evidence ladder

| Level | Meaning | Allowed label |
|---|---|---|
| L0 | No evidence | UNCONFIRMED |
| L1 | Described by a manufacturer document | DOCUMENTED |
| L2 | L1 plus implemented as a mapping in the app | PROTOCOL SUPPORTED |
| L3 | The Windows driver accepted a message (`midiOutShortMsg` returned 0) | still PROTOCOL SUPPORTED; shown as "driver accepted" only |
| L4 | **Physical effect observed and recorded** (operator protocol or measurement) | HARDWARE VERIFIED |
| L5 | **Mixer-originated bytes received** for a named control | read support confirmed (OBSERVED) |

Only L4 and L5 justify the words HARDWARE VERIFIED or "read". **No parameter has L4 or L5 evidence in the repository** (S1.1 search: only L3 dispatch logs and three negative inbound captures E07, E08, E17).

## 2. Register

| ID | Evidence | Type / source tier | Where | Proves | Does not prove | Reliability |
|---|---|---|---|---|---|---|
| **E01** | Behringer / Music Tribe *Quick Start Guide FLOW 8*, "V 1.0": MIDI Implementation (PDF p. 8, printed 14–15), Specifications (PDF p. 9, printed 16–17), controls | Manufacturer document (retailer-hosted copy, Thomann) | `docs/product/sources/behringer_flow8_quick_start_guide_V1.0_thomann-copy_505388.pdf`; SHA-256 `cfe98d5cfd298d77c7a919bb7ef87c8207ec4a9cc6a8227db2e1a79a298f5d29` | The documented channel/CC/PC mapping, ranges, channel exclusions, specification figures (L1) | That this unit's firmware matches V 1.0; value curves; EQ frequency meaning; any read-back | High; text extracted by machine, human re-check of the chart advised |
| E02 | Manuals+ mirror of the user guide | Third-party mirror | `docs/product/sources/manuals-plus_mirror_flow8_user_guide_BEFLOW8K2.pdf`; SHA-256 `f4469ea36e27c85ac52ada932a7f1092ea084326072f64ef85ba424ea36e3c7f` | Same chart exists in another copy | Anything independent of E01 (partly garbled text) | Low |
| E03 | App implementation: `command_boundary._build_phase_c_allowlist` (97 ids), `midi_constants.py`, `parameter_mapping.py` | Repository code | `flow8/` | What the app maps and sends | That the mapping is correct on hardware; curves | Fact about the code only |
| E04 | Phase 1 hardware proof: main fader, ch 1 fader, mute, pan sent at safe values, 0 inbound events | Repository log | `FLOW8_PHASE1_MIDI_TEST_RESULTS.md`, `FLOW8_PHASE1_RAW_MIDI_LOG.md` | The driver accepted these four messages (L3) | Any physical effect; the document itself labels inbound "BLOCKED / UNVERIFIED" | Medium (self-reported) |
| E05 | Real-world audit dispatch log: 15 commands (ch 1 fader, pan, mute, EQ ×4, low cut, compressor, sends ×4, main balance) | Repository log | `docs/audit/REAL_WORLD_HARDWARE_AUDIT.md` §3 | `Status=DRIVER_DISPATCHED`, `HW_Applied=None` (L3); 0 inbound events | Any physical effect | Medium |
| E06 | Phase C2 re-grading: `HARDWARE_TESTED` → `API_ACKNOWLEDGED` for 4 parameters; a WinMM return code "is not an application-level acknowledgement" | Repository decision | `FLOW8_PHASE_C2_IMPLEMENTATION.md` lines 85–109; `state_model.py` `VerificationLevel` | The project already treats driver acceptance as non-verification | — | High |
| **E07** | Stage 1 hardware capture of the application (90 s, USB TX reported ON by the operator, controls moved) | New this project, 2026-11-18 | `docs/audit/hw_stage1/d01_events.jsonl`, `d01_before.png`, `d01_after.png` | Ports opened; **0 raw bytes** received; 0 outbound messages | Why: not isolated (setting, cable, driver or behaviour) | High for the observation |
| **E08** | Isolated read-only logger (`flow8_midi_in_logger.py` through a wrapper), four 22.5 s windows, ch 1 fader, Main fader, ch 1 pan, ch 1 mute | New, 2026-11-18 | `docs/audit/hw_stage1/d01_isolated_logger_events.json`, `d01_isolated_logger_report.md` | 0 events, 0 bytes, 0 CC messages with `FLOW 8 MIDI IN` (device 0) selected | Absence of the feature (the operator's actions are not independently recorded) | High for the observation |
| E09 | Windows audio endpoint enumeration (PnP query, this session) | New, 2026-11-18 | Command output, not saved to a file | Endpoints `Mic 1`, `Mic 2`, `Mic/Line 3`, `Mic/Line 4`, `Line 5/6`, `Line 7/8`, `Main L/R`, `Multi In 1-10`, `USB Out 1/2`, `USB Out 3/4` (Recording mode) report status OK; Streaming-mode endpoints report Unknown | That audio can be captured, the signal point, sample rates | Medium (enumeration only) |
| E10 | USB audio capability report (2026-11-09): 10 in / 4 out, 44.1 and 48 kHz, ASIO driver | Repository document | `FLOW8_USB_AUDIO_CAPABILITIES.md` | Driver INF and Windows view at that date | Agreement with E01 ("8 x 2", 48 kHz) | Medium |
| E11 | Forum statements that the FLOW 8 does not transmit control or snapshot changes over USB; snapshot recall by Program Change works | Third party (unofficial forum), known only from search summaries (pages returned HTTP 403) | `https://behringer.world/viewtopic.php?t=68`, `?p=1515`, `?p=1533` | A consistent claim worth testing | Anything about this unit | Low |
| E12 | `abelroes/flow-8-midi` README: BLE state read, SysEx dumps, "real-time bidirectional sync ... not yet supported" | Third-party project | `https://github.com/abelroes/flow-8-midi` | A third party claims a full state read over Bluetooth | The mechanism; whether usable on Windows or over USB | Low–Medium |
| E13 | Behringer ideas board: user asks the mixer to "transmit midi commands to PC", status Planned | Manufacturer's platform, user post | `https://ideas.behringer.com/p/flow-8-midi` | Users consider USB transmit missing | Anything about the firmware | Low |
| E14 | Earlier claims "VERIFIED ON REAL HARDWARE" (parameters, presets, phantom "relay click") | Repository documents | `docs/testing/HARDWARE_VERIFICATION_MATRIX.md`, `docs/stage2/STAGE_2_HARDWARE_VERIFICATION.md`, `docs/audit/REAL_WORLD_HARDWARE_AUDIT.md` ("VERIFIED"), `FLOW8_PHASE2A_TEST_RESULTS.md` ("Hardware-Verified" group) | That the project believed the effect occurred | Raw evidence of any physical effect was **not located**; these labels equal E04/E05-level (L3) at best | Treated as L3 until raw evidence appears (conflict C-10) |
| **E17** | Phase 2B physical MIDI IN verification (2026-11-09): staged read-only logger, four windows (ch 1 fader, Main fader, ch 1 pan, ch 1 mute) | Repository log | `FLOW8_PHASE2B_MIDI_IN_RESULTS.md`, `FLOW8_PHASE2B_RAW_MIDI_LOG.md` ("Total Events Captured: 0") | **0 inbound events** nine days before E07 and E08: the same negative result on an earlier date | Absence of the feature (the pan stage notes no dedicated physical pan control on the hardware) | High for the observation |
| E15 | CueAir research | Excluded | `docs/reverse-engineering/*` | Nothing about FLOW 8 | — | **Not evidence** |
| E16 | Code reads this session: `midi_out.py` (only `send_cc`), `safety_dialogs.py` (gain and phantom gates), `service.py` (`set_gain`, `set_phantom`), `flow8_midi_harness.py` (`send_short_msg`) | Repository code | as named | Enforcement state in `FLOW8_SAFETY_POLICY.md` §3 | Runtime behaviour on hardware | Fact about the code only |

## 3. Claims in earlier documents that exceed the evidence

| Document | Claim | Re-grade |
|---|---|---|
| `HARDWARE_VERIFICATION_MATRIX.md` §2 | Fader, pan, mute, EQ, gain, low cut, compressor, phantom, sends "VERIFIED ON REAL HARDWARE" | L3 at best (E04, E05); gain, phantom and presets: raw evidence not located |
| same §3 | Seven presets "dispatched ... VERIFIED ON REAL HARDWARE", undo/redo "restored" | Driver acceptance only; the mixer cannot be read back, so "restored" cannot be shown |
| `REAL_WORLD_HARDWARE_AUDIT.md` §2 | EQ, low cut, compressor, sends "VERIFIED" | Status column mixes protocol and driver evidence; no physical effect recorded |
| `FLOW8_USB_MIDI_PROTOCOL.md` §6 | Everything "VERIFIED" | Means "read from a chart" |
| `BIDIRECTIONAL_STATE_MODEL.md`, `KNOWN_LIMITATIONS.md` | Inbound telemetry exists with "USB TX: ON" | No source in E01; contradicted by E07/E08 (not proven) |

These documents are not edited in S1. They are recorded as conflict C-10.

## 4. Evidence still missing (what would raise each class; none executed)

| To establish | Evidence needed |
|---|---|
| HARDWARE VERIFIED for a write parameter | A protocol where the operator watches the mixer panel or an audio capture shows the effect for a named parameter, logged with the command; phantom, gain and reset excluded |
| Read support for fader/pan/mute | Raw bytes from `FLOW 8 MIDI IN` while the owner moves a named control (L5) |
| Program Change numbering (C-01) | Official statement or controlled hardware test with the owner; never against reset |
| EQ frequencies and Q (C-04) | Official statement or measured frequency response |
| Fader taper and curves (C-05, C-12) | Official table or measurement |
| Ch 5/6 and 7/8 gain/low cut/compressor (C-06) | Official statement or physical test |
| USB audio configuration (C-07) | Captured stream (channel count, rate, signal point) |
