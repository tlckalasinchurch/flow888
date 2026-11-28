# FLOW 888 v3 — Hallmark closure, visual acceptance and engineering safety audit (2026-11-28)

> **Round 3 update (the "EXECUTE NOW" pass).** The checks in this report were re-run on the final code (C1-C5) and give the same results unless noted.
>
> **New defect C5 (class A, fixed).** On a slider whose value is unknown (FX PARAM 1 and 2, LIMITER), the keyboard focus ring disappeared in both themes.
> - Cause: `input[type="range"].unk-range` set a 1 px dashed outline, with higher specificity than `:focus-visible`. It was introduced in UI pass 2.
> - Fix: `input[type="range"].unk-range:focus-visible { outline: 2px solid var(--sel); outline-offset: 2px; }`
> - Before: 6 failures (3 controls × 2 themes), outline 1 px dashed.
> - After: 0 failures, measured over 384 focus stops by real Tab presses (`focus_check.py`, `focus_check.json`).
>
> **Round 3 numbers (C1-C5)**
>
> | Check | Result |
> |---|---|
> | Hallmark | 15 FAIL, 2 REFLEX, 0 WARN (`closure_round3_console.txt`); classification unchanged |
> | Acceptance captures | 100: contrast 0, page errors 0, text <12 px 0, targets <24 px 0, page overflow 0 |
> | Stage overflow | only 320 SENDS (deliberate) |
> | Faders | 198 checks, max error 0.3 px; resize max 0.5 px |
> | Offline | all `--`, `MUTE ?` |
> | Interaction | one key or click = 1 command; drag = 1 gesture; UNDO `CC ch1 7 101`, REDO `CC ch1 7 68`; LOCKED and NO MIXER send 0; reconnect reads `--` / `UNK` |
> | MIDI | byte-identical to the baseline (1037 bytes, `payload_round3.json`) |
> | Full suite | 533 ran, 528 passed, 0 failed, 0 errors, 5 hardware skips, 0 physical port opens (`run_tests_no_hw_round3.log`) |
>
> **Diffs:** `patches/v3css_diff_before_C5.patch` and `patches/v3css_diff_after_C5.patch`.
>
> **Branding: LOCKED** per the owner, following PRODUCT.md and PR #13: product FLOW 888, hardware FLOW 8, console label LIVE CONSOLE. No change.
>
> **A1 and A4** are recorded in `REPOSITORY_VERIFICATION.md` §6. Nothing was added to git.

- **Branch:** `feat/v3-console-ui-refinement` (pushed earlier as `8e777bb`).
- **Tonight's work is uncommitted:** one CSS change plus audit files. No commit, push, merge or deploy.
- **Hardware isolation:** port 8844 was not used. Every run used an in-process hub on a free port or the rig on 8855, with winmm open and send replaced by guards that raise. Every run recorded 0 physical MIDI calls.

## 1. Executive summary
- **Repository: VERIFIED.** The repository was clean before tonight. The Hallmark session's 3 files are committed and accounted for. There is no dependency, backend, test or production-asset drift.
- **Hallmark closure: VERIFIED.** 15 FAIL and 2 REFLEX remain. Every one is classified below, and none is a genuine defect.
- **Visual acceptance: VISUAL VERIFIED.** 100 captures (5 viewports × day/night × 10 pages) found 4 genuine UI defects, all fixed in CSS (C1-C4). After the fixes there are 0 contrast failures, 0 targets under 24 px, 0 page errors, 0 geometry failures and no unintended page overflow.
- **MIDI and state: TEST VERIFIED.**
  - MIDI payloads are byte-identical to the baseline (1037 bytes, 12 commands).
  - Locked and offline controls send nothing.
  - Unknown values stay unknown after a reconnect.
- **Full suite: TEST VERIFIED.** 528 passed, 0 failed, 5 hardware skips.
- **Physical FLOW 8: NOT VERIFIED.** No device was connected.

## 2. Repository verification
Full detail is in `REPOSITORY_VERIFICATION.md`. In short:
- The branch is in sync with origin, and there were no tracked changes before tonight.
- The Hallmark session touched exactly `v3.js`, `v3.css` and `index.html`, checked change by change against `patches/hallmark_fixes.py`.
- `flow8/web_ui/` holds only source files and fonts.
- The hub serves a fixed route list, so `.hallmark/` cannot be reached over HTTP.
- No dependency manifests exist, and none were added.

## 3. Hallmark before / after

| Run | FAIL | REFLEX | WARN | Source |
|---|---|---|---|---|
| Baseline (before polish) | 74 | 88 | 12 | `before_console.txt` |
| After polish | 15 | 2 | 0 | `final_console.txt` |
| Closure (tonight, before C1-C4) | 15 | 2 | 0 | `closure_console.txt` |
| Closure (after C1-C4) | 15 | 2 | 0 | `closure_after_console.txt` |

The last run also shows 86 NOTE: one more spacing note than before, caused by C2's 10 px/8 px padding.

Every run used the live URL (`--url http://127.0.0.1:8855/v3/`), so CSS and fonts load. The disk render, which loads no CSS, is not used as evidence.

## 4. Remaining findings, classified

| Finding | Count | Class |
|---|---|---|
| 67: `.brand small` tracked 0.14em | 1 | B, intentional |
| 67: labels and controls tracked 0.04em | 13 | B, intentional hardware convention |
| 62: unknown slider thumb hidden | 1 | C, false positive |
| 38iii: `.page-head h1 i` | 1 | B, intentional |
| 39b: strip head 57 px tall | 1 | B, intentional |

Reasons, traceable to the source:
- **67, `.brand small`:** the "LIVE CONSOLE" line is part of the wordmark, which gate 67 lists as legal.
- **67, the 13 labels and controls:** these are `.state`, `.tool`, `.s-mute`, `.mini`, `.prov`, `.s-read .prov`, `.cue-tag`, `.s-head .num`, `.groups > span`, `.matrix th`, `.row label`, `.preset .cat` and the group MUTED label.
  - The uppercase labels follow the mixer's printed labels and the rev 7 reference, on the owner's instruction.
  - Gate 67 itself allows controls tracked 0.04em or less on an uppercase display. Labels fail it because the gate's limit for them is 0.03em.
  - Lowering the tracking from 0.04 to 0.03 purely to clear the count was not done; the task forbids closing findings for the number.
- **62:** the hidden thumb is the unknown-value state of a mixer control, not a scripted reveal. The console renders only from its script.
- **38iii:** the flagged text is the Thai page name next to the English one (a bilingual title), not an accented word.
- **39b:** the strip head is a two-line channel head (number and name), and its touch target is at least 44 px.

No finding is class A (genuine defect), D (owner decision) or E (needs backend or hardware data). The answers and dismissals already stamped in the CSS (41, F7, F19, F24) are unchanged.

## 5. Visual acceptance
- **Script:** `acceptance_check.py`.
- **Output:** `acceptance/` (100 PNGs) and `acceptance/results.json`.
- **Viewports:** 1280×800 (mouse), 1180×820, 1024×768, 768×1024 and 320×640 (touch), each in day and night.

**Faders**

| Check | Result | Status |
|---|---|---|
| Cap centre vs value, expected at 12 + v/127·(h−24) px from the well bottom | max error 0.5 px on every visible fader (8 per Mix view, 7 at 768, 2 at 320) | VISUAL VERIFIED |
| Cap inside its well | failed at 1024 (CH 1, selected, 1 px overhang); fixed by C1, now passes everywhere | VISUAL VERIFIED |
| Unknown cap parked at the bottom and dashed; known cap solid | all pass, including offline | VISUAL VERIFIED |
| Scale labels overlapping | 0 overlaps | VISUAL VERIFIED |
| Channel names covered (checked with `elementFromPoint`) | 0 | VISUAL VERIFIED |
| Resize 1280→1180→1024→1440→1280, checked 60 ms after each step (before the 150 ms re-render) | max error 0.5 px, all inside | VISUAL VERIFIED |

**EQ**

| Check | Result | Status |
|---|---|---|
| Axis labels on the log10 scale (`xOf`) | error under 0.05 % on every label | VISUAL VERIFIED |
| Labels shown, wider than 1100 px | 50, 100, 200, 500, 1k, 2k, 5k, 10k; 0 overlaps | VISUAL VERIFIED |
| Labels shown, 1100 px and narrower | 100, 1k, 10k (by design); 0 overlaps | VISUAL VERIFIED |
| Band colours, day | #46D16A, #3B9BF0, #B46CE0, #E6B83F (rev 7) | VISUAL VERIFIED |
| Band colours, night | one red, #FF7A6E | VISUAL VERIFIED |
| Freq and Q | 0 controls in the band cards; 8 "fixed" cells with lock icons | CODE + VISUAL VERIFIED |

**MAIN OUT and readouts**

| Check | Result | Status |
|---|---|---|
| MAIN OUT meter count | exactly 1, with `data-sid="main"`. The source is combined L+R, reported as the louder side (`audio_meter.py:35,43`), so no separate L/R meter is needed | CODE VERIFIED |
| MAIN OUT dead band | mute spacer hidden; readout shows `+0.0 SNT` | VISUAL VERIFIED |
| Meter content | empty: the rig has no USB audio stream, and no levels are injected | NOT VERIFIED (needs audio hardware) |
| Strip badge vs session provenance | 0 mismatches | TEST VERIFIED |
| Text contrast (probe-core, every text node) | 0 failures in 100 captures, day and night | VISUAL VERIFIED |
| Text below 12 px | 0 | VISUAL VERIFIED |

## 6. Responsive

| Check | Before fixes | After | Status |
|---|---|---|---|
| Page overflow (`documentElement`) | 0 | 0 | VERIFIED |
| Stage overflow at 320 | SENDS 237 px (deliberate sideways matrix), FX 65 px, OUTPUT 5 px | SENDS 237 px only (deliberate) | VISUAL VERIFIED |
| FX at 320 | 4th preset column and SNT badge cut off | 2-column grid (C2), nothing cut off | VISUAL VERIFIED |
| GEQ band width at 320 | 22 px, below the WCAG 2.5.8 minimum of 24 px | 27 px (C3) | VISUAL VERIFIED |
| LIMITER row at 320 | 1 px overflow: the range input kept its intrinsic width | 0 (C4) | VISUAL VERIFIED |
| Touch targets under 44 px | fader well 43.x px wide (136 px tall); GEQ bands 27 px at 320; mute groups 40×44 at 320 | unchanged; all at least 24 px (WCAG AA) | VERIFIED, noted |
| Clipped text | user channel names under a full CH label; the processor subtitle at 320 | unchanged; the channel label and the value stay whole | VERIFIED, noted |

## 7. Day / night
**VISUAL VERIFIED** for both themes:
- **Contrast:** 0 failures in either theme (50 captures each).
- **Focus-visible:** a 2 px `--sel` outline in both themes (teal by day, red by night).
- **Disabled:**
  - GO uses fill, ink and cursor (Hallmark 39a).
  - SAVE CURRENT MIX is `disabled` while locked.
  - Strip MUTE is `aria-disabled` while offline.
- **Selected:** day uses a teal fill. Night uses an outline plus a tint, so solid red means MUTED only.
- **Meters:** in night mode the meter zones collapse to `--ink-2` (one hue).
- **Warnings:** day uses the amber offline note; night uses its own warning tokens.

## 8. Interaction
Sources: `interaction_e.py` and `interaction_e.json`, plus `ui_refine_2026-11-28/interaction_check.py`.

| Check | Result | Status |
|---|---|---|
| One arrow key on a fader | 1 POST, 1 hub `setFader`, 1 MIDI message (`CC ch2 7 97`) | TEST VERIFIED |
| One click on MUTE | 1 POST, 1 `setMute`, 1 MIDI message | TEST VERIFIED |
| Mouse drag (10 moves over 300 ms) | 1 `beginGesture`, 6 throttled `setFader`, 1 `endGesture` (one undo step) | TEST VERIFIED |
| UNDO / REDO | hub `undo` sends `CC ch1 7 101` (previous value); `redo` sends `CC ch1 7 68` | TEST VERIFIED |
| LOCKED (held from the keyboard) | fader key, fader drag, MUTE and EQ node send 0 POSTs and make 0 hub calls | TEST VERIFIED |
| NO MIXER (real `reconcile_connection()` path) | the same controls send 0 POSTs and make 0 hub calls; every readout shows `--` | TEST VERIFIED |
| Reconnect with no new commands | 8/8 readouts `--`, badges `UNK`, mutes `MUTE ?` | TEST VERIFIED |
| Keyboard focus kept across a re-render | `tests.test_v3_keyboard_focus` (3 tests) passes in the suite | TEST VERIFIED |
| Touch tap on a mute group | opens the group editor (button 84×44) | TEST VERIFIED |
| Hover | border `#92999C`; a selected control keeps its teal border | TEST VERIFIED |

All controls still go through the same `action()` and `gesture()` paths in `v3.js`. Tonight's work changed no JavaScript.

## 9. MIDI regression
**TEST VERIFIED.**
- **What drives it:** `ui_refine_2026-11-28/payload_check.py` exercises the keyboard, a mouse drag, MUTE twice, a send cell, an FX preset and variant, the GEQ and a touch MUTE.
- **Result:** 12 commands and 12 MIDI messages.
- **Comparison:** the serialised sequence of commands, status codes and MIDI messages is byte-identical to the baseline (`payload_before.json` vs `payload_after_acceptance.json`, 1037 bytes).
- **Baseline stability:** the baseline was identical across two runs.

## 10. Tests
**TEST VERIFIED.**
- **Command:** `python -m tools.run_tests_no_hw`.
- **Result:** 533 ran, 528 passed, 0 failed, 0 errors, 5 skipped (hardware), 0 attempted physical port opens (`run_tests_no_hw_acceptance.log`).
- **No existing test was edited.**
- **No linter or type checker** is configured in this repo.

## 11. Design system consistency

| Source | Palette | Note |
|---|---|---|
| `DESIGN.md` | navy "Night Console" (owner decision 2026-11-26) | also governs the v2 console |
| `v3.css` | graphite / teal (rev 7 reference) | — |

The blueprint records the open question:
- `mix-workspace-blueprint.md:141`: "The token values in DESIGN.md … stay navy until the owner approves this mapping".
- `:424`: decision 8 is still open.
- `:437`: "charcoal palette in `v3.css` only".

There isn't enough evidence to rewrite `DESIGN.md`, so it was not changed; it is listed under owner decisions below. **CODE VERIFIED:** the semantic roles match across both systems: selection teal, MON green, FX violet, warning amber, fault red, and the provenance vocabulary.

## 12. Owner decisions
Nothing below was changed.

### R7-2: LOCK outline
- **Current behaviour:** LOCK is neutral grey in the LIVE slot.
- **Evidence:** blueprint 0d line 40 ("teal outline"); `.safety.lock` in `v3.css`.
- **User impact:** LOCK reads like UNDO/REDO, so it is harder to find in a hurry.
- **Risk:** low (visual only).
- **Recommendation:** a teal outline at rest; the amber locked state stays.
- **Status:** REQUIRES OWNER APPROVAL.

### Default channel names
- **Current behaviour:** "CH 5/6" sits over "Channel 5/6", and the second line truncates at 768 and 1024.
- **Evidence:** `stripEl` uses `chName(c)`; the acceptance run's `clipped` list.
- **User impact:** a redundant line with ellipses.
- **Risk:** low.
- **Recommendation:** hide the name line when it equals the default; show custom names.
- **Status:** REQUIRES OWNER APPROVAL (it changes which names appear).

### `DESIGN.md`: navy vs graphite
- **Current behaviour:** two palettes, both in use (v2 navy, v3 graphite).
- **Evidence:** blueprint :141, :424, :437; `DESIGN.md:73`.
- **User impact:** design tools read the navy system when working on v3.
- **Risk:** medium (future drift).
- **Recommendation:** either add a "v3 console (rev 7)" token section to `DESIGN.md` and keep navy for v2, or move both consoles to graphite.
- **Status:** REQUIRES OWNER APPROVAL.

### V3-D10: EQ provenance
- **Current behaviour:** the hub reports one EQ provenance per channel, read from the LOW band (`lan_hub.py:582`).
- **Evidence:** the note in `tests/test_v3_keyboard_focus.py`; the defect register.
- **User impact:** with LOW unknown, the other bands show as unknown and each edit restarts at 0 dB.
- **Risk:** medium.
- **Recommendation:** per-band `eqProvenance` in the session (a backend change).
- **Status:** BLOCKED (backend change, protected layer).

### Brand line
- **Decision:** the owner locked the branding in the round 3 instruction: FLOW 888 for the product, FLOW 8 for the hardware, LIVE CONSOLE for the console label.
- **Current UI:** matches the decision.
- **Status:** CLOSED.

### A1: evidence folder
- **Current behaviour:** `disk_render_no_css/` was committed holding only Hallmark's `.gitignore`.
- **Evidence:** `git ls-files`.
- **User impact:** the evidence is missing on GitHub.
- **Risk:** none.
- **Recommendation:** drop that `.gitignore`, or the whole folder, in the next commit.
- **Status:** owner decision (it needs a commit).

## 13. Files changed tonight

**`flow8/web_ui/v3/v3.css`:** +14 lines, 0 removed (`git diff --stat`). All appended (C5, the unknown-slider focus ring, added in round 3):
- **C1:** fader cap width `min(46px, calc(100% - 4px))`.
- **C2:** `min-width: 0` on grid children, plus a 2-column FX preset grid at 400 px and below.
- **C3:** GEQ gap 2 px and tighter panel padding at 400 px and below.
- **C4:** `input[type=range] { min-width: 0 }`.

**New audit files in `docs/audit/hallmark_2026-11-28/`:**
- `REPOSITORY_VERIFICATION.md` and `FINAL_ACCEPTANCE_REPORT.md`
- `acceptance_check.py` and `acceptance/`
- `interaction_e.py` and `interaction_e.json`
- `closure_console.txt` and `closure_after_console.txt`
- `run_tests_no_hw_acceptance.log`
- `patches/`

**New payload record:** `docs/audit/ui_refine_2026-11-28/payload_after_acceptance.json`.

**Not changed:** `v3.js`, `index.html`, any Python file, any test, `DESIGN.md`, `PRODUCT.md`, `.gitignore`.

**Backup:** the pre-fix CSS is in the session scratchpad (`v3.css.pre-acceptance`).

## 14. Risks and limitations
- **No hardware:** there was no physical FLOW 8, USB audio or BLE device. Meters, LIV (OBSERVED) values from MIDI IN and BLE routing are NOT VERIFIED on hardware.
- **Emulated touch:** touch is Chromium emulation (`has_touch`), not a real iPad.
- **Gate 67 stays failing:** Hallmark will keep 14 FAILs while the hardware-label convention stands. This is a recorded exception, not a pass.
- **ResizeObserver:** the fader fix relies on `ResizeObserver`, which all current Safari, Chrome and Edge versions support. Where it is missing, the existing 150 ms re-render still corrects the cap positions.

## 15. Recommended next tasks
1. Owner answers on R7-2, default names, the `DESIGN.md` palette and the brand line (section 12).
2. Commit tonight's CSS (C1-C4) and audit files on the branch, then open the PR.
3. A backend task for V3-D10 (per-band EQ provenance), in its own reviewed change.
4. Hardware Stage 1 with a connected FLOW 8 (per-stage "GO"), then a touch pass on a real iPad.

| Verification type | Status |
|---|---|
| CODE VERIFIED | yes |
| VISUAL VERIFIED | yes (Chromium, 5 viewports, day and night) |
| TEST VERIFIED | yes (528 passed; payloads byte-identical) |
| HARDWARE VERIFIED | **no** (no FLOW 8 connected) |
