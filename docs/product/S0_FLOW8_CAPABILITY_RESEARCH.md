# S0: FLOW 8 Capability Research (Documentation Only)

Date: 2026-11-18. Scope: Stage S0 only. No source code changed. No MIDI sent. No hardware touched. No CueAir value is used as evidence in this document.

Labels: **FACT** = stated in a cited source. **THIRD-PARTY** = stated by a non-official source. **ASSUMPTION** = my inference, not stated by any source. **UNCONFIRMED** = no source found. Confidence: High / Medium / Low.

## 1. Sources

> Update 2026-11-18: the source register was split into manufacturer document / hosting copy / mirror and third-party sources, with SHA-256 values, page numbers and numbering semantics, in `S0_MIDI_MAPPING_ERRATA.md` §1–2. Source A below is the manufacturer's Quick Start Guide V 1.0 as hosted by a retailer (hosting copy, SHA-256 unchanged). The correction of D-S0-01/D-S0-02 is recorded there; this document's text is otherwise unchanged.

| ID | Source | Type | How obtained | Notes |
|---|---|---|---|---|
| **A** | Behringer *FLOW 8 Quick Start Guide* (Music Tribe), PDF, copy hosted by a retailer: `https://images.thomann.de/pics/atg/atgdata/document/manual/505388.pdf`. SHA-256 `cfe98d5cfd298d77c7a919bb7ef87c8207ec4a9cc6a8227db2e1a79a298f5d29` | Official manufacturer document, retailer-hosted copy | Downloaded with curl, text extracted with `pdftotext -raw` this session | MIDI Implementation = PDF page 8 (printed pages 14–15). Specifications = PDF page 9 (printed pages 16–17). Controls description = earlier pages. The chart columns are laid out in tables; I read them in raw order and cross-checked against the layout-mode extraction |
| **B** | Manuals+ mirror of the FLOW 8 user guide, `https://www.adorama.com/col/productManuals/BEFLOW8K2.pdf`, SHA-256 `f4469ea36e27c85ac52ada932a7f1092ea084326072f64ef85ba424ea36e3c7f` | Third-party mirror of the same guide | Downloaded, partly garbled text | Used only to confirm A's chart exists in the same form |
| **C** | Unofficial Behringer Forums threads, found via search: `https://behringer.world/viewtopic.php?t=68`, `?p=1515`, `?p=1533`, `?t=2058` | THIRD-PARTY forum posts | Search summaries only. The pages returned HTTP 403 to my fetch tool, so I did **not** read the posts myself | Statements below are marked "as reported by search summary" |
| **D** | `https://github.com/abelroes/flow-8-midi` README | THIRD-PARTY open-source project | Fetched and read | States BLE state read and SysEx dumps; no byte-level detail in the README |
| **E** | `https://ideas.behringer.com/p/flow-8-midi` (Behringer ideas board) | Manufacturer's feedback board, user post, status "Planned" | Fetched and read | A user request, no staff reply visible |

Not found: a separate official "MIDI Implementation" PDF, a full-length FLOW 8 user manual with FX preset names, any official statement about a USB TX menu setting.

## 2. Verified facts from the official chart (source A)

### 2.1 MIDI channel assignment (FACT, High)

| MIDI channel (1-based) | Target |
|---|---|
| 1, 2, 3, 4 | Input channels 1, 2, 3, 4 |
| 5 | Input 5/6 |
| 6 | Input 7/8 |
| 7 | Input USB/BT |
| 8 | MAIN bus |
| 9 | MON 1 bus |
| 10 | MON 2 bus |
| 11 | FX 1 bus |
| 12 | FX 2 bus |
| **13** | **FX 1 slot (effect engine)** |
| **14** | **FX 2 slot (effect engine)** |
| 15 | "not used" |
| 16 | Global: snapshots, FX common control |

### 2.2 Parameters (FACT unless marked)

| Parameter | Target | MIDI | Range as stated | Evidence | Confidence |
|---|---|---|---|---|---|
| Channel level (to MAIN) | Input ch 1–7 | CC 7 | value 0 = OFF; 1–127 = −70 dB … +10 dB; curve between not stated | A p.8 | High (range), curve UNCONFIRMED |
| Channel balance | Input ch 1–7 | CC 10 | 0–127 = 1.0 left … 1.0 right; 64 = centre | A p.8 | High |
| Mute | Input ch | CC 5 | 0 = off; 1–127 = mute | A p.8 | High |
| **Solo** | Input ch | **CC 6** | 0 = off; 1–127 = solo | A p.8 | High |
| EQ Low / Low-mid / Hi-mid / Hi | Input ch | CC 1 / 2 / 3 / 4 | 0–127 = −15 … +15 dB; 64 = 0.0 dB; curve between not stated | A p.8 | High (range), curve UNCONFIRMED |
| Gain | Input ch "NOT on Ch. USB/BT" | CC 8 | 0–127 = −20 … +60 dB; curve not stated | A p.8, spec p.9 lists gain range −20 to +60 dB | High (range) |
| Low cut | Input ch "NOT on Ch. USB/BT" | CC 9 | 0–127 = 20 Hz … 600 Hz, "continuous control"; scale (linear or log) not stated | A p.8 | High (range), scale UNCONFIRMED |
| Compressor | Input ch "NOT on Ch. USB/BT" | CC 11 | 0–100 = 0 … 100 %; 101–127 identical to 100 % | A p.8 | High |
| +48 V | **Only ch 1 and 2** | CC 12 | 0 = off; 1–127 = on | A p.8 | High |
| Channel status | Input ch | CC 13 | 0 = hidden; 1–127 = active | A p.8 | High |
| Send to MON 1 / MON 2 / FX 1 / FX 2 | Input ch | CC 14 / 15 / 16 / 17 | 0 = OFF; 1–127 = −70 … +10 dB | A p.8 | High |
| Bus level | Main, Mon 1, Mon 2, FX 1 bus, FX 2 bus | CC 7 on ch 8–12 | 0 = OFF; 1–127 = −70 … +10 dB | A p.8 | High |
| Bus balance | **Main only** | CC 10 on ch 8 | 64 = centre | A p.8 | High |
| Bus limiter | Main, Mon 1, Mon 2 (not FX buses) | CC 8 | 0–127 = −30 … 0 dB | A p.8 | High |
| 9-band bus EQ | Main, Mon 1, Mon 2 (not FX buses) | CC 11–19 = 62 Hz, 125 Hz, 250 Hz, 500 Hz, 1 kHz, 2 kHz, 4 kHz, 8 kHz, 16 kHz | 0–127 = −15 … +15 dB; 64 = 0 dB | A p.8 | High |
| FX effect preset select | FX 1 on ch **13**, FX 2 on ch **14** | Program Change 1–16 | PC 0 and 17–127 ignored | A p.8 | High |
| FX parameter 1 | FX slot ch 13 / 14 | CC 1 | 0–100 = 0 … 100 %; 101–127 = 100 % | A p.8 | High |
| FX parameter 2 | FX slot ch 13 / 14 | CC 2 | switch: 0 = "Value A"; 1–127 = "Value B" | A p.8 | High |
| Snapshot load | Global, ch 16 | Program Change 1–16 | PC 0 and 17–127 ignored; "Presets = 1–15; **RESET = Prog. Chg. #16**; Loading #16 = RESET!" | A p.8 | High |
| FX mute (both FX sends) | Global ch 16 | CC 1 | 0 = off; 1–127 = mute | A p.8 | High |
| Tap tempo | Global ch 16 | Note On, note 0 (C −1), velocity 1–127 (velocity 0 ignored) | 50–250 BPM; only delay/echo effects; currently FX 2 presets 1–12 | A p.8 notes | High |

### 2.3 Hardware and audio facts (source A, specifications page)

| Item | Statement | Confidence |
|---|---|---|
| Channel EQ | Low ±14.6 dB @ 20 Hz, shelving; Low mid ±14.8 dB @ 300 Hz; High mid ±14.8 dB @ 1.5 kHz; High +14.1/−14.9 dB @ 20 kHz, shelving | High that these are the stated figures. **What the frequency means is not defined** (corner, centre or measurement point) → UNCONFIRMED. Q is not given anywhere in the sources (UNCONFIRMED) |
| Mic input gain range | −20 dB to +60 dB | High |
| Phantom power | +48 V switchable; MIDI chart: only ch 1 and 2 | High |
| USB audio | "Bit depth 24-bit / 48 kHz", "Channels 8 x 2" | High for the printed text; its relation to the 10-in/4-out mode seen in Windows is UNCONFIRMED |
| Controls | USB AUDIO jack: "audio streaming, firmware updates and MIDI control" | High |
| Compressor | The sources give only a single 0–100 % control; threshold, ratio, attack, release, knee are **not documented** | High that none are documented |
| FX engines | Two FX engines; FX1/FX2 buttons select engine for "patch selection and parameter adjustment"; the on-mixer screen lists the effect names | High |

## 3. Questions asked by the owner

### 3.1 EQ band frequencies and ranges
- Range ±15 dB, 64 = 0 dB (FACT, A). The dB-vs-CC curve between 0, 64 and 127 is UNCONFIRMED; the app assumes two linear halves (ASSUMPTION).
- Frequencies: A states 20 Hz shelf, 300 Hz, 1.5 kHz, 20 kHz shelf in the specification table (FACT as printed; meaning UNCONFIRMED). **The app's labels 80 Hz / 400 Hz / 2.5 kHz / 10 kHz have no source in A, B, C, D or E.** I found their origin only in `channel_detail.py` (`EQ_BANDS`); no document in the repository cites them.
- Q: UNCONFIRMED.

### 3.2 Compressor
Single control 0–100 %, CC 11. Everything else UNCONFIRMED (not published). The chart's "NOT on Ch. USB/BT" restricts only the USB/BT channel; whether channels 5/6 and 7/8 respond is UNCONFIRMED (see §4, D-S0-03).

### 3.3 Low cut
CC 9, 0–127 = 20 Hz … 600 Hz, continuous (FACT). Slope/behaviour and scale: UNCONFIRMED. The app maps linearly (ASSUMPTION).

### 3.4 FX slots, types, MIDI control
- Two engines. Preset selection by Program Change 1–16 on **ch 13 (FX 1) and ch 14 (FX 2)**; FX parameter 1 (CC 1, percent) and parameter 2 (CC 2, A/B switch) on the same channels (FACT, A).
- Preset names/types: **UNCONFIRMED.** A does not list them; they are on the mixer screen and in the control app. A third-party review reports 12 reverbs on FX 1, 12 delays on FX 2 and four flanger/chorus effects on each (THIRD-PARTY, via search summary, not read by me). FX 2 presets 1–12 support tap tempo (FACT, A).
- Meaning of parameters 1 and 2 per preset: UNCONFIRMED.
- The chart lists PC 1–16, but the snapshot note says preset 16 of the **snapshot** list is RESET; whether FX preset 16 exists as a normal effect is UNCONFIRMED.

### 3.5 Control Change / Program Change mapping
See §2.1–2.2. The app's `midi_constants.py` agrees with the chart for channels 1–12 and CC numbers 1–12, 14–17 (checked by reading both). Differences are in §4.

### 3.6 What can be read back from the hardware
- **Official documentation (A):** the chart is a *receive* chart. It contains no statement that the mixer transmits parameter changes, and the guide contains no "USB TX" menu setting (searched for "TX" and "transmit": no hits).
- **THIRD-PARTY (C, via search summaries, not read by me):** a user reports that Behringer support said the FLOW 8 does not transmit MIDI for control-value or snapshot changes and that the only outbound MIDI is a dump started from the snapshots menu; other users agree.
- **THIRD-PARTY (D):** the open-source controller states that over Bluetooth it "reads the mixer's full state (all parameters, channel names, snapshot names)" and "periodically syncs state from the mixer via SysEx dumps", and that real-time reflection of physical fader moves is "not yet supported". Byte-level format is not in the README.
- **E:** a user asks Behringer to "transmit midi commands to PC"; status "Planned" (no date).
- **Conclusion (ASSUMPTION, Medium):** USB MIDI IN from the FLOW 8 probably carries no live control changes; this fits our 0-byte captures. It is not proven: we have no official statement, and the mixer menus were not inspected by me.
- Read-back of individual parameters over USB: UNCONFIRMED (no source describes it). State dump over Bluetooth: THIRD-PARTY only, Low–Medium.

### 3.7 Limits that force CueAir workflows to be reduced
(Each is FACT from A unless stated.)
1. EQ: four fixed bands with gain only; no frequency, Q or type control over MIDI.
2. Compressor: one percent control; no threshold, ratio, attack, release or gate. (No gate or expander is documented at all.)
3. Low cut: one frequency control; no filter type or slope.
4. Gain only via CC 8 and see §4 for which channels.
5. Phantom: channels 1 and 2 only.
6. FX: preset selection plus two parameters (one percent, one A/B); preset content not editable over MIDI.
7. Snapshots are stored on the mixer (15 + reset), selected by number; their contents cannot be read or edited over MIDI per the sources. Program Change 16 resets the mixer.
8. Probably no live read-back over USB (ASSUMPTION, Medium); no meter data in the chart.
9. Level control taper between −70 and +10 dB is not specified.

## 4. Discrepancies between official documentation and the repository

| ID | Repository says | Official chart (A) says | Severity | Confidence in the discrepancy |
|---|---|---|---|---|
| **D-S0-01** | FX 1 on MIDI ch 14, FX 2 on ch 15, ch 13 "Reserved" (`docs/hardware/FLOW8_PROTOCOL_SPECIFICATION.md` lines 39–41; `HARDWARE_VERIFICATION_MATRIX.md`) | FX 1 = ch **13**, FX 2 = ch **14**, ch 15 "not used" | **High (safety):** a Program Change meant for FX 1 would change the FX 2 engine, and one on ch 15 is ignored. Not yet implemented in code (no Program Change sender found in `midi_out.py` or `command_boundary.py`), so nothing wrong has been sent | High |
| **D-S0-02** | Snapshot recall "Program Change 1..16" | PC 1–15 recall snapshots; **PC 16 = RESET of the mixer** | **High (safety):** a generic 1–16 range would allow a reset | High |
| **D-S0-03** | Gain, low cut and compressor on channels 1–4 only; ch 5/6 compressor marked UNSUPPORTED | Chart restricts only "Ch. USB/BT"; implies ch 1–6 (inputs 1–4, 5/6, 7/8) | Medium (missing capability, no harm) | Medium: the chart is explicit about USB/BT but does not say the line channels have the hardware; physical confirmation needed |
| **D-S0-04** | EQ band labels 80 Hz / 400 Hz / 2.5 kHz / 10 kHz (UI) | Specification lists 20 Hz shelf, 300 Hz, 1.5 kHz, 20 kHz shelf | Medium (UI shows unsourced numbers) | High that the UI numbers are unsourced; meaning of the official figures UNCONFIRMED |
| **D-S0-05** | Continuous FX parameters are UNSUPPORTED; "no CC for FX parameters" (`KNOWN_LIMITATIONS.md` §1.3) | FX parameter 1 (CC 1, percent) and parameter 2 (CC 2, A/B) exist | Medium (capability under-reported) | High |
| **D-S0-06** | Inbound telemetry exists "when SETUP → MIDI → USB TX: ON" (`BIDIRECTIONAL_STATE_MODEL.md`, `KNOWN_LIMITATIONS.md`) | No such menu in A; chart is receive-only; third-party reports say the mixer does not transmit | **High (premise of D-01)** | Medium: absence in A is certain; absence of the feature is not proven |
| **D-S0-07** | Solo (CC 6) "defined, not in boundary, unverified" | CC 6 documented for inputs | Low | High |
| **D-S0-08** | Fader unity at raw 101 (`parameter_mapping.py`: −70…0 dB over 1–101, 0…+10 over 101–127) | Only "1–127 = −70 … +10 dB"; a third-party formula (via search summary) is linear in dB over 1–127, which puts 0 dB near 111 | Medium (dB readouts may be several dB off; raw values are what is sent) | Low–Medium: the official chart does not give the taper |
| **D-S0-09** | USB audio sample rates 44.1 and 48 kHz; 10-in/4-out recording mode | A specification says "24-bit / 48 kHz", "Channels 8 x 2" | Low (S9 only) | Medium |
| **D-S0-10** | Channel status (CC 13), bus limiter (Main/Mon CC 8), 9-band EQ listed in some documents but with weaker classification | All documented in A | Low | High |

## 5. Values that remain unconfirmed

1. Meaning of the specification frequencies (corner, centre, measurement point) and any Q for the four EQ bands.
2. CC-to-dB and CC-to-Hz curves (fader, gain, EQ, low cut, send).
3. Compressor internals (threshold, ratio, attack, release) and what 0–100 % changes.
4. Whether channels 5/6 and 7/8 respond to CC 8, 9 and 11.
5. FX preset names and types for both engines, what parameters 1 and 2 do per preset, whether FX preset 16 exists.
6. Whether the mixer transmits any live MIDI over USB and under which setting; format of any dump; whether Bluetooth state read is usable from Windows.
7. Whether PC 16 on channel 16 resets only mixer settings or also names/snapshots (not stated).
8. Actual USB audio mode and sample rates versus the printed specification.

## 6. Impact on S1 (capability table)

1. The table must record, per parameter: official range, curve status (UNCONFIRMED where unknown), channels per the chart and channels the app permits, readable (no, per A; UNCONFIRMED), verification class, source ID.
2. Mark `gain` as *gated*; keep the range and note the −20…+60 dB figure from A.
3. Add `snapshot_recall(16)` as **forbidden**; allowed PC range 1–15.
4. Record FX slot channels as 13/14 and keep FX program change **disabled** until D-S0-01 is corrected and a hardware test exists.
5. Record EQ band frequencies as UNCONFIRMED and require the UI not to print numeric frequencies, or to print only the official specification figures with the label "from the Behringer specification; behaviour unconfirmed".
6. Add `solo` (CC 6), `channel_status` (CC 13), bus limiter and bus EQ as documented-not-implemented, class PS.
7. Mark `readable_from_hardware = unconfirmed` for every parameter; `observed` provenance stays possible only if telemetry is later shown.
8. A control whose class is UN or UNCONFIRMED for range cannot be exposed as a functional hardware control.

## 7. Impact on S2 (Preserve Levels)

Official facts support a structural rule: a preset may write only EQ (CC 1–4), low cut (CC 9) and compressor (CC 11). Never CC 7 (level), CC 10 (balance), CC 8 (gain), CC 12 (+48 V), CC 14–17 (sends). The statement shown to the user should read: "Fader, pan, gain, sends and +48 V are never changed." Because the mixer cannot be read back, the wording must not say "levels are preserved on the mixer"; it says "this app does not send level commands". Applicability: low cut and compressor on channels 5/6 and 7/8 stay disabled until D-S0-03 is settled by a documented or hardware-observed result.

## 8. Proposed acceptance criteria for the next stages

**S0 sign-off (this stage):** the owner reads §4 and §5 and accepts or corrects them; the PDF pages named in §1 are checked by a human against §2.2 (the tables were machine-extracted); source A is retained locally for reference (not committed).

**S1:** (a) every allowlisted parameter and every documented-but-unimplemented parameter has an entry with source ID, range, curve status, channels, readable flag, class; (b) a test fails if a control is offered for an entry with class UN or with `range_confirmed = false` and no "unconfirmed" label; (c) a test asserts snapshot Program Change 16 cannot be constructed; (d) a test asserts FX Program Change is not sendable while disabled; (e) UI text for EQ bands matches the table (no unsourced frequency); (f) gain and +48 V keep their gates; (g) full regression results reported by category.

**S2:** (a) a test applies every preset to every allowed channel and asserts the only commands are CC 1–4, 9, 11 on permitted channels; (b) the dialog has no toggle and shows the fixed statement; (c) a test proves a preset object cannot carry level, balance, gain, phantom or send fields; (d) wording never says the mixer's levels were verified or preserved.

**Additional stage proposed before S8:** correct the repository's FX channel and snapshot documentation (D-S0-01, D-S0-02), as a documentation-only change, once you approve.

## 9. What S0 did not do

No hardware test, no MIDI sent, no code read beyond the lines named, no verification that the chart matches this unit's firmware (the guide's revision/date is not stated in the extracted text). The forum statements in §3.6 come from search summaries; the pages themselves returned HTTP 403.
