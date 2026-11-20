# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Small-venue live engineers who run a Behringer FLOW 8 mixer at gigs, rehearsals and events. They work under time pressure, often from an iPad or phone on the venue Wi-Fi as well as the host computer, and need to trust what the screen says about the mix.

## Product Purpose

FLOW 8 Workstation is a live-mixing workstation for the Behringer FLOW 8. It gives the engineer safe, reversible starting points (curated channel presets, snapshots before every change, one-step undo) and a remote console over the LAN. Success: the engineer changes the mix faster without ever being misled about what the mixer is actually doing.

## Positioning

The app never presents an app-side value as a mixer reading. Every value carries provenance (UNSYNCED, COMMANDED, OBSERVED), and safety gates are structural, not cosmetic. A neighbouring mixer-remote app that shows optimistic defaults as live state could not truthfully claim this.

## Operating Context

- The LAN hub (`flow8/lan_hub.py`) serves the web console (`flow8/web_ui/`); the same URL works on the host computer and on an iPad on the same Wi-Fi. `python main.py` is the default launch; `--legacy-tk` is the old Tkinter window, kept for regression only.
- The host computer owns the USB MIDI ports. The FLOW 8 sends no meter data over USB MIDI; meters come from the USB audio capture stream. MIDI IN reports only some hardware moves (faders, mute, pan, bus faders), and the mixer does not echo commands back.
- Must work offline at a venue: no build step, plain HTML, CSS and JS, font bundled.
- Touch use: targets of at least 44 px on coarse pointers; protection against stray touches during a show.

## Capabilities and Constraints

- Safety rules are in `docs/product/FLOW8_SAFETY_POLICY.md` (SR-01 to SR-12) and bind all design work: no Program Change sender, no mixer reset, preamp gain and +48 V gated and never automated, presets never touch levels, no control for undocumented parameters.
- Provenance rule: after a disconnect all values return to UNSYNCED; unknown stays unknown; a driver return code is not hardware confirmation.
- Capability truth lives in `docs/product/FLOW8_CAPABILITY_MATRIX.md` and `FLOW8_PARAMETER_MAPPING.md`.
- Undecided: licensing of third-party preset data (roadmap options A, B, C) is an open owner decision.

## Brand Commitments

- **Naming policy (owner decision, 2026-11-20; supersedes policy A):** the user-facing product name is "FLOW 888". App titles, brand mark, navigation, labels and documentation shown inside the app use "FLOW 888". "FLOW 8 CueAir Pro" is permitted only as an internal project/development codename. Do not expose "CueAir" in the UI or other user-facing copy. "FLOW 8" still names the Behringer hardware.
- CueAir-related workflow ideas are not evidence of a FLOW 8 capability. SR-10 remains in force unchanged.
- The previous title conflict is resolved: `flow8/web_ui/index.html` uses "FLOW 888" for `<title>`, the brand mark and the version label. No Safety Layer or Business Logic change is authorized by this naming decision.
- The existing "Cyber Neon" theme tokens were NOT confirmed as binding in this interview; treat them as the incumbent look, not a commitment.

## Evidence on Hand

- Official manufacturer manuals and quick start guide under `docs/product/sources/` (third-party copyright, untracked).
- Hardware capture logs and audit screenshots under `docs/audit/` and `capture/`.
- No real user testimonials, venue case studies or measured latency from hardware are on hand; future work must not fabricate them.

## Product Principles

1. Never show a value the system cannot back with data.
2. Safety is structural: a gate that only the UI enforces is not a gate.
3. Every change is reversible, and the engineer can see what changed.
4. Built for glance-reading in a dark venue and for stray touches, not for first-time exploration.
5. State what is not known, in plain words, instead of hiding it.

## Accessibility & Inclusion

No standard was set in this interview. Known requirement from the existing design doc: touch targets of at least 44 px on coarse pointers. Further accessibility requirements are undecided.
