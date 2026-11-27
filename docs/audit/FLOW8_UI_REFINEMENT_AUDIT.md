# FLOW 888 v3 — UI/UX Audit and Refinement (2026-11-28)

- **Scope:** the real v3 console (`flow8/web_ui/v3/`), every page: MIX (SOURCE, EQ, COMP, FX SEND, MON SEND), SENDS matrix, CHANNEL, FX, MY MON, SHOW, OUTPUT, SETUP; connected and offline states.
- **Base:** `6a9b8c6` plus the uncommitted working tree of 2026-11-27 (TASK 01–05). Nothing committed.
- **Viewports:** 1440×900 (mouse), 1180×820, 1024×768, 768×1024, 390×844 (touch emulation, coarse pointer). Extra fold check at 1366×768.
- **Rig:** real `Flow8LanHub` + `Flow8Service` in-process, MIDI OUT = repo fixture `fake_open_port`. winmm `midiOutOpen`, `midiInOpen`, `midiOutShortMsg` and `midiOutLongMsg` raise if called; every run ends with **0 physical MIDI calls**. No FLOW 8 was connected.
- **State shown:** a realistic soundcheck state sent through the hub (`seed()` in `ui_refine_2026-11-28/ui_harness.py`): CH 1–4 and MAIN faders, CH 1 EQ/low cut/comp, one MON send, one GEQ band, FX 1 preset, two cues. Everything else stays UNSYNCED. No meter data is injected: meters are honestly empty because no USB audio stream exists in the rig.
- **Judged against:** `PRODUCT.md`, `DESIGN.md` (12 px type floor, 44 px coarse-pointer targets, provenance rules, colour-is-meaning), `design-plans/flow888-v3/mix-workspace-blueprint.md` rev 7, and WCAG 2.2 AA.
- **Evidence:** `docs/audit/ui_refine_2026-11-28/` — `before/` and `after/` (60 screenshots each, `metrics.json`), `interaction_check.json`, `u1_fold_check.txt`, `run_tests_no_hw.log`.

## Skills used

| Skill | Used for |
|---|---|
| `impeccable` (context loader, `audit`, `polish`, `operate`, `craft-floor` references) | Loaded PRODUCT.md / DESIGN.md, audit dimensions, the Operate-mode bar, the polish order (misleading state first), and the craft floor before editing |
| `ux-ui-audit` (`probe-core.js`) | Text-contrast measurement on all 120 captures; rule that every finding carries a measurement |
| `task-observer` | Session observation workspace (no new skill observations written this pass) |

`frontend-ui-engineering`, `design-taste-frontend` and the other listed design skills were not invoked; the work needed no landing-page or new-component guidance. No linter, formatter or type checker exists in this repo (CLAUDE.md), so none was run.

---

## Part A — Audit findings

Severity: **P1** misleading state, blocked live task, or WCAG AA failure · **P2** major UX or consistency · **P3** polish.

| # | Sev | Page · component | Finding | Evidence (before) |
|---|---|---|---|---|
| F1 | P1 | MIX · strip head, 1024 | Channel identity truncated: `CH 5…`, `CH 7…`, `USB…`. 5/6 and 7/8 look the same | `clipped` in `before/metrics.json` 1024/mix-*; `before/1024-mix-eq.png` |
| F2 | P2 | MIX · strip provenance badge | Set at 11 px, below the DESIGN.md 12 px floor (8 per Mix capture, 165 instances total) | `small` in `before/metrics.json` |
| F3 | P1 | MIX · 1366×768 / 1024×768 (U-1), 1180×820 offline | Strip MUTE row, PRESET and FX 2 below the fold; needs a scroll during a show | `before/1024-mix-eq.png`, `before/1180-mix-offline.png` |
| F4 | P1 | MIX · EQ band cards, 1024 | Knob covers the gain value (`+1.9 d` cut) | `before/1024-mix-eq.png` |
| F5 | P1 | Header · 768 (iPad portrait) | LOCK (41×44) and MUTE ALL squeezed to icons, words clipped. DESIGN.md: "MUTED, LOCKED … carry text" | `clipped` + `targets44` 768/*; `before/768-mix-eq.png` |
| F6 | P1 | MIX · mute groups | Targets 40×44 (1180, 1024), 31×44 (768), under the 44 px coarse-pointer rule | `targets44` 1180–768 |
| F7 | P2 | MIX/CHANNEL · EQ while unknown | Unknown EQ drawn like a value: solid teal nodes on 0 dB and knob pointers at 0 dB (Unknown-Reads-Unknown rule) | `before/1180-mix-offline.png` (real `reconcile_connection()` path) |
| F8 | P2 | SHOW · cue list | NOW used the OBSERVED (green, "LIV") badge class and NEXT the COMMANDED class: cue position dressed as provenance; NOW also had a 3 px coloured left bar | `v3.js` pageShow (before) |
| F9 | P2 | MIX/CHANNEL · EQ graph | Axis labels are SVG text inside `preserveAspectRatio="none"`: squashed to ~10 px tall at 1180, stretched on CHANNEL; band 1 sits on the `0`/`-6` labels | `before/1180-mix-eq.png`, `before/1180-channel.png` |
| F10 | P2 | All pages · channel names | Four schemes for one thing: `CH 5/6` (Mix), `05 Channel 5/6` (Sends), `05` (My Mon), `5` (Channel picker, where `7` meant USB/BT) | page sources |
| F11 | P2 | All · desktop mouse | No hover feedback on any control at 1440 (no `:hover` rule in `v3.css`) | `v3.css` (before) |
| F12 | P3 | SENDS · 390 | Matrix wider than the phone (167 px horizontal scroll) | `stageOverflowX` 390/sends |
| F13 | P2 | MY MON · 1024 | Strip 07 hidden under the sticky master; names truncated | `before/1024-stage.png` |
| F14 | P2 | MIX · 768 | Mix cards wrap `MON / 1` and `+0.0 / dB` over three lines; 7th strip off-screen | `before/768-mix-eq.png` |
| F15 | P3 | CHANNEL · EQ header | FLAT and badge in the opposite order to the MIX EQ view | page sources |
| F16 | P3 | OUTPUT · GEQ | No 0 dB reference in the band wells | `before/1180-output.png` |
| F17 | P3 | FX · VARIANT | A and B segments have no divider; reads as one blank box when unknown | `before/1180-fx.png` |
| F18 | P2 | MIX · fader, EQ node, send cell (keyboard) | After one arrow-key step the page re-renders and focus falls to `<body>`; the 2nd and 3rd presses do nothing (WCAG 2.1.1, 2.4.3). Registered as V3-D09 | 3 presses → 1 command, `activeElement` BODY (all three controls) |
| F19 | P3 | Hub session · EQ provenance | `lan_hub.py` reports one `eqProvenance` per channel, read from LOW. With LOW unknown, other bands show unknown and each edit restarts at 0 dB. Backend; **not fixed** (V3-D10) | `lan_hub.py` `eq_prov = self._param_raw(f"ch{idx}.eq_low", 64)[1]` |
| F20 | P2 | Design system | `v3.css` tokens (graphite `#0E1113`/`#15181A`, teal `#35B4B0`) follow blueprint rev 7, but `DESIGN.md` frontmatter still names the navy "Night Console" (`#06111A`, `#1FE0D0`). Two sources of truth. **Not changed: owner decision** | `DESIGN.md` vs `v3.css:7-17` |

What already worked (measured, kept as is):
- **Contrast:** `probe-core.js` measured every text node on all 60 captures per run (141 on Mix at 1440); **0 failures** before and after.
- **No overflow of the page itself** at any size (`docOverflowX` = 0 on all 120 captures).
- **Provenance vocabulary** present on every value: `--` with a dashed edge, a dashed parked fader cap, and `MUTE ?` when unknown; after a real disconnect everything reads UNK.
- **Safety controls:** hold-to-arm on LOCK (0.8 s) and MUTE ALL (0.6 s) with a progress bar; nothing sends while LOCKED or with NO MIXER (TASK 03 tests).
- **No page errors** on any capture.

## Part B — UI improvements

Files changed (UI only): `flow8/web_ui/v3/v3.js`, `flow8/web_ui/v3/v3.css`, `flow8/web_ui/v3/index.html`. Added: `tests/test_v3_keyboard_focus.py`. Backup of the pre-pass files: scratchpad `v3_backup_2026-11-28/`.

| # | Change | Component | Why |
|---|---|---|---|
| F1, F2 | Provenance badge moved from the strip head to the readout row (`+0.0 SNT`), 12 px; the head keeps the full channel label. The badge follows the value during a drag or keyboard step | `stripEl`, `fader().paint` | The operator must tell 5/6 from 7/8 at a glance; the badge describes the number, so it sits beside it (blueprint rev 7, R7-4) |
| F3 | Short landscape screens (≥1001 px wide, ≤860 px tall): one-line mix cards, a 52 px bar and 48 px tabs (still ≥44), tighter strip head | `@media (min-width:1001px) and (max-height:860px)` | MUTE and every mix must be reachable without scrolling during a show |
| F4 | Band knob hidden ≤1100 px; the gain number stays | `.band .knob` | The number is the reading; the knob only repeats it |
| F5 | ≤1000 px: UNDO/REDO become 52 px icon buttons with `aria-label`; the USB MIDI chip hides (DESIGN.md: the link pill carries state below desktop widths); LOCK and MUTE ALL never shrink below their words (≥761 px) | header | Safety state is never colour or icon alone |
| F6 | Mute groups 2×2 in the side column (84×44 measured) | `.grps` | 44 px coarse-pointer rule |
| F7 | Unknown EQ: dashed grey nodes, empty dashed knob ring with no pointer | `.eq-node:not(.on)`, `knob()` | Unknown-Reads-Unknown |
| F8 | Cue NOW/NEXT get their own `.cue-tag` (teal NOW, grey NEXT); the coloured left bar removed | `pageShow` | Provenance colours stay reserved for provenance |
| F9 | EQ axis labels rendered as 12 px HTML over the SVG; grid strokes `vector-effect: non-scaling-stroke`; 70-unit gutters on both sides | `eqGeometry` | Labels hold the type floor; band 1 clears the scale; band 4's touch circle stays inside the graph on a phone |
| F10 | One label everywhere, as printed on the mixer: `CH 1 … CH 5/6, CH 7/8, USB/BT` (Sends rows, My Mon strips, Channel title; Channel picker `1 2 3 4 5/6 7/8 USB`) | `chLab`/`LAB` | One name per thing; `7` no longer means USB |
| F11 | Hover (pointer devices only): border lifts to `--ink-3`; selected, state-coded and disabled controls keep their own border. Pressed: `brightness(1.15)` | end of `v3.css` | Mouse users see what will respond |
| F13 | ≤1100 px: My Mon "I am" column 240 px | `.mymon` | All 8 strips visible at 1024 |
| F14 | 761–1000 px: mix cards one block, no icons, nowrap; side column 148 px; strips min 76 px with a tighter fader grid | tablet media block | All 7 strips and full mix names fit at 768 |
| F15 | Channel EQ header: badge, then FLAT (as on MIX) | `pageChannel` | Same order on both EQ views |
| F16 | GEQ wells get a 0 dB line | `.geq-well::after` | A reference for reading a band |
| F17 | Divider between VARIANT A and B | `.seg` | Two choices read as two |
| F18 | Stable ids `fdr-<strip>`, `eqn-<band>`, `cell-<ch>-<mix>` so `render()` gives focus back | `fader`, EQ node and cell templates | Keyboard users can step a control repeatedly |

**Not changed on purpose:**
- **F12:** the phone SENDS matrix keeps 110 px cells and scrolls sideways. Squeezing it to fit gave 39 px horizontal-drag cells (measured), which are unusable for a 127-step drag. On a phone the per-channel FX SEND / MON SEND views on MIX are the better path.
- **F19, F20:** backend and owner decisions.

Before and after, same state and viewport:

| | Before | After |
|---|---|---|
| iPad 1024×768 Mix | `before/1024-mix-eq.png` (strip labels cut, knob over gain, MUTE/PRESET/FX 2 below the fold) | `after/1024-mix-eq.png` (full labels, everything on one screen, fader well 136 px) |
| iPad 1180×820 offline | `before/1180-mix-offline.png` (MUTE row cut, unknown EQ in teal) | `after/1180-mix-offline.png` (fits, dashed unknown EQ) |
| iPad portrait 768 | `before/768-mix-eq.png` (LOCK/MUTE ALL icon-only, 7th strip off-screen) | `after/768-mix-eq.png` |
| My Mon 1024 | `before/1024-stage.png` | `after/1024-stage.png` |

## Part C — Testing

| Check | Result | Status |
|---|---|---|
| Lint / format / type check | None configured in the repo (CLAUDE.md: "No linter or formatter is configured"; plain JS, no TypeScript) | NOT RUN (none exists) |
| New test `tests.test_v3_keyboard_focus` | Before the fix: 3/3 failed (1 of 3 presses sent). After: **3/3 pass** | TEST VERIFIED |
| Full suite `python -m tools.run_tests_no_hw` | **533 ran, 528 passed, 0 failed, 0 errors, 5 skipped (hardware), 0 physical port opens.** Previous baseline 530/525/0/5 (TASK 05); +3 = the new focus tests. No pre-existing failures. Log: `ui_refine_2026-11-28/run_tests_no_hw.log` | TEST VERIFIED |
| Measurement harness, 60 captures × 2 | Clipped text 64 → 35 (remaining: user channel names `Channel 5/6` and `USB/BT Return` under a full CH label); text < 12 px 165 → **0**; coarse targets < 44 px 108 → 14 (9 GEQ bands at 390 px, 30×202, pass WCAG 2.5.8 at 24 px; fader well 43.x px rounding); targets < 24 px 0 → 0; contrast failures 0 → **0**; page errors 0 → **0**; stage overflow 3 → 1 (F12, deliberate) | VISUAL VERIFIED |
| Fold check (U-1) | 1366×768 and 1024×768: strip MUTE bottom 734 px, PRESET 741, FX 2 752, stage scroll 0; 1180×820: 786/793/804, scroll 0 | VISUAL VERIFIED |
| Interaction check (`interaction_check.json`) | Keyboard ArrowUp on CH 5/6 → `setFader ch5 value 1`, readout `-69.3 SNT`; mouse drag on CH 2 → `beginGesture, setFader×2, endGesture`, readout follows; hover border `rgb(146,153,156)`, selected keeps teal `rgb(53,180,176)`; EQ ArrowUp → `setEqBand low_mid 72`; axis labels 12 px; touch tap on an empty group opens its editor (84×44) | TEST VERIFIED |
| Physical MIDI | 0 calls across every run | VERIFIED |

## Part D — Remaining issues

- **F19 / V3-D10 (backend):** per-band EQ provenance. Until the hub reports it, LOW MID/HI MID/HIGH edits on a channel whose LOW band is unknown restart at 0 dB.
- **F20 (owner):** DESIGN.md tokens and v3 tokens disagree (navy vs graphite). Either update DESIGN.md to the rev 7 palette or retune `v3.css`. Not touched.
- **R7-1…R7-4** in the rev 7 blueprint are still open. This pass applied R7-4 (badge beside the value) because it was needed to fix F1; revert is one template change if the owner declines.
- **V3-D07** (LOCK lost on reload) and **V3-D08** (Back button): unchanged, owner decision / UX phase.
- **Phone:** the SENDS matrix scrolls sideways (deliberate, F12); 9 GEQ bands are 30 px wide at 390 px.
- **Night mode** was not re-captured in this pass. The new rules use existing tokens only (`--sel`, `--ink-3`, `--line-2`), which night mode redefines, but it is NOT VISUALLY VERIFIED.
- **Real touch hardware** (an actual iPad) not used: touch is Chromium emulation (`has_touch`, coarse pointer).
- **Meters:** no USB audio in the rig, so meter rendering is unchanged and was not exercised.

## Part E — Verification status

| Level | Status |
|---|---|
| CODE VERIFIED | Yes: every change is in the three v3 files listed; no change to `flow8/*.py`, hub, safety layer, allowlist, MIDI mapping, transport router, BLE or port 8844. Payload shapes unchanged (interaction check, existing payload tests). |
| VISUAL VERIFIED | Yes, in Chromium at 1440, 1366, 1180, 1024, 768 and 390 px, connected and offline. Night mode: not verified. |
| TEST VERIFIED | New focus test 3/3; full suite 528 passed, 0 failed, 5 hardware skips. |
| HARDWARE VERIFIED | **No.** No FLOW 8 was connected. Nothing in this report is confirmed on the mixer. |

---

# Pass 2 (2026-11-28): design-agency review

## Skills actually invoked

| Requested | Status | Used for |
|---|---|---|
| frontend-design | Invoked | Art direction check: the brief pins the direction (rev 7 reference); uppercase panel labels kept as the mixer's printed labels |
| ui-ux-pro-max | Invoked (`search.py --domain ux`, 3 queries) | No colour-only state; 8 px touch spacing; 2 px focus ring at 3:1 |
| design-taste-frontend | Invoked, app-screen route (`references/app-screens.md`, `lint.mjs --app`, `inspect.mjs --app` with the Playwright Chromium) | Token and state audit, edge-text and h1 checks |
| impeccable | Invoked (pass 1; its context and craft floor still apply) | Final refinement rules |
| design-critique / design-reviewer | **Not installed.** Substitute: `impeccable-finish-reviewer` agent, an independent read-only review against the rev 7 contract | 12 findings, triaged below |
| web-design-guidelines, react-best-practices, accessibility-auditor | **Not installed.** v3 is plain JS, not React. Accessibility measured with ux-ui-audit `probe-core.js` plus the harness | — |

## Findings and fixes

| # | Source | Finding (evidence) | Fix |
|---|---|---|---|
| P2-1 | design-taste lint | 25 hard-coded state colours outside the tokens; night mode leaked green (CONNECTED border `#1F5A27`), pink mutes and a light grey fader cap; the offline note used the old DESIGN.md amber `rgba(255,176,32)` | State-tint tokens (`--ok/warn/bad-tint/-line`, `--mute-*`, `--muteall-*`, `--cap*`, `--meter-off`, `--on-sel`, `--on-amber`, `--sel-strip`) with night values |
| P2-2 | harness night captures (new) | Night text failed contrast: `--ink-3 #9A2C24` 2.51–2.74:1, `--ink-2 #C2392F` 3.57–3.89:1, `--mix-fx` 3.81:1 (225 failing text nodes over 15 night captures) | Night inks `#FF7A6E / #E85A4E / #D8564A`, measured 4.87–8.2:1 on every night surface; `--mix-fx #E0483C`. Result: **0 contrast failures** in 75 captures |
| P2-3 | ui-ux-pro-max (colour only) | Strip mute ON read "MUTE" like OFF; a lit mute group showed only its letter in red | Strip label `MUTED` when muted; lit group shows `MUTED` under its letter |
| P2-4 | design-taste inspect | Brand text 8 px from the screen edge; Mix page had no `h1` | Brand inset to 16 px; visually hidden `h1` naming the workspace |
| P2-5 | own critique | MAIN OUT panel had a ~60 px dead band (mute spacer under a strip with no mute) | Spacer removed; the master fader takes the height |
| R1 | reviewer | Unknown sliders (LIMITER, FX PARAM 1, LOW CUT, COMP) showed a thumb at a made-up position | Thumb hidden while unknown; dashed edge |
| R2 | reviewer | MAIN mix card showed `+0.0 dB` without a badge | Badge on every known mix value |
| R3 | reviewer | Send cells showed a bare number | Badge in each cell; it turns SNT during a drag or keyboard step |
| R4 | reviewer | SETUP showed raw keys `outputPad`, `footswitch`, `hwSnapshots` (`lan_hub.py:80-82`) | Names: Output pads, Foot switch mode, Mixer memory snapshots |
| R5 | reviewer | Night: selection and MUTED were the same solid red block | Night selection is an outline on a tint; solid red fill now means MUTED only |
| R6 | reviewer | NEXT cue used the dashed border that means "unknown" everywhere else | Solid border; the NEXT tag says it |
| R7 | reviewer (contract) | Per-band EQ hues from rev 7 0d missing; curve and nodes used two near-identical teals | `--band-1..4` (#46D16A, #3B9BF0, #B46CE0, #E6B83F) on nodes, band chips, knob arcs and the CHANNEL legend; curve on `--eq`; night collapses them to one red |
| R8 | reviewer (contract) | EQ grid had 3 lines; 300 Hz and 1.5 kHz could not be placed | Log grid (minor lines 30–9k), labels 50/100/200/500/1k/2k/5k/10k; minor labels hidden ≤1100 px |
| R9 | reviewer (contract) | FX mix cards showed UNK while the FX preset was known | FX card with an unknown level shows the preset name and its badge (`CHURCH SNT`) |
| — | copy | "2 step(s) NOT SET" | Proper plural |

**Not taken from the review:**
- **R10 (teal outline on LOCK):** depends on R7-2, which is still an open owner decision.
- **R11 (hide default names such as "Channel 1" under "CH 1"):** changes what names the app shows; owner decision.
- **R12 moon icon:** the night toggle is the text "NIGHT"; the glyph the reviewer saw is the settings gear, so the finding is wrong.
- **Reviewer's risk note:** R7 contradicts older blueprint sections (lines 107, 223, 412) that reject band hues. Rev 7 0d says it governs, and the owner called the image final. Revert is four token values if the owner prefers one hue.

## Verification (pass 2)

| Check | Result | Status |
|---|---|---|
| Full suite `tools.run_tests_no_hw` | 533 ran, 528 passed, 0 failed, 0 errors, 5 hardware skips, 0 physical port opens (`run_tests_no_hw_pass2.log`) | TEST VERIFIED |
| Harness, 75 captures (60 day + 15 night, 5 widths) | Contrast failures **0**; text <12 px **0**; page errors **0**; physical MIDI calls 0; stage overflow only 390 SENDS (deliberate, F12) | VISUAL VERIFIED |
| Interaction check | Keyboard step `-69.3 SNT` (1 setFader); drag `beginGesture, setFader×2, endGesture`, readout `+6.2 SNT`; hover border `rgb(146,153,156)`; group 84×44 opens editor on tap | TEST VERIFIED |
| taste `lint.mjs --app` | 0 FAIL, 16 WARN. The WARNs are inset state bars (DESIGN.md shadow vocabulary) and the literal word "unlock" in "Hold LOCK to unlock" | defended |
| taste `inspect.mjs --app` | 1 FAIL, 1 WARN. FAIL: at 390 px the 5th button of the sideways-scrolling channel row is cut at the edge, which is how a horizontal scroller shows there is more. WARN: LIVE CONSOLE / MUTE GROUPS uppercase, copying the hardware's printed labels as the brief asks | defended |
| Night mode | Captured and measured (was NOT VERIFIED in pass 1) | VISUAL VERIFIED |
| Hardware | No FLOW 8 connected | **NOT VERIFIED** |

Evidence: `docs/audit/ui_refine_2026-11-28/pass2/` (75 PNG + `metrics.json`), `.taste-skill/v3-pass2-before|after|final/` (inspector screenshots and `report.json`).
