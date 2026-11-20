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
| E18 | Retailer product page, AT Prosound (Thai), read 2026-11-20 by a web-fetch agent. The page was truncated: the first part was read verbatim (mostly site navigation), the spec table, features and FAQ only through the agent's summary | **Secondary: retailer** | `https://www.atprosound.com/product/behringer-flow-8/` (not saved; retailer copyright) | That a retailer publishes these figures and claims (§5) | Any FLOW 8 capability (SR-09); the page is internally inconsistent on USB channels, FX preset count and Bluetooth range | Low |
| E19 | Retailer and catalogue text supplied by the owner in chat, 2026-11-20: an English spec table, a Thai spec summary, an English feature list, a Thai specification list | **Secondary: retailer / catalogue copy** | Not stored (third-party copy); key values in §5 | Same as E18 | Same as E18; the English spec table repeats manufacturer figures rounded (e.g. EQ ±15 dB) and adds figures E01 does not print | Low |
| E21 | Six screenshots of the official FLOW control app (iPad) supplied by the owner in chat, 2026-11-20: MAIN, MONITOR 1 and MONITOR 2 bus pages (LEVEL, BALANCE on MAIN only, LIMITER, 9-band EQ labelled 63Hz–16000Hz, ±15 dB), FX 1 page (DECAY %, INSTRUMENT / VOCAL, 16 named presets, MUTE), FX 2 page (FEEDBACK %, DULL / BRIGHT, 16 named presets, TAP FOR TEMPO, MUTE), STAGE view | Owner-supplied screenshots of the manufacturer's app | Not stored in the repository (copies were attached in chat; no decision to commit them) | What the FLOW app exposes and the preset names it shows | Any MIDI address or value mapping; that this app's commands have any effect; hardware state | Medium (app UI, not a specification) |
| E20 | Runtime observation of the running console, 2026-11-20: `/api/status` `meterStatus` = `running`, device `Multi In 1-10 (BEHRINGER FLOW 8 (Recording))`, mode `recording`; `/api/events` delivered `meters` frames with per-strip values that change between frames (about −74 to −112 dBFS, no test signal) | New, 2026-11-20 | Command output, not saved (`curl /api/status`, `curl /api/events`); stream code `flow8/audio_meter.py` | Device detected; a 10-channel input stream opened and is delivering frames (the meter closes the stream after 2 s without frames) | Which physical input each capture channel carries; the signal tap point; sample rate actually negotiated; any host-to-mixer (output) channel | Medium (observation of the app's own status, no reference signal) |

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

## 5. Additions 2026-11-20: retailer sources and manufacturer re-read

E18 and E19 are secondary sources. They are recorded so that their claims are not used by mistake; none of them is promoted to DOCUMENTED. Where they differ from E01, E01 stands.

E01 was re-read this session as text (`pdftotext -layout` of the stored copy, hash unchanged). E02 was searched the same way.

| Topic | E01 (manufacturer) | E18 / E19 (retailer) | Status |
|---|---|---|---|
| Channel EQ gain range | Low ±14.6 dB @ 20 Hz shelving; Low mid ±14.8 dB @ 300 Hz; High mid ±14.8 dB @ 1.5 kHz; High +14.1/−14.9 dB @ 20 kHz shelving (printed p. 16–17) | ±15 dB for every band, same frequencies | Retailer rounds. Frequencies agree; their meaning and Q are still unstated (C-04) |
| USB audio channels | "Channels 8 x 2", "24-bit / 48 kHz" | "10 out / 2 in" (spec table); the E18 page also reportedly says 10 in / 2 out and 10 in / 4 out elsewhere | Retailer contradicts E01 and itself. C-07 |
| Bluetooth range | "30 m (without interference)" | "12 m"; E18 also reportedly says about 20 m | Retailer differs. No app feature depends on it |
| Line input gain range | Gain range −20 to +60 dB is printed for the mic inputs | Also listed for the line inputs 5L / 7L | Not adopted. C-06 unchanged |
| FX presets | Chart: tap tempo on FX 2 presets 1–12 | "16 presets" per engine (one Thai list says 16 in total) | Unchanged. C-09 |
| EZ-Gain | **Not mentioned.** E01 and E02 contain no "EZ" text | E18 reportedly: EZ-Gain sets gain automatically and, when enabled, turns on +48 V by itself when it detects a condenser mic on ch 1 or 2 | **UNCONFIRMED** (C-13) |
| +48 V control path | "Phantom power can be activated in the control app" (printed p. 10–11) | — | DOCUMENTED: +48 V can change outside this application |
| Footswitch | Mode "FX" (default): switch 1 = FX mute, switch 2 = tap tempo. Mode "SNAPSHOT": switch 1 = snapshot up (next), switch 2 = snapshot down (previous) (printed p. 12–13) | Same functions | DOCUMENTED: a snapshot can change on the mixer without this application |

E20 is a runtime observation, not a document. What it does and does not establish for USB audio is set out in C-07 (`FLOW8_UNRESOLVED_CONFLICTS.md`).
