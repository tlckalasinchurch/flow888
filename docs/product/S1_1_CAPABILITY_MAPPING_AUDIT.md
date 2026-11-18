# S1.1 Capability Mapping Audit

Date: 2026-11-18. Stage S1.1, documentation only. No source changed, no MIDI sent, no hardware opened. The only runtime actions were importing the allowlist and calling `Flow8MidiOut.send_cc` on a port object that was **never opened** (it can only validate and then raise "not connected").

## 1. Rule applied

The application allowlist (`ACTIVE_ALLOWLIST`) records what the **application can send**. It is an implementation fact and is **never evidence** that the FLOW 8 supports a parameter, that a mapping is correct on hardware, or that a value can be read back. Each parameter is therefore classified on five separate dimensions:

| Dimension | Question | Evidence that may be used |
|---|---|---|
| Documented MIDI mapping | Does a manufacturer document list this channel/CC/range? | E01 (Quick Start Guide V 1.0, PDF p. 8) only |
| Application allowlisted | Can the app send it? | Code (E03) |
| Protocol supported | Documented **and** implemented | Both of the above; says nothing about hardware |
| Hardware verified | Physical effect observed and recorded | Operator protocol or measurement (none exists) |
| Read-back supported | Mixer-originated bytes received for this control | Raw MIDI IN capture (none exists) |

## 2. Method

1. The manufacturer chart was transcribed again, independently of the code, into a table of (MIDI channel, CC) with its documented meaning and exclusions ("NOT on Ch. USB/BT", "ONLY on Ch. 1 + 2", "ONLY on MAIN BUS", "NOT on FX1/2 BUS").
2. Each of the 97 allowlist entries was compared with that table for channel, CC and meaning.
3. The low-level validator `Flow8MidiOut.send_cc` was exercised for all 16 channels × 128 CC numbers on an unopened object to list exactly which (channel, CC) pairs it accepts.
4. The inbound handler `Flow8Service._on_midi_in_event` was read to list which parameters the app can decode if bytes ever arrive.

## 3. Results

| Measure | Result |
|---|---|
| Allowlist entries compared | 97 |
| Entries whose channel, CC and meaning match a chart row | 97 of 97 |
| Entries with no chart row or a different meaning | 0 |
| Documented (channel, CC) pairs in the chart table (inputs and buses only) | 147 |
| Documented pairs the app does **not** allowlist | 50 |
| Pairs `send_cc` accepts | 134 (allowlist: 97; extra: 37) |
| Allowlisted pairs that `send_cc` rejects | 0 |
| Parameters the app can decode if bytes ever arrive | 29 (decoder exists; **no evidence any arrives**) |
| Hardware verified | **0** |
| Read-back supported (evidence) | **0** |

The 97 allowlist entries are consistent with the manufacturer chart (a consistency check of the code against the document, not hardware evidence). The allowlist is also checked at import time by `_validate_allowlist` (channel scope, CC scope, uniqueness of the (channel, CC) pair); that is a code consistency check, not evidence either.

### 3.1 Documented but not allowlisted

| Documented function | Pairs |
|---|---|
| 9-BAND EQ band 1 | 3 |
| 9-BAND EQ band 2 | 3 |
| 9-BAND EQ band 3 | 3 |
| 9-BAND EQ band 4 | 3 |
| 9-BAND EQ band 5 | 3 |
| 9-BAND EQ band 6 | 3 |
| 9-BAND EQ band 7 | 3 |
| 9-BAND EQ band 8 | 3 |
| 9-BAND EQ band 9 | 3 |
| BUS LIMITER | 3 |
| CHANNEL STATUS | 7 |
| COMP | 2 |
| GAIN | 2 |
| LOW CUT | 2 |
| SOLO | 7 |

Extra pairs accepted by `send_cc` but **not** allowlisted (all documented in the chart, so not undocumented): (1,6), (2,6), (3,6), (4,6), (5,6), (6,6) ... 37 pairs = solo on channels 1-7 (7) plus bus limiter and 9-band EQ on channels 8, 9, 10 (30). These cannot be reached through the command boundary but can through `Flow8MidiOut.send_cc` directly (gap G-04).

### 3.2 Findings

| ID | Finding | Evidence | Effect on status |
|---|---|---|---|
| B-01 | The mapping document cited application code (E03) and driver-only logs (E05) in its Source column, which could read as using the allowlist as evidence | `FLOW8_PARAMETER_MAPPING.md` before this stage | **Corrected:** Source now lists documentary sources only (E01 with page); allowlist status moved to a separate column "App allowlisted"; E05 appears only under hardware verification |
| B-02 | PROTOCOL SUPPORTED applies to the raw CC value only. The engineering-unit conversions (`unit="dB"`, `"Hz"`, `"%"`) in `parameter_mapping.py` are app-defined approximations (fader unity at raw 101, linear gain, low cut, EQ halves, compressor %) | `parameter_mapping.py`; conflicts C-05, C-12 | **Clarified:** unit paths are APP ONLY (derived) and UNCONFIRMED; they are not part of the PROTOCOL SUPPORTED classification |
| B-03 | A decoder exists for 29 parameters but no mixer-originated byte has ever been seen in this repository (three captures: 2026-11-09 Phase 2B, and 2026-11-18 twice) | E07, E08, E17 | Read-back stays UNCONFIRMED; the decoder is not evidence |
| B-04 | `send_cc` accepts 37 pairs that the boundary does not allow | dry-run above | Allow-lists disagree (G-04); no status change |
| B-05 | The chart calls CC 10 BALANCE on every channel; the app calls it pan on mono channels | chart, `LOGICAL_CHANNELS` | Label question only; raw mapping unaffected |
| B-06 | Compressor: chart values 101-127 equal 100 %; allowlist accepts 0-127 | chart, allowlist | Compatible; values above 100 behave as 100 % per the chart |
| B-07 | Gain, low cut and compressor are allowlisted on channels 1-4; the chart implies channels 1-6 | conflict C-06 | Channels 5/6 and 7/8 stay UNCONFIRMED and not allowlisted |
| B-08 | Phantom is allowlisted for channels 1-2 with no gate at the boundary | `command_boundary.py` | Status stays PROTOCOL SUPPORTED, safety GATED in policy; enforcement gap G-02 |

### 3.3 Status corrections applied

No parameter changed class: none of the 97 was over-classified against the chart, and none was HARDWARE VERIFIED to begin with. What changed is the **evidence trail**: sources, a separate allowlist column, and the scope statement for unit conversions (B-01, B-02). The two over-claims about hardware verification are in older documents and are corrected in `S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

## 4. Appendix: the 97 allowlisted parameters

Columns: parameter; (MIDI channel, CC); chart row (E01 p. 8); chart match; allowlisted; `send_cc` accepts; protocol supported = documented and allowlisted; hardware verified; read-back confirmed; decoder exists in the app.

| Parameter | (ch, CC) | Chart row | Chart match | Allowlisted | send_cc accepts | Protocol supported | Hardware verified | Read-back confirmed | Decoder exists |
|---|---|---|---|---|---|---|---|---|---|
| ch1.eq_low | 1, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch1.eq_low_mid | 1, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch1.eq_hi_mid | 1, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch1.eq_hi | 1, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch1.mute | 1, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch1.fader | 1, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch1.gain | 1, 8 | GAIN | yes | yes | yes | yes | no | no | yes |
| ch1.low_cut | 1, 9 | LOW CUT | yes | yes | yes | yes | no | no | no |
| ch1.pan | 1, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch1.compressor | 1, 11 | COMP | yes | yes | yes | yes | no | no | no |
| ch1.phantom | 1, 12 | 48 V | yes | yes | yes | yes | no | no | yes |
| ch1.send_mon1 | 1, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch1.send_mon2 | 1, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch1.send_fx1 | 1, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch1.send_fx2 | 1, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| ch2.eq_low | 2, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch2.eq_low_mid | 2, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch2.eq_hi_mid | 2, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch2.eq_hi | 2, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch2.mute | 2, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch2.fader | 2, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch2.gain | 2, 8 | GAIN | yes | yes | yes | yes | no | no | yes |
| ch2.low_cut | 2, 9 | LOW CUT | yes | yes | yes | yes | no | no | no |
| ch2.pan | 2, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch2.compressor | 2, 11 | COMP | yes | yes | yes | yes | no | no | no |
| ch2.phantom | 2, 12 | 48 V | yes | yes | yes | yes | no | no | yes |
| ch2.send_mon1 | 2, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch2.send_mon2 | 2, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch2.send_fx1 | 2, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch2.send_fx2 | 2, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| ch3.eq_low | 3, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch3.eq_low_mid | 3, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch3.eq_hi_mid | 3, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch3.eq_hi | 3, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch3.mute | 3, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch3.fader | 3, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch3.gain | 3, 8 | GAIN | yes | yes | yes | yes | no | no | yes |
| ch3.low_cut | 3, 9 | LOW CUT | yes | yes | yes | yes | no | no | no |
| ch3.pan | 3, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch3.compressor | 3, 11 | COMP | yes | yes | yes | yes | no | no | no |
| ch3.send_mon1 | 3, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch3.send_mon2 | 3, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch3.send_fx1 | 3, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch3.send_fx2 | 3, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| ch4.eq_low | 4, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch4.eq_low_mid | 4, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch4.eq_hi_mid | 4, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch4.eq_hi | 4, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch4.mute | 4, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch4.fader | 4, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch4.gain | 4, 8 | GAIN | yes | yes | yes | yes | no | no | yes |
| ch4.low_cut | 4, 9 | LOW CUT | yes | yes | yes | yes | no | no | no |
| ch4.pan | 4, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch4.compressor | 4, 11 | COMP | yes | yes | yes | yes | no | no | no |
| ch4.send_mon1 | 4, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch4.send_mon2 | 4, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch4.send_fx1 | 4, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch4.send_fx2 | 4, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| ch5.eq_low | 5, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch5.eq_low_mid | 5, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch5.eq_hi_mid | 5, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch5.eq_hi | 5, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch5.mute | 5, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch5.fader | 5, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch5.pan | 5, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch5.send_mon1 | 5, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch5.send_mon2 | 5, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch5.send_fx1 | 5, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch5.send_fx2 | 5, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| ch6.eq_low | 6, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch6.eq_low_mid | 6, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch6.eq_hi_mid | 6, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch6.eq_hi | 6, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch6.mute | 6, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch6.fader | 6, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch6.pan | 6, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch6.send_mon1 | 6, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch6.send_mon2 | 6, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch6.send_fx1 | 6, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch6.send_fx2 | 6, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| ch7.eq_low | 7, 1 | EQ LOW | yes | yes | yes | yes | no | no | no |
| ch7.eq_low_mid | 7, 2 | EQ LOW MID | yes | yes | yes | yes | no | no | no |
| ch7.eq_hi_mid | 7, 3 | EQ HI MID | yes | yes | yes | yes | no | no | no |
| ch7.eq_hi | 7, 4 | EQ HI | yes | yes | yes | yes | no | no | no |
| ch7.mute | 7, 5 | MUTE | yes | yes | yes | yes | no | no | yes |
| ch7.fader | 7, 7 | CHANNEL LEVEL | yes | yes | yes | yes | no | no | yes |
| ch7.pan | 7, 10 | CHANNEL BALANCE | yes | yes | yes | yes | no | no | yes |
| ch7.send_mon1 | 7, 14 | SEND to MON1 | yes | yes | yes | yes | no | no | no |
| ch7.send_mon2 | 7, 15 | SEND to MON2 | yes | yes | yes | yes | no | no | no |
| ch7.send_fx1 | 7, 16 | SEND to FX1 | yes | yes | yes | yes | no | no | no |
| ch7.send_fx2 | 7, 17 | SEND to FX2 | yes | yes | yes | yes | no | no | no |
| main.fader | 8, 7 | BUS LEVEL | yes | yes | yes | yes | no | no | yes |
| main.balance | 8, 10 | BUS BALANCE | yes | yes | yes | yes | no | no | yes |
| mon1.fader | 9, 7 | BUS LEVEL | yes | yes | yes | yes | no | no | no |
| mon2.fader | 10, 7 | BUS LEVEL | yes | yes | yes | yes | no | no | no |
| fx1.fader | 11, 7 | BUS LEVEL | yes | yes | yes | yes | no | no | no |
| fx2.fader | 12, 7 | BUS LEVEL | yes | yes | yes | yes | no | no | no |
