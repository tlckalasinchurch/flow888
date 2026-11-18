# Stage 2: Professional Design System & Interface Specification

**Document ID:** `STAGE_2_DESIGN_SYSTEM`  
**System Archetype:** Modern Professional Digital Audio Workstation (DAW)  
**Hardware Console Inspiration:** Behringer FLOW 8 Studio & Stage Hybrid  
**Target Resolution:** 1366×768 (Minimum) to 1920×1080 / High-DPI  
**Date:** 2026-11-18  
**Status:** SPECIFIED & APPLIED  

---

## 1. Visual Architecture & Philosophy

The Stage 2 Design System transforms the interface from a tentative prototype into an authoritative hardware workstation.

### Core Tenets:
1. **Ergonomic Restraint:** Dark studio surfaces reduce eye fatigue during long sessions. Neon accents are restricted to active signals, cursor focal points, and mute/solo alerts.
2. **Numeric Supremacy:** Every continuous controller (fader, EQ, low cut, compressor, send) explicitly couples its visual slider with a high-contrast engineering readout (e.g. `+2.5 dB`, `120 Hz`, `35%`).
3. **Truth in Provenance:** Visual indicators communicate parameter confidence (`OBSERVED`, `COMMANDED`, `UNSYNCED`, `DISPATCH_FAILED`, `UNSUPPORTED`) using distinct text badges and glyphs so state is never conveyed by color alone.
4. **Hardware Homogeneity:** Controls maintain consistent spatial footprints, uniform click-targets, and predictable mouse-wheel/keyboard step increments.

---

## 2. Color Palette & Surface Tokens

| Token Name | Hex Code | Purpose / Usage |
|---|---|---|
| `bg_base` | `#080B12` | Deep charcoal application background |
| `bg_alt` | `#0D1220` | Secondary surface for navigation rails and cards |
| `surface` | `#131A28` | Primary channel strip and inspector background |
| `surface_alt` | `#1A2435` | Inset panels, trough tracks, and inactive buttons |
| `surface_hover` | `#223046` | Pointer hover and active handle state |
| `border_subtle` | `#1F2937` | Low-contrast panel and strip dividers |
| `border_strong` | `#2D3B4E` | Control focus outlines and modal borders |
| `text_primary` | `#F4F7FF` | High-contrast values, channel titles, active buttons |
| `text_secondary`| `#A4B1C6` | Parameter labels, engineering units, subtitles |
| `text_muted` | `#607085` | Unsynced indicators, scale markings, inactive hints |
| `accent_cyan` | `#00E5FF` | Active faders, primary channel highlights |
| `accent_teal` | `#00B4D8` | EQ curves, filter cutoffs, secondary selections |
| `accent_purple` | `#A855F7` | Acoustic presets, DSP profile tags |
| `accent_lime` | `#C6FF00` | Unity gain (0 dB) indicators, Solo monitors |
| `status_success`| `#39D98A` | Confirmed hardware telemetry (`OBSERVED`) |
| `status_warning`| `#FFB84D` | Commanded state (`COMMANDED`), +48V phantom alerts |
| `status_danger` | `#FF5470` | Mute active, dispatch errors, boundary rejections |

---

## 3. Typography Scale

All fonts resolve dynamically against system typefaces (`Inter`, `Segoe UI`, `Arial` for sans-serif; `JetBrains Mono`, `Cascadia Mono`, `Consolas` for monospace):

| Typography Token | Typeface | Size | Weight | Line / Usage |
|---|---|---|---|---|
| `font_title` | Sans | 20 pt | Bold | Application title ("FLOW 8 WORKSTATION") |
| `font_section` | Sans | 14 pt | Bold | Section headers ("EQUALIZER", "DYNAMICS") |
| `font_subtitle`| Sans | 12 pt | Bold | Channel Strip Titles ("CH 01", "MIC 1") |
| `font_body` | Sans | 10 pt | Regular | Labels, descriptions, inspector text |
| `font_caption` | Sans | 8 pt | Regular | Auxiliary notes, hardware socket types |
| `font_eyebrow` | Sans | 8 pt | Bold | Upper-case category tags, close buttons |
| `font_mono_val`| Mono | 9 pt | Bold | Numeric readouts (`-3.0 dB`, `120 Hz`, `30%`) |
| `font_badge` | Mono | 8 pt | Bold | Provenance pills (`[OBS]`, `[CMD]`, `[UNSYNC]`) |

---

## 4. Parameter Provenance Badges (Non-Color Dependent)

To satisfy accessibility and unambiguous hardware truth, each provenance tier pairs color with an explicit textual glyph and label:

| Provenance Tier | Text Badge | Glyph | Color | Semantic Meaning |
|---|---|---|---|---|
| `OBSERVED` | `[OBS: TELEMETRY]` | `●` (Solid Circle) | `#39D98A` (Green) | Confirmed hardware MIDI IN telemetry packet received |
| `COMMANDED` | `[CMD: HOST]` | `▲` (Triangle) | `#FFB84D` (Amber) | Dispatched by software / write-only parameter |
| `UNSYNCED` | `[UNSYNC: BOOT]` | `○` (Empty Circle) | `#607085` (Muted) | Startup baseline; state unknown on mixer |
| `DISPATCH_FAILED` | `[ERR: FAILED]` | `✕` (Cross) | `#FF5470` (Red) | Command rejected by boundary or driver error |
| `UNSUPPORTED` | `[N/A: HARDWARE]` | `—` (Dash) | `#384656` (Dark) | Feature does not exist on physical hardware |
| `STATE_UNCERTAIN` | `[WARN: UNCERTAIN]`| `⚠` (Warning) | `#FF5470` (Red) | Compensation rollback failed; state uncertain |

---

## 5. Control Dimensions & Spacing Metrics

- **Mixer Channel Strip Width:** Minimum $104\text{ px}$, optimal $128\text{ px}$.
- **Fader Height:** $200\text{ px}$ with clear $0\text{ dB}$ unity tick mark (`#C6FF00`).
- **Horizontal Sliders:** Height $26\text{ px}$, width spans parent width with $12\text{ px}$ internal padding.
- **Inspector Panel Width:** Docked at $320\text{ px}$ (scales down to $260\text{ px}$ on 1366×768 displays).
- **Click Targets:** All buttons have a minimum click dimension of $24\text{ px} \times 24\text{ px}$ with mouse-pointer cursor (`hand2`).
- **Detents & Snapping:** Pan and EQ sliders feature a center detent (at raw 64 / $0.0\text{ dB}$) with $\pm 2$ snap-to-feel margin.
