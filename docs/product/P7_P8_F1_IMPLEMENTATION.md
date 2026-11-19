# P7 / P8 / F1: EQ curve, inspector ergonomics and clean-room Thai presets

**Status:** Implemented, offline- and browser-verified (simulated connection).
**Date:** 2026-11-19.
**Branch:** `stage2-mixer-workstation`.
**Companions:** `F7_CHANGE_PLAN_IMPLEMENTATION.md`, `FLOW8_SAFETY_POLICY.md`,
`docs/hardware/FLOW8_HARDWARE_CAPABILITIES.md`, `docs/hardware/FLOW8_PARAMETER_MAP.md`.

This stage delivered three items on the ranked list at once:

1. **P7 / F4** — the EQ view draws a real frequency response computed from the values this
   app sent (4-band EQ + Low Cut), with honest provenance styling and draggable nodes.
2. **P8** — the Inspector fits 1366×768, and pointer drags are coalesced into single undo
   steps by a batch gesture protocol.
3. **F1 (unblocked)** — a 100% clean-room Thai acoustic preset catalog, applied only through
   the Staged Change Plan.

---

## 1. P7 / F4 — EQ curve

### Model

`flow8/web_ui/app.js` now computes each band as a standard RBJ biquad at the FLOW 8's fixed
centre frequency, then sums the four bands and the low cut into one response:

| Element | Frequency | Shape used | Note |
|---|---|---|---|
| EQ Low | 100 Hz | low shelf, Q 0.7 | centre from the FLOW 8 app; shape assumed |
| EQ Low-Mid | 500 Hz | peaking, Q 1.0 | shape assumed |
| EQ Hi-Mid | 2 kHz | peaking, Q 1.0 | shape assumed |
| EQ High | 12 kHz | high shelf, Q 0.7 | shape assumed |
| Low Cut | 20–600 Hz | 2nd order high pass (12 dB/oct) | slope from `FLOW8_HARDWARE_CAPABILITIES.md`; scale linear per `parameter_mapping` |

The **gain values are exact** (raw 64 = 0.0 dB, asymmetric mapping as in
`parameter_mapping.eq_db_to_midi`); only the filter shape is an assumption, and both the
Inspector and the EQ tab say so in their notes. Nothing here is a measurement.

### Honesty rules

- `COMMANDED` / `OBSERVED` → solid high-contrast curve with a light fill.
- `UNSYNCED` (the user's `ASSUMED_DEFAULT`) → dashed dim curve, plus the label
  `UNSYNCED · CURVE IS AN ASSUMPTION`; the side panel shows `SOURCE UNSYNC`.
- The bus **9-band graphic EQ** has no verified MIDI address, so it is drawn as a dashed
  0 dB line with hollow nodes, labelled `GEQ 9-BAND · NO VERIFIED MIDI ADDRESS`, and its
  section stays locked. No value is invented and nothing is sent.

### Interaction

- Band nodes drag vertically (gain); the Low Cut node drags horizontally (frequency).
- Values update the numeric side panel live and are sent throttled (see P8), so the mixer
  follows the finger.
- `RESET` (Inspector and EQ tab) no longer fires five commands: it builds a change plan
  (`eq_*` → 64, `low_cut` → 0 on CH 1–4) and opens the F7 review panel. One `COMMIT`,
  one `UNDO` step.

---

## 2. P8 — ergonomics at 1366×768 and batch gestures

### Two real defects found and fixed

1. **The Inspector never rendered.** `renderInspector()` existed but was not called from
   `renderView()`, so the non-blocking Inspector from the CueAir rewrite could not open at
   all. It is now called on every view render.
2. **The Inspector was a flex row inside a column layout.** Once it did render it took the
   bottom of the split workspace and squeezed the fader bank and stage cards. It is now an
   absolute overlay on the right (`@media (min-width: 761px)`), with the phone bottom-sheet
   behaviour unchanged.

### Layout

- Canvas buffers are sized from their CSS box before every draw, so nodes stay circular and
  labels keep their scale at any width (previously a 900 px buffer was stretched into a
  1070 px box).
- A compact `@media (max-height: 820px)` block tightens paddings, knobs and preset cards for
  1366×768 and iPad landscape.
- Measured in Chromium at 1366×768: page overflow `0`, Inspector body needs no scroll
  (815 px content in an 815 px box), and the last Inspector section (SENDS) ends at y=754
  inside the 768 px viewport.

### Batch gesture protocol

```
pointerdown → POST beginGesture  → service.begin_batch()
pointermove → POST set* (≥ 70 ms apart, quiet: no toast)
pointerup   → POST set* (final)  → POST endGesture → service.end_batch()
```

The ledger coalesces every value of one parameter inside the batch into a single record whose
`previous_value` is the value at pointer-down and whose `new_value` is the value on release.
So a whole drag is one `UNDO`. A gesture that is never closed is closed before the next
command after `GESTURE_MAX_S = 20 s`, so an abandoned pointer cannot swallow unrelated
commands into one step.

Applied to: fader bank faders, Inspector/stage rotary knobs, EQ tab nodes, Inspector EQ nodes.

---

## 3. F1 — clean-room Thai presets

**Decision taken:** the owner's Option A — our own values, our own Thai text, no CueAir data.
`flow8/presets_th.py` states this in its module docstring and contains no converted values,
names or notes from any third-party preset file. The earlier CueAir-adapted catalog in
`flow8/presets.py` is left untouched for compatibility, but the console no longer uses it.

| id | Name (TH) | Category | Low cut | Low | L-Mid | H-Mid | High | Comp |
|---|---|---|---|---|---|---|---|---|
| th-pa-mc | ไมค์พูดพิธีกร (MC) | พูด/พิธีกร | 110 Hz | −3.0 | −2.5 | +2.0 | +0.5 | 25% |
| th-pa-lecture | ไมค์ประชุม / บรรยาย | พูด/พิธีกร | 90 Hz | −2.0 | −1.5 | +1.5 | 0 | 20% |
| th-vocal-male | เสียงร้องสด (ชาย) | ร้อง | 85 Hz | −1.0 | −1.5 | +2.0 | +1.5 | 35% |
| th-vocal-female | เสียงร้องสด (หญิง) | ร้อง | 110 Hz | −2.0 | −0.5 | +2.0 | +1.0 | 30% |
| th-vocal-harmony | เสียงร้องประสาน | ร้อง | 120 Hz | −2.5 | −2.0 | +1.0 | +0.5 | 40% |
| th-acoustic-di | กีตาร์โปร่ง (DI) | เครื่องดนตรี | 80 Hz | −3.0 | −1.0 | +1.0 | +1.5 | 15% |
| th-electric-clean | กีตาร์ไฟฟ้าคลีน | เครื่องดนตรี | 100 Hz | −2.0 | 0 | +1.5 | +1.0 | 20% |
| th-bass-di | เบสไฟฟ้า (DI) | เครื่องดนตรี | 30 Hz | +1.5 | −2.0 | 0 | −1.0 | 40% |
| th-keys-stereo | คีย์บอร์ดสเตอรีโอ | เครื่องดนตรี | 60 Hz | −1.5 | −1.0 | +0.5 | +0.5 | 15% |
| th-bgm | BGM เปิดงาน / ดนตรีพื้นหลัง | เล่นกลับ (BGM) | 70 Hz | −1.0 | −1.5 | 0 | −0.5 | 30% |
| th-flat-reset | รีเซ็ต EQ (Flat) | รีเซ็ต | OFF | 0 | 0 | 0 | 0 | 0 |

Each preset carries original Thai notes explaining the engineering reason (`why`), shown in the
console. Ranges are deliberately conservative: EQ gains stay within ±6 dB and no preset
touches fader, pan, mute, sends, preamp gain or +48V.

### Routing

```
GET /api/presets/thai            → catalog + exact raw values (eqRaw, lowCutRaw, compressorRaw)
console scope toggles            → presetPlanChanges() → previewChangePlan → COMMIT
```

The console converts nothing: it sends the raw values returned by Python, so the reviewed diff
is exactly what the boundary receives. Low Cut and Comp lines are only produced for CH 1–4;
CH 5–7 plans contain EQ lines only. The Inspector's ★ PRESETS key now opens the Presets tab
(the legacy quick-apply modal was removed).

---

## 4. API additions

| Action / route | Purpose |
|---|---|
| `GET /api/presets/thai` | clean-room catalog, categories, exact raw values |
| `beginGesture` | open one ledger batch (allowed offline) |
| `endGesture` | close it, return `steps` (number of undo records committed) |

`previewChangePlan` / `commitChangePlan` are unchanged; presets and RESET reuse them.

## 5. Tests

- `tests/test_thai_presets.py` — 12 tests: catalog originality/Thai text, tonal range, reset
  semantics, scope rules, no gain/phantom in any plan, end-to-end commit as one undo step,
  fader/pan/send untouched, API raw values.
- `tests/test_gestures.py` — 5 tests: drag coalescing for faders and EQ, separate steps
  outside gestures, `endGesture` without `beginGesture`, stale-gesture close.
- Full suite: 503 tests before this stage → **520 tests** (`OK`, 5 skipped) — see §6.

## 6. Browser verification (Chromium, 1366×768, simulated connection, no hardware)

```
PAGE_OVERFLOW 0
EQ drag:      BEFORE_EQ_LOW 64 → AFTER_EQ_LOW 29 → UNDO_EQ_LOW 64      (one drag, one undo)
Fader drag:   BEFORE_FADER 80 → AFTER_FADER 75 → UNDO_FADER 80         (one drag, one undo)
Inspector:    open, 3 sections, body 815/815, last section bottom 754 ≤ 768
Bus GEQ:      visible, "GEQ 9-BAND · NO VERIFIED MIDI ADDRESS", locked note
Preset:       6 plan rows → committed 6 changes → UNDO restores all 6, fader stays 80
Unsynced CH2: dashed curve + "UNSYNCED · CURVE IS AN ASSUMPTION"
CONSOLE_ERRORS []
```

Screenshots (local evidence, `tools/output/` is git-ignored):
`p7-eq-1366.png`, `p7-eq-unsynced-1366.png`, `p7-eq-drag-1366.png`,
`p7-preset-plan-1366.png`, `p7-preset-committed-1366.png`, `p8-inspector-1366.png`,
`p8-inspector-bottom-1366.png`, `p8-bus-geq-1366.png`.

Not hardware-verified: the mixer was not connected, so no claim is made about the audible
result or about MIDI delivery beyond the command boundary.

## 7. Known limitations

- **Curve shape is assumed.** Band Q, shelf/peak choice and the low cut slope are
  approximations; only the gains and the fixed centres are known. The curve is labelled as a
  picture of the commanded values, never as a measurement.
- **Bus GEQ is read-only.** No verified MIDI address exists, so it cannot be displayed with
  values or edited; the section stays locked.
- **Gesture batches are hub-wide.** One drag at a time is expected; a second client starting a
  drag closes the first batch (the first client's final value still lands as its own step).
- **Live sends only while connected.** Offline, a drag sends once on release (which the hub
  rejects with `503` and a toast) instead of streaming rejected commands.
- **Old adapted catalog remains.** `/api/presets` and `apply_channel_preset` still exist for
  compatibility and tests; the console no longer calls them.

## 8. Next

1. **F0 / P0** — USB TX capture and unplug detection remain the blocker for any OBSERVED claim.
2. F5 / P9 — FX slot mapping needs a Program Change test on the mixer.
3. F7 follow-up — plan staleness lock (preview → commit re-check) once F0 gives inbound state.
