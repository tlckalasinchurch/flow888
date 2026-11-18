# FLOW 8 Product Roadmap (CueAir-informed)

Date: 2026-11-18. Companion documents: `CUEAIR_RESEARCH_STATUS.md`, `CUEAIR_FEATURE_GAP_MATRIX.md`, `IMPLEMENTATION_PRIORITY.md`. Classes (HV / PS / AO / UN) are defined in the gap matrix. No source code is changed by this document.

## Product statement

A professional live-mixing workstation for the Behringer FLOW 8 that gives a small-venue engineer CueAir-style intelligent starting points: curated channel presets, safe level-preserving application, snapshots before every change, and recommendations backed by a real measurement. It never shows an app value as if it were a mixer reading.

## Decision needed from the project owner (before F1)

**CueAir preset data licensing.** `cuetone-basic.cueairpreset` is third-party curated content (58 presets with written rationale). "Independent reimplementation" of the workflow is clear; copying the preset values and notes is a different question.
- Option A: derive our own presets, using the CueAir categories and correction types as a checklist, with our own values and notes.
- Option B: convert the CueAir values mechanically and ship them (needs permission from the maker).
- Option C: convert for local/private use only, do not distribute.
The design below works for all three; F1 only changes where the numbers come from.

## Features

Each feature lists: user problem, CueAir reference, hardware feasibility, approach, dependencies, acceptance criteria.

### F0. Hardware-truth foundation (blocks every inbound claim)

- **User problem:** The screen must not claim mixer state it does not know.
- **CueAir reference:** `/xremote` sync, cached state model.
- **Feasibility:** Inbound fader/pan/mute only, PS. Zero bytes received in today's captures (BLOCKER).
- **Approach:** (1) Resolve USB TX capture with the operator (menu setting, cable, driver) using the read-only logger. (2) Detect cable removal in the app (WinMM handle error or periodic port check) and run the existing reconcile path; today the app does not detect unplug (ASSUMPTION from reading `app.py`; not yet reproduced on hardware).
- **Dependencies:** Operator access to the mixer.
- **Acceptance:** Logger shows raw CC bytes while a control is moved; app strip follows within 100 ms with provenance OBSERVED and zero outbound messages; physical unplug turns all state UNSYNCED within 3 s and clears undo.

### F1. CueAir-grade channel preset library (priority 1)

- **User problem:** Setting EQ/compression for vocals, speech, drums, guitar from scratch is slow and error-prone.
- **CueAir reference:** 58 presets, 9 categories, `preserveLevels`, notes and `why` per preset.
- **Feasibility:** Writable: EQ band gain ×4 (HV prior docs), Low Cut Ch 1–4 (HV prior docs), 1-knob comp Ch 1–4 (HV prior docs). Not writable: frequencies, Q, gate, ratio/attack/release (UN).
- **Approach:** A build-time converter (not runtime) reads the source preset JSON and produces our `ChannelPreset` data plus a per-preset "FLOW 8 fit" record: EQ gains obtained by evaluating the preset's biquad response at the four FLOW 8 band centres; low cut from `/preamp/hpf`; compressor knob from threshold/ratio by a documented heuristic (marked approximate); everything dropped is listed. Notes/why translated into English. Preset picker shows the fit report.
- **Dependencies:** Licensing decision; confirmation of FLOW 8 EQ centre frequencies and CC→dB curve; existing `CommandLedger` and batch undo.
- **Acceptance:** All presets either converted or listed as "not applicable" with reason; golden tests compare converted values to hand-computed cases; applying a preset changes only EQ/low cut/comp (test asserts no fader/pan/gain/phantom command is emitted); one undo restores the exact previous values; picker never states a parameter was applied that FLOW 8 cannot receive.

### F2. Honest "Preserve Levels" (priority 1, small)

- **User problem:** A checkbox that does nothing is a safety lie.
- **CueAir reference:** `preserveLevels: true` on every preset.
- **Feasibility:** AO.
- **Approach:** Make the guarantee structural: presets cannot contain level fields; show "Levels always preserved: fader, pan, gain" as a statement, remove the toggle (defect D-12).
- **Dependencies:** none.
- **Acceptance:** No checkbox; a test asserts the preset application path cannot issue fader/pan/gain/phantom commands.

### F3. Snapshot-before-change and complete scenes (priority 1)

- **User problem:** An engineer needs one-click return to the sound before a preset or batch change, and scenes that include EQ/comp/sends.
- **CueAir reference:** `scene_save`, "BEFORE AI/BEFORE RECALL", `scene_card`, `scene_advance`.
- **Feasibility:** Store and resend are AO using verified writes; hardware snapshot recall (PC 1–15 on Ch 16) is PS and not used; PC 16 resets the mixer and is forbidden.
- **Approach:** Auto-capture of known commanded values before preset/recall; extend reversible parameters to EQ, low cut, comp and sends (excluding phantom, never gain by default); JSON persistence; unknown parameters are left out and shown as "not captured". Scene cards show what is stored.
- **Dependencies:** D-04 expansion; existing provenance rule (UNSYNCED values are never captured).
- **Acceptance:** Capture/recall round-trip test across all supported parameters; app restart keeps scenes; recall is one undo step; recall of a scene with unknown parameters reports exactly what was not sent.

### F4. EQ and dynamics workflow with visual curve (priority 2)

- **User problem:** Gain sliders without a picture are hard to reason about.
- **CueAir reference:** EQ curve, strip detail.
- **Feasibility:** AO (computed from commanded gains at fixed band centres).
- **Approach:** Canvas curve labelled "COMMANDED — not measured"; grey when provenance is UNSYNCED; shows which bands/features the channel lacks.
- **Dependencies:** Confirmed band centres; F1 projection maths shared.
- **Acceptance:** Curve matches the projection function in tests; changes with undo/redo/preset without rebuild; unsynced state visibly differs.

### F5. FX preset management (priority 2)

- **User problem:** Choosing a reverb/delay slot blindly.
- **CueAir reference:** 48 FX starting points with `algorithm`, `group`, `use` tags.
- **Feasibility:** Slot selection Program Change Ch 13 (FX 1) / Ch 14 (FX 2) (PS per official chart, not hardware verified; S0 correction from Ch 14/15); continuous parameters UN.
- **Approach:** Table of FLOW 8 FX1/FX2 slot names (from documentation, confirmed on the mixer); map each CueAir FX preset to the nearest slot with a "closest match" explanation; send level uses existing send controls (preserve return levels as CueAir does).
- **Dependencies:** Slot table; hardware test of Program Change.
- **Acceptance:** Slot select verified on the mixer by listening and by the mixer display; UI states "slot selected, parameters fixed by firmware"; no decay/size controls shown.

### F6. Channel analysis and recommendations (priority 2–3)

- **User problem:** "It sounds boomy/harsh, which preset or EQ fixes it?"
- **CueAir reference:** CueAi suggestions, `fix-*` correction presets, MCP `propose_changes`. Recommendation logic not yet researched.
- **Feasibility:** MIDI gives no levels. Real measurement needs the USB audio stream (PS, not integrated). Recommendations are AO.
- **Approach:** Rule-based analysis of captured USB audio per input (RMS/peak, band energy ratios) mapped to `fix-*`-style corrections; the output is a proposal, applied only through the F7 flow. No claim about post-processing result.
- **Dependencies:** Audio capture library and device mapping; F1; F7; research of CueAi logic.
- **Acceptance:** Synthetic-signal tests (boom, mud, sibilance) produce the expected recommendation; capture works on the real mixer; analysis labelled with which channel, what signal point (unknown pre/post-EQ is stated).

### F7. Staged changes: propose, preview, confirm, commit (priority 2)

- **User problem:** Multi-parameter changes should be reviewed and reversible during a live show.
- **CueAir reference:** `propose_changes`, `confirmRequired`, snapshot, rollback.
- **Feasibility:** AO over verified writes.
- **Approach:** A single "change plan" object (list of parameter, from, to, reason) rendered as a diff; commit goes through `CommandLedger` batch and F3 snapshot; "from" shows unknown when unknown.
- **Dependencies:** F3.
- **Acceptance:** Preview sends nothing (test); commit is one undo step; partial failure rolls back (existing behaviour tested).

### F8. Professional live UX (priority 3, only what blocks a feature)

- Bus master faders (D-08) when F0 verified; strip clipping at 1366×768 (D-06) because the inspector is the F1/F4/F7 surface; gain control decision (D-07: keep gated or add confirmation) is a safety decision for the owner; solo only after CC 6 is tested on the mixer.
- **Acceptance:** per defect register entries; each verified by screenshots and, for hardware controls, an operator test.

## Defects that stay in scope

Only: F0 items (state integrity, reliable hardware operation), D-04 (needed by F3), D-03 (needed by F1 undo quality), D-06 (inspector must fit), D-12 (F2). All other open defects (D-09, D-10, D-11, D-13, D-14) are deferred unless they block one of the above.
