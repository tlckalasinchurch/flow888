# FLOW 888 v3: Mix Workspace blueprint (Phases 0-2)

Status: PROPOSAL, **revision 7 (2026-11-27): final approved visual direction**. Mockup awaiting owner
review. No product source has been edited for revision 7; source changes wait for explicit approval
of the mockup. Section 0d is the governing section; earlier sections hold where 0d is silent.

## 0d. Revision 7: the owner's FINAL approved visual direction (2026-11-27)

Master visual reference: `design-plans/flow888-v3/reference-rev7.png` (the owner's image, saved
unchanged). Owner instruction: reproduce it closely (layout, proportions, three-column console,
top toolbar, left processing panel, large central EQ, fader section, right Main / Monitor / FX column,
dark hardware surfaces, compact rectangular controls, teal selection, segmented LED meters,
typography, spacing, borders, density); do not reinterpret it; adapt it only to the FLOW 8 hardware
and existing v3 functionality; keep business logic, MIDI mapping, USB/BLE transport, transport router
and safety layer unchanged.

Mockup for review: `mix-workspace-mockup-rev7.html`; screenshots
`shots-rev7/mockup-rev7-ipad-1180x820.png` (primary) and `shots-rev7/mockup-rev7-ipad-1024x768.png`.
Measured (headless Chromium, 2026-11-27): no horizontal or vertical overflow and no clipped control at
either size; fader zone 183 px at 1180x820 and 158 px at 1024x768 (DESIGN.md minimum 120 px).
Fader scale, EQ centres and meter scale use the same formulas as `v3.js` (`dbText`, `EQ_BANDS`,
`meterFrac`); values in the mockup are sample values.

### Reproduced from the reference

| Zone | Reference | Mockup rev 7 |
| --- | --- | --- |
| Toolbar (56 px) | brand + LIVE CONSOLE; CONNECTED (green outline, ring icon); MIDI; UNDO; REDO (dimmed); LIVE (teal); settings; menu | same order and shapes; FLOW 888 brand; USB MIDI; LOCK in the teal button's place; MUTE ALL; settings |
| Tabs (50 px) | 6 icon tabs; MIX = teal outline on a teal tint | identical |
| Left column | channel header with chevron; icon list SOURCE, GATE, EQ (teal fill), COMP, FX SEND, MON SEND, CHANNEL; source card; LINK, PRESET | channel header; same list without GATE, buttons 52 px; MUTE GROUPS A-D; PRESET |
| EQ workspace | EQ tab, "4-BAND PEQ", graph 20 Hz-20 kHz ±12 dB with log grid, curve and fills coloured per band, nodes 1-4 coloured; 4 band cards (number chip, name, Freq / Gain / Q, knob) | identical composition and colours; FLOW 8 centres; Freq and Q show a lock; badge (SNT) and FLAT where EQ ON was |
| Fader bank | 8 strips: CH n + name, scale, segmented meter, fader, dB readout, M and S; selected strip teal outline and tint | 7 strips (FLOW 8): same parts; one MUTE button; badge after the readout |
| Right column | MAIN OUT: L R meter, fader, MAIN (teal), 0.0 dB, MUTE; MON 1, MON 2, FX 1, FX 2 cards with mini meter, value or preset, chevron | MAIN OUT: one MAIN L+R meter, fader, MAIN (teal), 0.0 dB; same four cards with value or FX preset name and chevron, no mini meter |

### Adapted to the FLOW 8 (reference element → what the mockup does, and the evidence)

| Reference element | Mockup | Evidence |
| --- | --- | --- |
| Brand "FLOW 8 CueAir Pro v3" | **FLOW 888** | `PRODUCT.md` naming policy (owner decision 2026-11-20): UI uses FLOW 888; "CueAir" never in user-facing copy. **Needs the owner to confirm this stays** (decision R7-1) |
| LIVE button | LOCK (hold), same position and teal outline | no "live mode" exists; LOCK is the existing live-safety control |
| Menu (hamburger) | MUTE ALL (hold) | no menu content exists; MUTE ALL is an existing safety control and must stay one tap from the top bar |
| GATE | not drawn | the FLOW 8 has no gate (capability matrix) |
| EQ ON toggle, band ON pills | provenance badge (SNT / LIV / UNK) and FLAT | EQ and band bypass have no documented MIDI address |
| Editable Freq and Q (100 Hz, 315 Hz, 2.80 kHz, 8.00 kHz; Q 0.7-1.2) | fixed 20 Hz, 300 Hz, 1.5 kHz, 20 kHz; "fixed" Q; lock glyph | `v3.js` `EQ_BANDS` (manufacturer centres); C-04: frequency and Q not possible |
| Curve / headphone / RTA buttons | not drawn; graph takes the width | no analyser, no cue bus |
| Solo (S) | not drawn | not in the allowlist, LAN-locked (`LAN_LOCKED_FEATURES["solo"]`); owner decision: left out |
| 8th strip "CH 8 Pad" | 7 strips: CH 1-4, CH 5/6, CH 7/8, USB/BT | FLOW 8 has 7 input strips |
| Fader scale +6 … -40 | +10, 0, -12, -24, -40, -∞ | FLOW 8 fader curve (`dbText`: raw 127 = +10 dB, 101 = 0 dB); +6 and -6 are too close to label |
| Meter on every strip | ch 1-6 meters; USB/BT shows the "no meter" texture | `audio_meter.py`: ch 7 is not in the USB capture |
| MAIN L/R meter | one "MAIN L+R" meter | `audio_meter.py` sends Main as one value (`main`) |
| MAIN MUTE | not drawn | `set_mute` accepts ch 1-7 only; MUTE ALL is in the toolbar |
| Mini meters on MON / FX cards | not drawn | no meter source for buses |
| FX names "Hall", "Delay" | FLOW 8 preset names (e.g. CHURCH, DELAY 1/2) | `v3.js` `FX_NAMES` |
| LINK | not drawn | stereo link has no verified MIDI address (`LAN_LOCKED_FEATURES["stereoLink"]`) |
| Source card (left foot) | mute groups A-D | groups are existing v3 functionality (D02 fix: lamp from hub state, dashed = unknown) |
| MON identity in amber/yellow | MON stays emerald (#34D399) | DESIGN.md Colour-Is-Meaning: amber = caution |
| Plain dB values | dB value + provenance badge | product rule: only OBSERVED / COMMANDED values are shown as values |

### Decision resolved by the image

- **Per-band EQ colours** (open decision 1 of rev 6): the approved image uses green / blue / purple /
  yellow for bands 1-4, so the mockup does too, **scoped to the EQ graph and the band cards only**.
  Elsewhere green stays signal/LIV, purple stays FX, amber stays caution. Hues: #46D16A, #3B9BF0,
  #B46CE0, #E6B83F. Recorded conflict: band 3 purple is close to FX violet (#9870D8) and band 4 equals
  the caution amber; they never appear outside the EQ, so they do not carry those meanings there.

### Open decisions for revision 7

1. **R7-1 Brand.** Keep FLOW 888 (current policy), or change the naming policy in `PRODUCT.md` first.
   The mockup does not show "CueAir" either way (that part of the policy is not negotiable without an
   explicit owner change).
2. **R7-2 LIVE and menu positions.** LOCK in LIVE's place and MUTE ALL in the menu's place: approve, or
   specify another arrangement.
3. **R7-3 Strip MUTE.** One full-width MUTE (no Solo) instead of M + S squares: approve.
4. **R7-4 Provenance badge on strips.** After the readout (as drawn), or another form.

### Gap between v3 today (rev 6 build) and rev 7, for the implementation plan (not started)

`v3.css` / `v3.js` only, no hub or safety change: band colours on curve, fills, nodes and cards;
band cards with Freq / Gain / Q rows and knob; strip header two lines; readout + badge row;
full-width MUTE; FLOW 8 scale labels; MAIN L+R label; bus cards 74 px with chevron; toolbar order
(LOCK in LIVE position, MUTE ALL, settings); left list 52 px with icons, mute groups and PRESET at the
foot; ≤1100 px breakpoint as in the mockup. Tests: the existing v3 suites (`test_v3_*`) must stay
green; selectors that change (strip mute, group buttons) are kept or the tests updated with the change.

Owner decisions recorded 2026-11-27:
- Navigation: **Option A**, page tabs in the top bar (section 2).
- Product name in the UI: **FLOW 888** (the brief's "FLOW 8 CueAir Pro" is not used in the UI).
- Solo / PAFL: **left out**; opening it is a separate safety-policy job.
- Direction: professional dark mixing console, the owner's Qu MixPad photo as the primary visual
  reference (section 0 below). Implementation waits for explicit approval of this revision.

Visual preview (static, sample values, no script):
`design-plans/flow888-v3/mix-workspace-preview.html`; screenshots in `shots-2026-11-27/`
(`preview-mix-workspace-ipad.png`, `-desktop.png`, `-phone.png`).

Legend used below: **[existing]** = in v3 today, kept; **[moved]** = exists, new place;
**[changed]** = exists, behaviour or look changes; **[new]** = does not exist in v3 today.

## 0. Design direction: before and after

| Aspect | Before (v3 today) | After (this proposal) | Why |
| --- | --- | --- | --- |
| Screen model | 8 separate pages; the Mix page is faders only, EQ is on another page | Mix is a console workspace: selected channel's processing on top, faders below, buses right | The reference's main lesson: level and processing of one channel on one screen |
| Navigation | 84px left rail with icons and Thai sublabels | [changed] text tabs in the top bar, active tab underlined teal | Option A; gives the width to the strips |
| Left column | page rail | [new] selected channel identity, processing list, mute groups [moved], next cue [moved] | The reference's processing list |
| EQ | own page, band colours teal / green / orange / violet | [moved] top of Mix; [changed] curve in EQ cyan, numbered nodes 1-4, selected node active teal (section 0b) | Violet already means FX and green means signal (DESIGN.md Colour-Is-Meaning); four hues on four bands carried no state |
| Mix selector | tab row above the faders | [moved] right column, a mix-coloured bottom bar per mix, selected = teal border | The reference's bus column |
| Channel select | head tap jumped to the Channel page | [changed] the name button selects in place and fills teal | Selection without leaving the mix |
| Top bar tools | FINE, NIGHT, UNDO, LOCK, MUTE ALL | UNDO, [new] REDO, [moved] FINE and NIGHT into SET, LOCK, MUTE ALL | The brief's compact toolbar; REDO exists in the hub, not in v3 |
| Phone | the iPad bank shrunk, UNDO and FINE hidden | [new] single-channel focus; UNDO and REDO always in the bottom bar; FINE beside the fader | Fixes the open warning in `audit-2026-11-27.md` |
| Palette | Night Console navy (DESIGN.md) | [proposed, rev 3] charcoal values for the same roles (section 0b); meanings unchanged | Owner brief 2026-11-27: a near-black console, not navy. Token values change only after explicit approval |
| Surfaces | flat, 1px lines, inset state bars, radii 2-8px | flat, 1px lines, radius 3px, segmented LED meters, EQ graph without a frame | Hardware console look; DESIGN.md Flat-At-Rest kept |
Reference: an Allen & Heath Qu MixPad marketing photo supplied by the owner (iPad, Qu-5). It is used
for layout and hierarchy only; no artwork, colour scheme or wording is copied.
Base: commit `6a9b8c6` plus the uncommitted v3 working tree, after the Phase 3 fixes in
`audit-2026-11-27.md`.

## 0b. Visual direction, revision 3: professional digital mixing console (owner brief 2026-11-27)

Governing sentence: **design FLOW 888 as a professional digital mixing console, not a dark-themed
web dashboard.** Character: industrial, high density, precise controls, flat dark surfaces,
technical-instrument look, minimal decoration. Primary visual reference: the owner's Qu MixPad photo.

### Self-explaining controls (revision 5, owner brief 2026-11-27: "the user should know what it is for without being told")

- No instruction sentence on the Mix workspace. The EQ note "Frequency and Q are fixed. Drag a dot"
  is removed; a lock glyph beside each fixed frequency says it instead, and the round numbered
  nodes on a curve say "drag me".
- One 1.8px-stroke line icon set, drawn for this product, always beside a word, never alone:
  source on every strip head (mic for ch 1-4, jack for 5/6 and 7/8, USB for ch 7, speaker for Main),
  INPUT / EQ / COMP / SENDS in the processing list (signal-in arrow, EQ curve, compressor knee,
  split), destination on each mix (speaker MAIN, wedge monitor MON, wave FX), muted speaker on MUTE,
  arrows on UNDO / REDO.
- Readouts at 19px so the level is the first thing read on each strip.

### Reference palette mapped onto the DESIGN.md roles

The owner supplied these values as approximations taken from the photo, not as an Allen & Heath
specification. They are mapped onto the existing DESIGN.md roles; no role and no meaning changes.
**The token values in DESIGN.md and `v3.css` stay navy until the owner approves this mapping
explicitly.** The preview already uses the mapping so it can be judged.

| DESIGN.md role (token) | Approved today | Proposed (reference) | Contrast check (WCAG, computed 2026-11-27) |
| --- | --- | --- | --- |
| Well (`--well`), recessed areas | #050D14 | #08090A Pure Black | - |
| Chassis (`--chassis`) | #06111A | #111416 Console | - |
| Panel / Card (`--panel`, `--card`) | #0A1823 / #0E2030 | #1B1E20 Panel | - |
| Elevated (`--raised`), controls | #15303F | #292D30 Control | - |
| Border Light (`--line-2`) | #21495C | #484D50 Border | - |
| Border Dark (`--line`) | #14303F | #2C3033 (interpolated; not in the brief) | - |
| Text Primary (`--ink`) | #E8F3F6 | #E8EAEB | 13.9:1 on Panel |
| Text Muted (`--ink-3`) | #86A0AC | #92999C | 5.8:1 on Panel, 4.8:1 on Control: AA |
| Selection (`--sel`) | #1FE0D0 | #35B4B0 Active Teal | 6.6:1 on Panel; near-black text on it 7.9:1 |
| Selection deep (`--sel-deep`), fader fill | #0E8F8A | #0C7C82 Primary Teal | fill only: as text 3.4:1 on Panel fails AA |
| FX identity (`--mix-fx`) | #A78BFA | #9870D8 FX Purple | 4.5:1 on Panel |
| Caution (`--amber`) | #FFB020 | #E6B83F Warning | 9.0:1 on Panel |
| Fault / danger (`--red`) | #FF3B30 | #E34B45 Danger | white text on it 3.9:1 fails AA, so active MUTE uses #08090A text |
| LED green (`--green`): LIV and link lamps | #3BE36F | #31E83B Signal Green | - |
| Meter green (new role, meters only) | uses `--green` | #27D65B Meter Green | - |
| Meter hot (new role, meters only) | uses `--red` | #F04444 Meter Red | - |
| EQ curve (new role, EQ graph only) | - | #39C9DB EQ Cyan | - |
| MON identity (`--mix-mon`) | #34D399 | **#34D399 kept** | the brief has no MON colour; signal green must not double as an identity |
| Main identity (`--mix-main`) | #E8F3F6 | #E8EAEB | - |
| White | - | #FFFFFF only for high-emphasis numbers | - |

Conflicts found, and how the preview resolves them:
1. **EQ Cyan and Active Teal differ by only 1.27:1.** They read as one colour. So cyan is never used
   on anything selectable: it draws the curve, its fill and the ring of unselected nodes only. The
   selected node is a filled teal node with a light ring, drawn larger.
2. **"EQ nodes coloured per band"** (brief) conflicts with the Colour-Is-Meaning rule: the free
   hues are already taken (violet = FX, green = signal, amber = caution, red = fault). The preview
   numbers the nodes 1-4 instead. Open decision 1.
3. **Primary Teal #0C7C82 is too dark for text.** It is used only as the fader fill.
4. **Danger with white text fails AA.** Active MUTE uses near-black text on red.
5. **Signal Green as MON identity** would make green mean two things; MON keeps emerald #34D399.

### Component styling (the preview implements all of these)

| Component | Spec |
| --- | --- |
| Buttons | flat `--raised` fill, 1px `--line-2`, radius 3px, uppercase 14-16px weight 700, 44px minimum height. Active = `--sel` border (lists) or `--sel` fill with near-black text (channel name, channel chip) |
| Top toolbar | 52px, `--panel`; text tabs with a 3px teal underline on the current page; link pill (the only fully round element, per DESIGN.md); UNDO, REDO, SET, then a gap, LOCK and MUTE ALL |
| Processing list (left) | 132px column of stacked buttons, no cards; identity block with a 3px teal top bar; mute groups 2 x 2; next cue at the foot |
| EQ workspace | no frame around the graph; grid 1px `--line`, 0 dB line `--line-2`; curve 2px EQ cyan with a 10% fill; nodes 24px numbered, selected 28px teal; readouts show band, fixed frequency, "Q fixed" and gain; LOW CUT beside them; FLAT at the top right |
| Channel strip | Qu order, top to bottom: name, MUTE, fader with meter, readout (rev 4). 1px `--line` frame and a 3px top bar in the mix colour; 44px name button (selected = teal fill, and the whole strip tinted #10302F); fader well `--well` with a 4px slot and dB ticks; cap #C9D6DC; segmented LED meter 8px wide (4px lit, 2px gap; green to 72%, amber to 88%, red above); readout; 44px MUTE |
| Master and buses (right) | reference order (rev 4): master strip of the selected mix (100px, one Main meter: `audio_meter.py` sends Main L/R as one value, `main`), then the 5 mix buttons (52px, 3px bottom bar in the mix colour, selected = teal border) at the screen edge. Separate L/R meters would need a hub change and are not proposed |
| Meters | segmented LED, never a smooth bar; MON and FX masters show "no meter" because there is no data source |
| Forbidden | glass, clay, gradient backgrounds, glows (the preview also removed the link-lamp glow), floating cards, large dashboard cards, round consumer-style buttons |

## 0c. Revision 6: owner's FLOW 8 concept screenshot as the primary visual target (2026-11-27)

The owner supplied a concept image of a "FLOW 8 CueAir Pro v3" console. It supersedes the Qu MixPad
photo as the layout target. The preview (`mix-workspace-preview.html`, rev 6) follows its
composition, proportions and density; sections 0 and 0b still hold where this section is silent.

### Composition taken from the concept

| Zone | Concept | Rev 6 preview |
| --- | --- | --- |
| Row 1 toolbar (60px) | brand + "LIVE CONSOLE", CONNECTED, MIDI, UNDO, REDO, LIVE, settings, menu | brand FLOW 888 + LIVE CONSOLE, CONNECTED (LED green, means link up), USB MIDI, UNDO, REDO (dimmed when nothing to redo), LOCK, MUTE ALL, settings (FINE, NIGHT) |
| Row 2 navigation (54px) | 6 large icon tabs: MIX, FX, MY MON, SHOW, OUTPUT, SETUP | same 6; selected = teal border on a dark teal tint |
| Left panel (196px) | channel header, SOURCE, GATE, EQ, COMP, FX SEND, MON SEND, CHANNEL; LINK, PRESET | channel header, SOURCE, EQ (selected = teal fill), COMP, FX SEND, MON SEND, CHANNEL; mute groups A-D; PRESET |
| EQ workspace (330px) | EQ tab, graph 20 Hz - 20 kHz, ±12 dB, coloured nodes, 4 band cards with Freq / Gain / Q, knob, ON toggles; EQ ON; curve, phones, RTA buttons | EQ tab, same graph scale, numbered nodes (cyan ring; selected teal), 4 band cards with Freq (lock), Gain, Q "fixed" and a gain knob; FLAT; no ON toggles, no EQ ON, no RTA |
| Fader bank | 8 strips: number, name, scale, segmented meter, fader, dB value, M and S | 7 strips (the FLOW 8 has 7 input strips): number, name, scale, segmented meter, fader, dB value, M |
| Right panel (176px) | MAIN OUT with L/R meter, fader, MAIN, 0.0 dB, MUTE; MON 1, MON 2, FX 1, FX 2 cards with mini meters | MAIN OUT with one meter, fader, MAIN (selected mix), 0.0 dB; MON 1, MON 2, FX 1, FX 2 cards with level or preset and a chevron (tap = mix on faders) |

### Shown in the concept but not drawn, and why (no invented capability)

| Concept element | Reason (evidence) |
| --- | --- |
| Brand "FLOW 8 CueAir Pro v3" | CLAUDE.md: CueAir is not named in user-facing UI; owner decision 2026-11-27: FLOW 888 |
| GATE | no gate on the FLOW 8 (capability matrix: "gate or expander: not possible") |
| Solo / S buttons | not in the allowlist, LAN-locked (`LAN_LOCKED_FEATURES["solo"]`); owner decision: left out |
| Editable EQ frequency and Q, band ON, EQ ON | not possible per the evidence (C-04); band and EQ bypass not documented |
| 8th input strip | the FLOW 8 has 7 input strips (ch 1-4, 5/6, 7/8, USB/BT) |
| Main L/R meter | `audio_meter.py` delivers Main as one value (`main`) |
| Main MUTE | `Flow8Service.set_mute` accepts channels 1-7 only; MUTE ALL stays in the toolbar |
| Mini meters on MON / FX cards | no meter source for buses |
| LINK | stereo link has no verified MIDI address (`LAN_LOCKED_FEATURES["stereoLink"]`) |
| LIVE mode | no such mode exists; LOCK (hold) is the existing live-safety control |
| RTA, curve and headphone buttons beside the graph | no analyser or cue bus exists |
| Per-band node colours (green, blue, purple, yellow) | purple = FX and green = signal in DESIGN.md; numbered nodes instead (open decision 1) |

### Navigation mapping (no page is lost)

MIX = Mix workspace; FX = FX page; MY MON = My Mon; SHOW = Show; OUTPUT = Output;
SETUP = the Safety page plus the settings (FINE, NIGHT). The Sends page opens from FX SEND / MON SEND,
and the Channel page from CHANNEL, in the left panel.

## Phase 0: what exists (read-only, VERIFIED by reading source this session)

- Shell (`flow8/web_ui/v3/index.html`): top bar (brand, link pill HOST / FLOW 8 · USB, cue NOW/NEXT,
  FINE, NIGHT, UNDO, hold-LOCK, hold-MUTE ALL), left rail of 8 pages, `main.stage`.
- `v3.js` building blocks that the Mix Workspace can reuse as they are:
  `fader()` (relative drag, FINE, one gesture = one undo step), `stripEl()` (head, chips, fader,
  meter, readout, mute), `eqGeometry()` + the EQ section of `pageChannel()` (graph, gain dots at
  fixed centres, FLAT two-tap, low cut, comp, presets), `mixButtons()` / `MIXES` (MAIN, MON 1,
  MON 2, FX 1, FX 2), `chLevel()` / `masterLevel()` / `chLevelCmd()` / `masterCmd()` (a mix layer
  puts sends on the faders), `wireGroups()` (4 mute groups), `paintMeters()` (USB audio meters,
  ids `ch1..ch7`, `main`), `hold()`, `gesture()`, `PROV` / `PROV_TIP`.
- Hub actions used today: setFader, setSend, setBusFader, setMute, muteAll, setEqBand, resetEqFlat,
  setLowCut, setCompressor, setBusGeq, setBusLimiter, setFxPreset, setFxParam, applyPreset,
  librarySave, libraryLoad, runShowMode, undo, setActiveBus. The hub also offers `redo` and
  `setPan`, which v3 does not use yet.

## 1. What the reference does well, and what of it fits the FLOW 8

| Reference element | What it achieves | FLOW 8 reality (`docs/product/FLOW8_CAPABILITY_MATRIX.md`) | Decision |
| --- | --- | --- | --- |
| Large PEQ graph on top for the selected channel | Processing and level on one screen; no page switch | 4-band gain only, ±15 dB, CC 1-4. Frequency, Q and filter type: **not possible** per the evidence. Band on/off: not documented | Graph on top, gain dots at the fixed manufacturer centres. Freq and Q shown as fixed text, not as controls. No band in/out buttons |
| Processing list left: Source, Gate, Insert, PEQ, Comp, Delay | One tap to each processing block of the selected channel | Input: gain is host-only (SR-05), +48 V gated, low cut ch 1-4. Comp: one amount control, ch 1-4. Gate, insert and delay: **do not exist** | Left list: INPUT, EQ, COMP, SENDS, plus FX on FX layers. No GATE, INSERT or DELAY entries |
| Channel name button above each strip (bright green = selected) | Select a channel without leaving the mix | Selection is ours to show | Name button selects the channel. Selected = teal (DESIGN.md). Green stays LED and OBSERVED only |
| Mute + PAFL under each fader | Mute and listen per channel | Mute: CC 5, implemented. Solo: CC 6 documented, **not in the allowlist and LAN-locked** (`LAN_LOCKED_FEATURES["solo"]`) | Mute yes. No Solo/PAFL button; the strip keeps the space empty. Opening solo is a separate safety decision |
| Meter beside every fader | Signal at a glance | USB audio meters for ch 1-7 and Main only. No meters for MON or FX buses | Meter on input strips and Main. MON/FX masters show "no meter" (not a fake bar) |
| Right column: MainLR, FX sends, Mix 1-12 | One tap swaps the faders to that mix | 5 buses: MAIN, MON 1, MON 2, FX 1, FX 2 | Right column with exactly these 5. Tap = mix layer (existing `ui.mix`) |
| Master strip at the right edge | Main always reachable | Main level CC 7 (ch 8); MON/FX masters via setBusFader | Master strip of the selected mix, pinned right |
| Left bottom: Inputs / Mix / FX / DCAs / Mute Groups / Soft Keys | Layer switching | No DCAs, no soft keys on FLOW 8; our 4 mute groups are app-side | Mute groups move into the left panel's lower half |
| Top tabs: Processing, Routing, Meters, Scenes, Setup; Current / Next | Workspaces and scene position | Our 8 pages; cue NOW / NEXT exists | See Option A / B below. Cue NOW / NEXT stays in the bar |

## 2. Proposed Mix Workspace, iPad landscape 1180 x 820 (primary)

```
+--------------------------------------------------------------------------------------------+
| FLOW 888 | HOST . USB | Mix Sends Channel ... | UNDO REDO SET | LOCK | MUTE ALL |  52px
+--------+-----------------------------------------------------------------+---------------+
| CH 1   |  EQ graph of the selected channel (gain dots, fixed centres)    |  MAIN    [*]  |
| Mic 1  |  +12 .................................................          |  MON 1        |
|--------|      o-------o_____o----------o                                |  MON 2        |
| INPUT  |  -12 .................................................          |  FX 1         |
| EQ  [*]|  LOW 80 Hz +1.4 | LO MID 300 Hz -1.4 | HI MID ... | HIGH ...     |  FX 2         |
| COMP   |  FLAT (2-tap)            freq / Q fixed by the mixer      SNT   |               |
| SENDS  +-----------------------------------------------------------------+---------------+
|--------| [Mic 1*][Mic 2 ][Line 3][Line 4][Ln 5/6][Ln 7/8][USB/BT]       | [MAIN LR]     |
| MUTE   |  SNT     SNT     UNK     ...                                     |   SNT         |
| GROUPS |  |=|#    |=|#    |=|#    ...      fader + meter                 |   |=|#        |
| A B    |  |=|#    |=|#    |=|#                                            |   |=|#        |
| C D    |  -3.5    -9.0     --                                             |   +0.0        |
|        |  [MUTE]  [MUTE]  [MUTE?]                                        |   [ - ]       |
+--------+-----------------------------------------------------------------+---------------+
```

- Top half (about 40% of the height): the panel chosen in the left list for the selected channel.
  EQ shows the graph; INPUT shows gain "on mixer", +48 V locked chip, low cut; COMP shows the one
  amount control; SENDS shows the four send levels of this channel. All reuse `pageChannel()` parts.
- Bottom half: 7 input strips + the master strip of the selected mix. Fader zone stays at least
  120px (DESIGN.md). Strip head = name button (tap selects; teal when selected).
- Left column 120px: channel identity, processing list, mute groups (tap = toggle, hold = edit,
  as today).
- Right column 110px: the 5 mixes (tap = layer) above the master strip.

### Navigation for the other 7 pages: Option A chosen (2026-11-27)

The 84px rail becomes text tabs in the top bar (Mix, Sends, Channel, Output, FX, Show, My Mon,
Safety). The shell changes on all 8 pages; their content does not. The Thai sublabels of the rail
move to each tab's `title` and to the page heading, which already carries them.
(Option B, keeping the rail, was declined.)

### Measured layout of the preview at 1180 x 820 (VISUAL VERIFIED in headless Chromium)

| Zone | Size |
| --- | --- |
| Top bar | 52px: brand, link pill (HOST / USB lamps), 8 tabs, UNDO, REDO, SET, LOCK, MUTE ALL |
| Left processing column | 132px: identity card (teal top bar), INPUT / EQ / COMP / SENDS (44px each), mute groups 2 x 2, next cue at the foot |
| Upper workspace | 300px tall: header (channel, badge, fixed-frequency note, FLAT), graph, 4 band readouts + low cut |
| Lower workspace | the rest: 7 strips about 112px wide; name button 44px, fader zone, readout, 44px mute |
| Right column | 208px: 5 mixes (48px each) beside the master strip of the selected mix |
| Horizontal overflow | 0 at 1180, 1440 and 390 |

### Desktop (>= 1366)

Same zones; strips widen (about 150px at 1440). Proposed for implementation, not in the preview:
the processing panel (INPUT or COMP values) sits beside the EQ graph instead of replacing it.

### Mobile portrait (<= 760), from top to bottom

1. Bar: mark, link lamps, LOCK, MUTE ALL (hold actions as today).
2. Channel chips (scroll sideways): CH 1-4, 5/6, 7/8, USB, MAIN; selected = teal fill.
3. Mix row: MAIN, MON 1, MON 2, FX 1, FX 2; selected = teal border.
4. Focus: left, one large strip (name, badge, fader with meter, readout, MUTE, FINE); right,
   quick processing as horizontal sliders: four EQ gains, low cut, comp. Each shows its own badge
   rule (`--` when unknown).
5. Bottom bar: UNDO and REDO always visible, then the page tabs (scroll sideways).

## 3. Responsive specification

| Viewport | Layout |
| --- | --- |
| Desktop >= 1366 | Same as iPad. The EQ panel and the processing panel sit side by side (EQ graph plus COMP/INPUT values visible together). Strips up to 150px. |
| iPad landscape 1024-1365 | As drawn above. |
| iPad portrait 761-1023 | Top panel 35% height; right mix column becomes a row of 5 mix buttons above the strips; strips scroll sideways, master pinned right (existing pattern). |
| Phone <= 760 | **Single-channel focus**, not a shrunk console: channel chips row (scrolls), one large fader with meter and readout, MUTE, a 4-slider quick EQ (gain only) and LC, mix selector row. Bottom bar: UNDO and REDO always visible, then page tabs. FINE moves into the channel view next to the fader. Fixes the open warning "phone has no UNDO/FINE". |

## 4. Interaction specification

| Action | Behaviour |
| --- | --- |
| Select a channel | Tap the strip's name button. The top panel and the left identity update; no command is sent. Selection is stored locally (`ui.sel`). |
| Switch processing section | Tap INPUT / EQ / COMP / SENDS. Local only. |
| Fader | Existing `fader()`: relative drag, `beginGesture` → `setFader` (≤ 1 per 70 ms) → `endGesture`; one undo step. |
| Mute | Tap toggles, `setMute`. Unknown mute shows `MUTE ?` and dashed. |
| Mix layer (MON / FX send) | Tap a mix in the right column: faders show that mix's sends (`setSend` / `setBusFader`). The strip top bar takes the mix colour; selection stays teal. |
| Undo / Redo | `undo` / `redo` actions; buttons always visible at every width. |
| Connection loss | Existing offline note; controls are drawn but send nothing; values return to UNK on the next session read. |

### Command state (what the UI may claim)

The FLOW 8 does not echo commands and no inbound telemetry has been received (capability matrix:
"Can be read back from the hardware: nothing is confirmed"). So "hardware confirmed" can only be
shown when the hub reports OBSERVED.

| State | Source | Display |
| --- | --- | --- |
| UI state | local drag, before the POST returns | value moves; badge shows `...` (new, client-side only) |
| Command pending | POST in flight | same `...` |
| Sent | hub returns 200, provenance COMMANDED | `SNT` (sent, **not** confirmed) |
| Hardware confirmed | provenance OBSERVED | `LIV` (only possible once the mixer transmits) |
| Failed | HTTP error or DISPATCH_FAILED | `ERR` in red and a toast; the value returns to the last known one |

`...` and `ERR` are two new three-character labels. `FAILED` becomes `ERR` to match the convention.

## 5. Component architecture (inside the existing `v3.js` IIFE; no framework, no dependency)

- Reused unchanged: `fader`, `stripEl`, `gesture`, `hold`, `paintMeters`, `wireGroups`, `mixButtons`,
  `eqGeometry`, command builders, `PROV_TIP`.
- Extracted (moved, not rewritten) from `pageChannel()`: `eqPanel(c)`, `inputPanel(c)`,
  `compPanel(c)`, so the Channel page and the Mix Workspace render the same code.
- New: `sendsPanel(c)` (four send faders of one channel), `procList()` (left column),
  `mixColumn()` (right column), `phoneMix()` (phone single-channel view), a pending flag per
  control id for the `...` badge.
- `pageMix()` is rewritten to compose these; its existing behaviours (mix layer, groups, head tap)
  are kept. The head tap selects in place instead of jumping to the Channel page.

## 6. Hardware capability mapping (no new capability)

Shown as controls: fader ch 1-7 and Main, mute, EQ gain x4, low cut and comp (ch 1-4), sends to
MON 1/2 and FX 1/2, bus masters. Shown as fixed text: EQ frequencies, Q. Shown as locked chips:
gain, +48 V. Not shown: solo, gate, insert, delay, band on/off, DCAs, bus meters, pan (exists in
the hub but not requested here). Untested on hardware: all of the above (HARDWARE VERIFIED = 0).

## 7. File change plan

| File | Change |
| --- | --- |
| `flow8/web_ui/v3/v3.js` | rewrite `pageMix`; extract three panels from `pageChannel`; add `sendsPanel`, `procList`, `mixColumn`, `phoneMix`; REDO button wiring; pending/ERR badge |
| `flow8/web_ui/v3/v3.css` | Mix Workspace grid, left and right columns, phone single-channel view, `...`/`ERR` badge styles. Existing tokens only |
| `flow8/web_ui/v3/index.html` | add REDO and SET buttons; rail markup moves into the bar as tabs (Option A) |
| `tests/test_v3_console.py` | add: `redo` accepted; static check that no Solo/gate/freq/Q sender exists. Existing tests unchanged |
| not touched | `lan_hub.py`, `service.py`, transport, MIDI, safety, v2 files, DESIGN.md tokens |

## 8. Acceptance criteria

1. At 1180x820 the Mix page shows EQ of the selected channel, 7 input strips, the master strip and
   the 5 mixes without scrolling and without horizontal overflow.
2. Tapping a strip name changes the top panel with zero POSTs.
3. Every value with UNSYNCED provenance shows `--` / `UNK`; nothing shows `LIV` unless OBSERVED.
4. A failed POST shows `ERR` and a toast, and the value returns.
5. No Solo, gate, insert, delay, band on/off, EQ frequency or Q control exists.
6. UNDO and REDO are visible at 1440, 1180, 768 and 390.
7. At 390 the Mix page is a single-channel view with fader, meter, mute, quick EQ and mix selector.
8. The other 7 pages render as before except that navigation is now the top-bar tabs (Option A).
9. `tools.run_tests_no_hw`: 0 failed, 0 physical port opens; `tests.test_v3_console` passes.
10. Selected = teal, FX = violet, amber = warning only, red = mute/danger, green = meters/LIV only.

## Decisions taken (2026-11-27)

1. Option A, top tabs. 2. UI name FLOW 888 (CLAUDE.md: CueAir is not named in user-facing UI;
FLOW 8 branding policy, PR #13). 3. Solo left out.

## Unresolved decisions (need the owner before or during implementation)

1. **EQ band colours.** The brief asks for per-band colours, but the free hues collide with FX,
   signal, caution and fault. Preview: numbered nodes, cyan curve, teal selection. Approve that, or
   name four EQ-only hues to use despite the overlap.
2. **FINE and NIGHT inside SET.** They leave the top bar on iPad. Acceptable, or keep them visible?
3. **Next cue in the left column.** The bar's NOW / NEXT moves to the left column foot. Keep, or
   drop it from Mix (Show page still has it)?
4. **New badges `...` (pending) and `ERR` (failed, replaces `FAILED`).** Approve both labels.
5. **Head tap.** It now selects in place; the Channel page stays reachable by its tab. Confirm that
   losing the jump-to-Channel shortcut is fine.
6. **Mute groups** are app-side (localStorage per device), as today. They stay so.
7. **Hardware.** FX MIDI channels (13/14 vs 14/15) and every command path remain untested on a real
   FLOW 8; the workspace does not change that.
8. **Charcoal palette (section 0b).** Approve the mapping, which changes the DESIGN.md token values
   (and `v3.css`), or keep navy and use the mapping as reference only. v2 shares DESIGN.md: say
   whether v2 changes too.
9. **LED lamp glow.** DESIGN.md allows a 6px glow on LED lamps; the brief forbids glow effects. The
   preview removes it. Approve removing it from DESIGN.md as well.
10. **Navigation of revision 6.** Six tabs (MIX, FX, MY MON, SHOW, OUTPUT, SETUP); Sends and Channel
    pages move behind the left panel, Safety under SETUP (section 0c). Approve, or keep 8 tabs.

---

## Implementation record, 2026-11-27 (owner: "ทำเลย ... UI ได้แบบนี้ หน้าตา", go ahead, looking like the concept)

Open decisions taken with the recommended answers (the owner can reverse any of them):
charcoal palette in `v3.css` only (DESIGN.md and the v2 console stay navy; decision 8 still open
for those); numbered EQ nodes; no LED glow in v3; FINE and NIGHT in the settings menu; next cue only
on the Show page; `ERR` replaces `FAILED` (the `...` pending badge was not built); head tap selects
in place; six tabs.

Files changed: `flow8/web_ui/v3/index.html` (two-row bar, tab nav, icon set, settings menu, REDO),
`flow8/web_ui/v3/v3.css` (tokens, bar, tabs, segmented meters, numbered EQ nodes, Mix workspace,
tablet and phone layouts), `flow8/web_ui/v3/v3.js` (6-tab navigation, link and MIDI pills, Mix
workspace with SOURCE / EQ / COMP / FX SEND / MON SEND editors, master and bus column, phone channel
row, REDO and settings wiring; EQ node, FLAT, range and send-cell wiring moved into shared functions
used by both Mix and the Channel / Sends pages), `tests/test_v3_console.py` (+2 tests).
Not touched: `lan_hub.py`, `service.py`, transport, MIDI, safety, v2 files, DESIGN.md.

Verification (VERIFIED this session, audit hub 127.0.0.1:8857 with MIDI opens denied):
- `python -m tools.run_tests_no_hw`: 463 ran, 458 passed, 0 failed, 5 skipped, 0 physical port opens.
- `python -m unittest tests.test_v3_console`: OK (10 tests).
- All 8 pages at 1440x900, 1180x820 and 390x844: no horizontal overflow, no clipped element, no page error.
- Selecting a strip posts nothing; selected border is `rgb(53,180,176)` (teal).
- Driven: fader drag = beginGesture, setFader x3, endGesture; EQ node drag = beginGesture, setEqBand x3,
  endGesture; MUTE = setMute; bus card = setActiveBus; UNDO = undo; REDO = redo; settings FINE toggles.
- Screenshots: `shots-2026-11-27/impl-*.png`.
- `tools.test_inventory` lists 218 missing names; they are tests of the removed Tkinter UI
  (`test_ui_shell`, `test_channel_detail`, not in git), present before this change.

Not verified: real FLOW 8 hardware (HARDWARE VERIFIED = 0), iOS Safari, LIV rendering.
