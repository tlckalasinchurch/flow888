---
name: FLOW 8 Live Console
description: Matte dark-slate live-mixing console for the Behringer FLOW 8, where colour carries meaning and nothing decorates.
colors:
  chassis: "#0E1013"
  panel: "#14171C"
  card: "#191C22"
  well: "#0A0B0E"
  elevated: "#22262D"
  border-dark: "#1F232A"
  border-light: "#2C313A"
  text-primary: "#E7E9EE"
  text-secondary: "#A1A7B0"
  text-muted: "#88909D"
  signal-cyan: "#3FD2E0"
  signal-amber: "#FFB020"
  signal-emerald: "#34D399"
  signal-violet: "#A78BFA"
  signal-red: "#FF3B30"
  led-green: "#3BE36F"
  led-blue: "#4FA8FF"
  mix-main: "#E6E8EB"
typography:
  label:
    fontFamily: "Barlow Condensed, Noto Sans Thai, Leelawadee UI, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    letterSpacing: "0.06em"
  body:
    fontFamily: "Barlow Condensed, Noto Sans Thai, Leelawadee UI, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    letterSpacing: "0.01em"
  title:
    fontFamily: "Barlow Condensed, Noto Sans Thai, Leelawadee UI, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    letterSpacing: "0.12em"
rounded:
  xs: "2px"
  sm: "3px"
  md: "5px"
  lg: "8px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "14px"
  lg: "16px"
components:
  status-pill:
    backgroundColor: "{colors.well}"
    textColor: "{colors.signal-amber}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  strip:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  tap-pad:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    height: "44px"
---

# Design System: FLOW 8 Live Console

## Overview

**Creative North Star: "The Matte Console"** (provisional: derived from the implemented CSS and the owner's stated direction, not yet confirmed in an interview)

A live console read at a glance in a dark room, often through a touch screen. Surfaces are matte, low-glare slate in five close steps. Colour is spent only on meaning: mix identity, LED state, channel tags, provenance. Decoration earns nothing.

Density is high but orderly. Type is a condensed grotesque so eight strips and an inspector fit without shrinking targets. Depth comes from tonal layering and 1px borders, not shadows or blur.

The owner wants this theme to stay flexible and evolve toward a refined, low-glare "Quiet Luxury" dark mode: no heavy gradients, no excessive glassmorphism. That is a direction of travel, not a present claim. The implemented system already leans that way.

**Key Characteristics:**
- Five-step slate ladder from chassis to elevated; no pure black, no pure white.
- Colour means state. A hue never appears as ornament.
- Zero `backdrop-filter`; shadows are inset state marks or LED glows only.
- Touch targets of at least 44px on coarse pointers; `prefers-reduced-motion` honoured.
- Provenance states (UNSYNCED, COMMANDED, OBSERVED) are a visual vocabulary, never hidden.

## Colors

A dark slate neutral ladder carries every surface; a small signal set carries meaning. Frontmatter values are normative.

### Primary
- **Signal Cyan** (`#3FD2E0`): selection and focus. The focus ring, the selected strip's border, inspector accents. Not a decoration colour.

### Secondary
- **Signal Amber** (`#FFB020`): caution and degraded state (link fault, status pill, amber LED).
- **Signal Emerald** (`#34D399`): the MON mix identity.
- **Signal Violet** (`#A78BFA`): the FX mix identity.

### Tertiary
- **Signal Red** (`#FF3B30`): clip, fault, destructive. LED glow `0 0 6px`.
- **LED Green** (`#3BE36F`) and **LED Blue** (`#4FA8FF`): link-up lamps; blue also marks USB strips.

### Neutral
- **Chassis** (`#0E1013`): page background.
- **Panel** (`#14171C`), **Card** (`#191C22`), **Elevated** (`#22262D`): ascending surface steps.
- **Well** (`#0A0B0E`): recessed areas (fader wells, LCD-style readouts, pills).
- **Border Dark** (`#1F232A`) and **Border Light** (`#2C313A`): 1px separators.
- **Text Primary** (`#E7E9EE`), **Secondary** (`#A1A7B0`), **Muted** (`#88909D`, 4.72:1 on the Elevated step so it passes AA on every surface).
- **Mix Main** (`#E6E8EB`): the MAIN mix identity (silver).

### Named Rules
**The Colour-Is-Meaning Rule.** A saturated hue appears only when it names a state, a mix, or a selection. If removing the colour loses no information, remove it.

**The Provenance Rule.** UNSYNCED, COMMANDED and OBSERVED values must look different from each other. Never render an unknown value in the same treatment as a mixer reading (PRODUCT.md, SR-08, SR-11).

**The Unknown-Reads-Unknown Rule.** An UNSYNCED value shows `--` in Muted with a dashed edge, the fader cap is parked and dashed, and mute is neutral. LED Green is reserved for OBSERVED readouts. A 3-letter provenance badge (UNS / CMD / OBS) stays visible on every strip at every width.

## Typography

**Display / Body / Label Font:** Barlow Condensed (bundled woff2, weights 500, 600, 700-800), with Noto Sans Thai, Leelawadee UI, Segoe UI, system-ui as fallbacks. One family throughout.

**Character:** Condensed, technical, hardware-label. Numerals are tabular (`font-feature-settings: "tnum"`) so values do not jitter during a fader drag.

### Hierarchy
- **Title** (700, 16px, 0.12em tracking): the brand mark and panel headers.
- **Body** (500-600, 13px, 0.01em): values, list rows, readouts. Sizes observed: 12, 13, 14, 15px most common.
- **Label** (700, 12px, 0.06em, uppercase): link names, pills, tags.
- **Floor:** 12px. Nothing in the console is set smaller.

### Named Rules
**The Tabular Numerals Rule.** Every number that can change live uses tabular figures.

## Layout

An app shell fills the viewport (`100dvh`): status strip on top, channel strips as an even row, a right-hand inspector (400px wide, `--insp-w`). Strips share space with flex growth; the master strip grows slightly more (1.15) and is set apart by a hairline.

Responsive breakpoints in the CSS: 1180px, 999px, 960px, 760px, and a height query at 820px. Coarse pointers raise key controls to 44px. Spacing is compact: 4, 6, 14 and 16px recur.

## Elevation & Depth

Tonal layering, not shadows. Depth is the slate ladder (well, chassis, panel, card, elevated) plus 1px borders.

### Shadow Vocabulary
- **State bar** (`box-shadow: inset 0 3px 0 var(--mix)`): the top of a strip in its mix colour; bottom variants (`inset 0 -2px 0`) mark cyan, amber and green state.
- **Selection ring** (`box-shadow: 0 0 0 1px var(--accent-cyan) inset`): the selected strip.
- **LED glow** (`0 0 6px` in the LED colour): lamps only.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces carry no drop shadow. Shadow-like marks are inset and mean state.

**The No-Blur Rule.** No `backdrop-filter`, no frosted panels. Glare and legibility outrank atmosphere.

## Shapes

Small, hardware-like radii: 2px, 3px, 4px, 5px, 6px, 8px, with 3px the most common. Circles (`50%`) for LEDs and knobs; a full pill (999px) only for the status pill. Borders are 1px hairlines.

## Components

### Channel Strip
- **Shape:** 5px corners, `{colors.card}` ground, top border in the mix or source colour (blue for USB).
- **State:** selected adds a 1px cyan inset ring; the master strip uses a subtle 180-degree `#22262D` to `#1B1E23` gradient (one of 19 gradient uses in the CSS; keep gradients this quiet).
- **Contents:** pan row, fader zone (min height 120px) with ticks and a 44x28 cap, mute/solo buttons, readout.

### Status Pill
- **Style:** `{colors.well}` fill, 1px `{colors.border-light}` border, amber label text, fully rounded.

### Navigation
- **Four sections** (Mix, Sound, Presets, Setup) in the top bar; Mix and Sound show a second row of views (Mixer, Stage, Channel / Input, EQ, Comp, Sends, FX). Touch targets are 44px.

### MUTE ALL
- Muting needs a 0.6s hold with a visible progress bar; restoring is a single tap. At least 24px separates it from LOCK, and an ALL MUTED chip stays in the status strip while it is active.

### Show Mode
- `MC` and `BAND` sit in the top bar, 44px tall. A mode switches only after a 0.45s hold with a visible progress bar (same pattern as MUTE ALL); a tap shows a hint. A mode with a step NOT SET is dashed and says NOT SET, and does not run. After every switch an `UNDO <mode>` button stays on screen for 8s. Cuts (mutes, zeros) always run before raises, and +48V and preamp gain are never part of a mode.

### Pads and Buttons
- **Tap pad / hardware button:** `{colors.elevated}` fill, 1px light border, 5px radius, 14px 700-weight label with 0.08em tracking, 44px minimum height on coarse pointers.

### Inspector
- **Style:** 400px right panel; step and close buttons 44x44 on coarse pointers.

## Do's and Don'ts

### Do:
- **Do** express new surfaces as steps on the existing slate ladder, using the frontmatter tokens.
- **Do** keep every live number tabular and every state distinguishable without colour alone where possible.
- **Do** keep touch targets at 44px or more on coarse pointers and respect `prefers-reduced-motion`.
- **Do** show provenance (UNSYNCED, COMMANDED, OBSERVED) in the UI wherever a value is shown.

### Don't:
- **Don't** add `backdrop-filter`, glassmorphism or glowing cards.
- **Don't** add decorative gradients; the one existing master-strip gradient is the ceiling, not a precedent.
- **Don't** use a signal hue as ornament.
- **Don't** name CueAir in user-facing copy (PRODUCT.md, SR-10).
- **Don't** treat the "Quiet Luxury" direction as done: palette and type changes toward it need a confirmed decision first.
