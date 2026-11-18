# FLOW 8 Capability Matrix (Single Source of Truth)

Date: 2026-11-18. Stage S1, documentation only. Per-parameter detail: `FLOW8_PARAMETER_MAPPING.md` (167 rows). Rules: `FLOW8_SAFETY_POLICY.md`. Evidence: `FLOW8_EVIDENCE_REGISTER.md`. Open disagreements: `FLOW8_UNRESOLVED_CONFLICTS.md`.

Nothing in this stage changed code, sent MIDI or opened hardware. CueAir is not evidence for any statement here.

## 1. Status vocabulary

| Status | Meaning here |
|---|---|
| **DOCUMENTED** | A source describes it; the app has no mapping or sender for it |
| **PROTOCOL SUPPORTED** | Documented and implemented as a mapping in the app; **not** confirmed on hardware |
| **HARDWARE VERIFIED** | Physical effect or mixer-originated message observed and recorded. A driver return code (`MMSYSERR_NOERROR`) never qualifies |
| **APP ONLY** | State the app keeps itself; not a mixer control and never shown as one |
| **UNCONFIRMED** | No sufficient evidence either way |
| **UNSUPPORTED** | The evidence says the mixer has no such capability |

**Count today: HARDWARE VERIFIED = 0.** Reason: every hardware log in the repository ends at `DRIVER_DISPATCHED` with `HW_Applied=None`, and the project's own Phase C2 re-grading reduced the earlier "hardware tested" parameters to `API_ACKNOWLEDGED` (evidence E04, E05, E06). Earlier documents that say "VERIFIED ON REAL HARDWARE" are over-claims (conflict C-10).

## 2. Capability by area

Legend for UI: **Yes** = a control exists in the current app; **Gated** = exists behind a gate; **Preview** = no dispatch; **No** = no control.

| Area | What the mixer can be commanded to do (documented) | In the app | Read-back from hardware | Status | Main limits and conflicts |
|---|---|---|---|---|---|
| **Channel fader** | Level on MIDI ch 1–7, CC 7; 0 = OFF, 1–127 = −70…+10 dB | Yes, strips 1–7 (+Main) | UNCONFIRMED; none seen (E07, E08) | PROTOCOL SUPPORTED | Taper unknown (C-05); sends were only driver-accepted |
| **Pan / Balance** | CC 10, 64 = centre; the chart calls it BALANCE; Main balance only on MAIN | Yes, strips and Main | UNCONFIRMED | PROTOCOL SUPPORTED | Whether mono channels behave as pan is not stated |
| **Mute** | CC 5, 0 off / 1–127 on | Yes | UNCONFIRMED | PROTOCOL SUPPORTED | none |
| **Solo** | CC 6 per channel | No | UNCONFIRMED | DOCUMENTED | Not in the allowlist |
| **Channel status** | CC 13 (hidden/active) | No | UNCONFIRMED | DOCUMENTED | Not in the allowlist |
| **Preamp gain** | CC 8, 0–127 = −20…+60 dB; chart excludes only USB/BT | Preview only; apply disabled in UI | UNCONFIRMED | PROTOCOL SUPPORTED (ch 1–4); UNCONFIRMED (ch 5/6, 7/8); UNSUPPORTED (USB/BT) | Curve unverified; **service layer is not gated** (policy gap G-01); C-06 |
| **Phantom +48 V** | CC 12, **ch 1 and 2 only** | Yes, confirmation dialog | UNCONFIRMED | PROTOCOL SUPPORTED (ch 1–2); UNSUPPORTED (ch 3–7) | Never automated; service layer not gated (G-02) |
| **EQ (4 bands)** | CC 1–4, ±15 dB, 64 = 0 dB, channels 1–7 | Yes, Inspector | UNCONFIRMED | PROTOCOL SUPPORTED | Frequencies and Q unconfirmed (C-04); the UI's frequency labels have no source |
| **Low cut** | CC 9, 20–600 Hz | Yes, ch 1–4 | UNCONFIRMED | PROTOCOL SUPPORTED (ch 1–4); UNCONFIRMED (ch 5/6, 7/8) | Scale unconfirmed; C-06 |
| **Compressor** | CC 11, 0–100 %; only this one control is documented | Yes, ch 1–4 | UNCONFIRMED | PROTOCOL SUPPORTED (ch 1–4); UNCONFIRMED (ch 5/6, 7/8) | No threshold, ratio, attack, release or gate documented anywhere |
| **FX 1 / FX 2** | Preset select (Program Change 1–16) on ch 13 / 14; Parameter 1 = CC 1 (0–100 %), Parameter 2 = CC 2 (A/B) | **No sender, no UI** | UNCONFIRMED | DOCUMENTED | Preset content unknown (C-09); Program Change disabled by policy; numbering C-01 |
| **FX sends** | Per-channel CC 16 / CC 17 | Yes, Inspector | UNCONFIRMED | PROTOCOL SUPPORTED | Taper (C-05) |
| **FX bus levels** | ch 11 / 12 CC 7 | No (backend allowlist only) | UNCONFIRMED | PROTOCOL SUPPORTED | none |
| **Monitor (Aux) sends** | CC 14 (MON 1), CC 15 (MON 2) | Yes | UNCONFIRMED | PROTOCOL SUPPORTED | Taper (C-05) |
| **Monitor bus levels** | ch 9 / 10 CC 7 | No | UNCONFIRMED | PROTOCOL SUPPORTED | Backend only |
| **Main output** | ch 8: level CC 7, balance CC 10; limiter CC 8 (−30…0 dB); 9-band GEQ CC 11–19 (±15 dB) on Main, MON 1, MON 2 | Level and balance only | UNCONFIRMED | PROTOCOL SUPPORTED (level, balance); DOCUMENTED (limiter, GEQ) | GEQ 62 vs 62.5 Hz (C-11) |
| **Snapshots** | Program Change 1–15 on ch 16 recalls stored snapshots; **16 = mixer reset** | **No sender, no UI** (the app's "scenes" are APP ONLY and send CCs) | UNCONFIRMED; contents cannot be read per the sources | DOCUMENTED | Numbering (C-01); recall and reset **disabled / forbidden** by policy |
| **FX mute, tap tempo** | ch 16: CC 1 mute; Note On 0 tap (FX 2 presets 1–12) | No | UNCONFIRMED | DOCUMENTED | disabled by policy |
| **USB MIDI input (host → mixer)** | USB jack provides "MIDI control" (guide) | Used (send path) | n/a | DOCUMENTED | Driver acceptance only; no physical effect recorded |
| **USB MIDI output (mixer → host)** | **No document describes it** | Listener exists; nothing received | **UNCONFIRMED; BLOCKED**: 0 bytes in three captures (2026-11-09 and 2026-11-18) | UNCONFIRMED | USB TX premise unsourced (C-02) |
| **USB audio** | Guide: 24-bit / 48 kHz, "8 x 2". Windows lists capture endpoints Mic 1, Mic 2, Mic/Line 3, Mic/Line 4, Line 5/6, Line 7/8, Main L/R, Multi In 1-10 (Recording mode) and USB Out 1/2, 3/4 (status OK, E09) | Not integrated | n/a | DOCUMENTED (existence); stream access UNCONFIRMED (no sample ever read) | Channel configuration (C-07); signal point (pre/post EQ) unknown |
| **App scenes, undo/redo, presets** | n/a | Yes | n/a | APP ONLY | Hold commanded values, never mixer state |

## 3. What can be controlled, read, and not done

**Can be commanded (documented and implemented, not hardware verified):** fader, pan/balance, mute, EQ ×4, low cut and compressor (ch 1–4), aux and FX sends, +48 V on ch 1–2 (behind a dialog; never automated), bus levels (backend only), Main balance. Gain has a path at service level but is gated at the UI.

**Documented but not implemented, so not available:** solo, channel status, bus limiter, 9-band GEQ, FX preset select, FX parameters 1–2, FX mute, tap tempo, snapshot recall.

**Never to be sent:** Program Change 16 on channel 16 (mixer reset).

**Can be read back from the hardware:** **nothing is confirmed.** The app contains a decoder for incoming fader, pan, mute, phantom and gain messages, but no source documents the mixer transmitting them, and our three captures (E07, E08, E17) received nothing. The app must show every value as COMMANDED (what it sent) or UNSYNCED, and must not say it reads real values. OBSERVED may only appear if mixer-originated bytes are actually received.

**Not possible according to the evidence:** EQ frequency, Q or filter type; compressor threshold, ratio, attack, release; gate or expander; per-preset FX editing beyond Parameters 1–2; phantom on ch 3–7; gain/low cut/compressor on USB/BT; solo or other state interrogation by query (no document).

## 4. Honest-UI constraints that follow

1. A control may exist only for a row that is DOCUMENTED in the manufacturer chart; its value is labelled COMMANDED, never "hardware".
2. No control for rows that are UNCONFIRMED, UNSUPPORTED, DISABLED or FORBIDDEN.
3. Numeric labels without a source (EQ band frequencies, fader dB readouts, gain dB preview) must be shown as approximate or unsourced (existing UI items to review in S2; not changed now).
4. Scenes and snapshots are "values this app commanded", never mixer state.

## 5. S1.2 update (2026-11-18)

Preamp gain is now **blocked in code** at the command boundary, service, engine, ledger and low-level port (no override), and +48 V ON needs a user-confirmation grant at the boundary. The rows above keep their capability classes (PROTOCOL SUPPORTED, not hardware verified); only the enforcement changed. EQ bands are labelled BAND 1–4 in the UI because the frequencies are unconfirmed (C-04). The 37 documented-but-unimplemented pairs are refused by the low-level port as well. See `S1_2_IMPLEMENTATION_REPORT.md`.
