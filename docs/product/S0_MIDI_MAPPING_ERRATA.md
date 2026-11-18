# S0 MIDI Mapping Errata Ledger

Date: 2026-11-18. Applies the owner-approved corrections D-S0-01 and D-S0-02 from `S0_FLOW8_CAPABILITY_RESEARCH.md` and records every document touched. Scope: documentation only. No source code changed in this step, no MIDI sent, no hardware touched, no previous evidence deleted or overwritten.

Labels: **FACT** = stated in a cited source. **ASSUMPTION** = inference. **UNCONFIRMED** = no source. Nothing UNCONFIRMED was promoted to verified.

## 1. Source register (three tiers kept apart)

### 1.1 Manufacturer document (content origin)
| Field | Value |
|---|---|
| Title | *Quick Start Guide — FLOW 8, 8-Input Digital Mixer with Bluetooth Audio and App Control* |
| Publisher | Behringer / Music Tribe (compliance text in the PDF names Music Tribe) |
| Version | Cover text reads "V 1.0" (extracted text, line 5) |
| Pages used | **PDF page 8** = MIDI Implementation chart (printed pages "14 FLOW 8" and "15 Quick Start Guide", one PDF page holds the spread). **PDF page 9** = Specifications (printed 16–17). Controls description = earlier pages of the same PDF (page numbers not recorded) |
| Limit | I did **not** obtain the file from a Behringer/Music Tribe server (my one attempt at a guessed manufacturer URL did not resolve). The authenticity of the retailer copy against the manufacturer's own copy is not verified |

### 1.2 Hosting source (copy of the document above)
| Field | Value |
|---|---|
| Host | Thomann (retailer) |
| URL | `https://images.thomann.de/pics/atg/atgdata/document/manual/505388.pdf` |
| Local file (kept) | `docs/product/sources/behringer_flow8_quick_start_guide_V1.0_thomann-copy_505388.pdf` (2,666,564 bytes, PDF 1.4) |
| **SHA-256** | `cfe98d5cfd298d77c7a919bb7ef87c8207ec4a9cc6a8227db2e1a79a298f5d29` (recomputed after copying: identical) |
| Retrieved | 2026-11-18 with curl; text extracted with `pdftotext -raw` and `-layout` |
| Note | The same document under `images.static-thomann.de/.../505388_flow_8_qsg_ww.pdf` returned unreadable content to my fetch tool and was not used |

### 1.3 Mirror and third-party sources (never used as the basis of a correction)
| ID | Source | Type | SHA-256 / status | Use |
|---|---|---|---|---|
| M1 | Manuals+ mirror via `https://www.adorama.com/col/productManuals/BEFLOW8K2.pdf` | Third-party mirror of the guide | `f4469ea36e27c85ac52ada932a7f1092ea084326072f64ef85ba424ea36e3c7f` (548,544 bytes; local copy `docs/product/sources/manuals-plus_mirror_flow8_user_guide_BEFLOW8K2.pdf`) | Text partly garbled; only confirms the chart exists in the same form |
| T1 | Unofficial Behringer Forums threads (`behringer.world`) | Third-party forum | Not read (HTTP 403); statements known only from search summaries | Context for the transmit question only |
| T2 | `https://github.com/abelroes/flow-8-midi` README | Third-party project | Read | Context only |
| T3 | `https://ideas.behringer.com/p/flow-8-midi` | Manufacturer feedback board, user post | Read; no staff reply | Context only |

The two PDFs in `docs/product/sources/` are copyrighted third-party files. They are kept as local evidence and are **not** to be committed or redistributed without checking the rights.

## 2. Numbering semantics (checked)

| Item | Finding | Basis | Confidence |
|---|---|---|---|
| MIDI channel numbers in the chart | 1-based, 1–16 | The chart assigns "SNAPSHOTS - whole mixer = 16" and says "[MIDI-Ch. 15 = not used]"; there are 16 channels, so 16 is the last. Existing repository tests and documents that write Main at channel 8 (status byte `0xB7`) use the same numbering | High |
| Status bytes | Control Change `0xB0 + (ch − 1)`, Program Change `0xC0 + (ch − 1)`, Note On `0x90 + (ch − 1)` | MIDI 1.0 convention (not stated in the chart) | High (standard) |
| Program Change numbers | The chart says "Program Change 0 & 17-127 = ignored" for FX, and "Presets = 1-15; RESET = Prog. Chg. #16" for snapshots. Values 0 and 17–127 are named, so the numbers are the raw data-byte values 0–127: preset N = data byte N, **reset = data byte 16 (`0x10`)** | Wording of the chart | **ASSUMPTION, Medium.** If a tool shows program numbers 1–128, data byte 15 appears as "16". The safe rule for any future sender: work in raw data bytes, never allow data byte 16, and do not send any Program Change on channel 16 until a controlled hardware test with the owner present |

Resulting status bytes (derived, not tested on hardware):

| Channel | Role | Control Change | Program Change | Other |
|---|---|---|---|---|
| 13 | FX 1 slot | `0xBC` (CC 1 = Param 1, CC 2 = Param 2) | `0xCC` (preset 1–16) | — |
| 14 | FX 2 slot | `0xBD` | `0xCD` | — |
| 15 | unused | — | — | — |
| 16 | Global | `0xBF` (CC 1 = FX mute) | `0xCF`: 1–15 recall snapshot, **16 = RESET** | Note On `0x9F`, note 0 = tap tempo |

Why the old documents were wrong: they placed FX 1 on channel 14 and FX 2 on channel 15, one channel too high (status `0xBD` / `0xBE`), and listed channel 13 as reserved. Under the official chart a Program Change sent to channel 14 would select the **FX 2** preset, and channel 15 is ignored.

## 3. Documents changed

Living reference documents were corrected in place with a visible correction note quoting the previous text. Historical reports keep their original text; an errata block was inserted under the title. All are tracked by git, so the previous versions also remain in history. Nothing was committed.

| File | Treatment | What changed |
|---|---|---|
| `docs/hardware/FLOW8_PROTOCOL_SPECIFICATION.md` | Corrected + note | Channel table rows 13–16; snapshot line |
| `FLOW8_USB_MIDI_PROTOCOL.md` | Corrected + notes | Channel table rows 13–16; section 4 heading and text; FX preset descriptions marked UNCONFIRMED; CC 1–4 → CC 1–2; PC 16 danger; coverage rows |
| `docs/testing/HARDWARE_VERIFICATION_MATRIX.md` | Corrected + note | FX 1/FX 2 rows; snapshot row; new Mixer Reset row; label changed from "VERIFIED BY PROTOCOL EVIDENCE" to "PROTOCOL SUPPORTED — NOT HARDWARE VERIFIED; sender disabled" |
| `docs/testing/KNOWN_LIMITATIONS.md` | Corrected + note | FX channels; FX parameters note |
| `docs/architecture/CUEAIR_TO_FLOW8_COMPATIBILITY.md` | Corrected | FX channels |
| `docs/product/FLOW8_PRODUCT_ROADMAP.md`, `docs/product/CUEAIR_FEATURE_GAP_MATRIX.md` | Corrected | FX channels; snapshot range; PC 16 forbidden |
| `PHASE_0_5_SUMMARY.md`, `FLOW8_ARCHITECTURE_ALIGNMENT.md`, `FLOW8_HARDWARE_DOMAIN_MODEL.md`, `FLOW8_SPECIFICATION_GAP_ANALYSIS.md`, `FLOW8_PHASE_C1_AUDIT.md`, `FLOW8_PHASE_UI1_REPOSITORY_AUDIT.md` | Errata block only (original text unchanged) | Points to this ledger |
| New: `docs/product/S0_MIDI_MAPPING_ERRATA.md` (this file), `docs/product/sources/*.pdf` | Added | Ledger and local evidence copies |

## 4. Before and after

| # | File : location (original) | Before | After | Source | Status after |
|---|---|---|---|---|---|
| 1 | `FLOW8_PROTOCOL_SPECIFICATION.md` : channel table | Ch 13 Reserved; Ch 14 FX 1; Ch 15 FX 2 | Ch 13 FX 1 slot; Ch 14 FX 2 slot; Ch 15 unused | Guide V 1.0, PDF p. 8 (OVERVIEW and FX-slot rows) | PS (official chart), not hardware verified |
| 2 | same : Ch 16 row | "Global Snapshots (PC 1..15) & Tap Tempo" | adds: PC 16 = MIXER RESET, forbidden; FX mute CC 1 | PDF p. 8 (SNAPSHOT and FX1/FX2 common rows) | PS; reset FORBIDDEN |
| 3 | `FLOW8_USB_MIDI_PROTOCOL.md` : channel table rows 13–16 | as row 1–2 before | as row 1–2 after | PDF p. 8 | as above |
| 4 | same : section 4 | "FX Slot Engines (Channels 14 & 15)"; FX 1 = 16 reverbs, FX 2 = 16 modulation models | "Channels 13 & 14"; preset content UNCONFIRMED | PDF p. 8 (no preset names); T3/review not used as basis | UNCONFIRMED (content) |
| 5 | same : section 4.2 | "CC 1 to CC 4 ... decay time, pre-delay, modulation depth, feedback" | CC 1 = Parameter 1 (0–100 %), CC 2 = Parameter 2 (A/B switch); meanings UNCONFIRMED | PDF p. 8 (FX rows) | PS; meaning UNCONFIRMED |
| 6 | same : section 5.1 | "PC 16 triggers Full Mixer Hardware Reset" (no warning) | adds DANGEROUS, never sent; numbering note | PDF p. 8: "Loading #16 = RESET!" | FORBIDDEN |
| 7 | same : coverage table | FX "VERIFIED"; Snapshots (1–15) & Reset "PC 1–16 ... VERIFIED" | split into FX (PS), Snapshots 1–15 (PS), Mixer Reset (FORBIDDEN) | PDF p. 8 | PS / FORBIDDEN |
| 8 | `HARDWARE_VERIFICATION_MATRIX.md` : FX rows | MIDI Ch 14 / Ch 15, "VERIFIED BY PROTOCOL EVIDENCE" | Ch 13 / Ch 14, "PROTOCOL SUPPORTED — NOT HARDWARE VERIFIED; sender disabled" | PDF p. 8 | PS |
| 9 | same : snapshot row | "Program Change (1..16)" | "1..15 only" + new FORBIDDEN row for PC 16 | PDF p. 8 | PS / FORBIDDEN |
| 10 | `KNOWN_LIMITATIONS.md` §1.3 | "Program Change 1..16 on MIDI Channels 14 and 15" | Channel 13 (FX 1), Channel 14 (FX 2); note on CC 1/CC 2 and snapshot rules | PDF p. 8 | PS |
| 11 | `CUEAIR_TO_FLOW8_COMPATIBILITY.md` : FX row | "Ch 14 (FX1) and Ch 15 (FX2)" | "Ch 13 (FX1) and Ch 14 (FX2)" | PDF p. 8 | PS |
| 12 | `FLOW8_PRODUCT_ROADMAP.md` F5/F3, `CUEAIR_FEATURE_GAP_MATRIX.md` rows 9 and 11 | "Ch 14/15"; "PC Ch 16" | "Ch 13/14"; "PC 1–15 on Ch 16, PC 16 forbidden" | PDF p. 8 | PS |

Searching the repository afterwards for the old pairing ("14 & 15", "14/15", "14–15") finds only the preserved original lines in the six historical reports, each now covered by an errata block, and the quoted "previous text" in the corrections.

## 5. Mapping items still UNCONFIRMED (not changed, not promoted)

1. Meaning of Parameter 1 and Parameter 2 for each FX preset; FX preset names/types; whether FX preset 16 is an ordinary preset.
2. Program Change data-byte versus 1-based display (see §2).
3. What PC 16 (reset) clears (names, snapshots, settings).
4. Whether channels 5/6 and 7/8 respond to CC 8 (gain), CC 9 (low cut), CC 11 (compressor). The chart excludes only "Ch. USB/BT"; the repository restricts these to channels 1–4.
5. EQ band frequency meaning and Q (specification gives 20 Hz shelf, 300 Hz, 1.5 kHz, 20 kHz shelf; the UI shows 80/400/2.5k/10k without a source).
6. Value curves between the documented end points (fader, gain, EQ, low cut, sends). The repository puts fader unity at raw 101; a third-party formula (not verified) suggests about 111.
7. Whether any live MIDI is transmitted over USB and under what setting (repository premise "USB TX: ON" has no source in the guide).
8. Whether the firmware that produced our captures matches guide V 1.0.

## 6. Conflicts found and deliberately NOT edited (need your approval)

| Item | Where | Why not changed |
|---|---|---|
| "Inbound CC arrives when SETUP → MIDI → USB TX: ON" | `BIDIRECTIONAL_STATE_MODEL.md`, `KNOWN_LIMITATIONS.md` §1.2, `FLOW8_PROTOCOL_SPECIFICATION.md` (inbound section), stage 2 documents | Outside the approved corrections (D-S0-06) |
| EQ band frequency labels | `channel_detail.py` (source), docs | Source code frozen; D-S0-04 not approved |
| Gain/low cut/compressor on ch 5/6 and 7/8 | docs and code | D-S0-03 not approved; needs hardware or documentation |
| Hi-Z input location: "Ch 4 = Hi-Z Instrument" (`FLOW8_PROTOCOL_SPECIFICATION.md`) versus "Ch 4 ... no Hi-Z" (`FLOW8_USB_MIDI_PROTOCOL.md`) versus guide: Hi-Z on 6R/8R | docs | Not a MIDI mapping; flagged because the two documents contradict each other |
| Fader taper "logarithmic" (`FLOW8_PARAMETER_MAP.md`) and unity at 101 | docs and `parameter_mapping.py` | D-S0-08 not approved |
| Comment "Channel 13 is reserved/unsupported on FLOW 8" in `tests/test_midi_out.py` line 52; `midi_out.py` rejects channels 13–16 | source | Source code frozen. Behaviour is currently safe (no FX or snapshot sender); revisit before any FX sender |

## 7. Confirmations for this step

- **Source code unchanged in this step:** `git diff --stat -- flow8 tests` is identical to the value before this step (the same five Stage 1 files, 151 insertions, 12 deletions, all from earlier approved Stage 1 work). `tests/` untracked files unchanged.
- **Hardware unchanged:** no MIDI port was opened and no message sent in this step.
- **Evidence preserved:** nothing deleted; original text of historical reports intact; previous values of corrected rows quoted in correction notes and in §4; git history untouched; nothing committed.
- **Not started:** S1 capability table, S2 Preserve Levels, FX Program Change sender, snapshot recall/reset sender, preamp gain enablement, phantom power automation.
