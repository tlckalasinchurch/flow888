# CueAir Feature Gap Matrix

Date: 2026-11-18. Sources: `docs/reverse-engineering/05/07/08`, `docs/architecture/CUEAIR_TO_FLOW8_COMPATIBILITY.md`, `docs/testing/HARDWARE_VERIFICATION_MATRIX.md`, extracted CueAir files, current `flow8/` source.

## Classification (required for every feature)

- **Hardware Verified (HV):** operator-observed on the physical mixer in a documented test. Where this rests only on prior documents it is marked "HV (prior docs)" and has not been re-verified.
- **Protocol Supported, Not Hardware Verified (PS):** the MIDI address is documented or implemented, no physical test evidence.
- **Application Only (AO):** exists only in the app; never presented as a mixer control.
- **Unsupported (UN):** FLOW 8 cannot do it over USB MIDI.

Inbound telemetry (mixer to app) is **blocked** on this machine today: 0 bytes received in three captures (2026-11-09 Phase 2B; 2026-11-18 application and read-only logger). Every inbound claim below is therefore PS at best.

## 1. Gap matrix

| # | CueAir capability | FLOW 8 hardware reality | Class | In flow888 today | Gap |
|---|---|---|---|---|---|
| 1 | Curated channel presets (58, 9 categories, notes, why) | Only EQ gain ×4, Low Cut, 1-knob comp can be written | HV (prior docs) for the 3 writable groups; rest UN | 13 hand-authored presets, not CueAir data | **Large:** no converter, 45 presets missing, no notes/why in UI |
| 2 | EQ frequency / Q / filter type | Fixed band centres, gain only | UN (freq/Q), HV (prior docs) (gain) | Gain sliders only | Projection of CueAir EQ onto 4 fixed bands not implemented |
| 3 | EQ response curve display | n/a | AO | None | Visualiser missing; must be labelled "commanded, not measured" |
| 4 | Compressor (thr, ratio, knee, attack, release, makeup) | One knob 0–100, Ch 1–4 only | HV (prior docs) knob; UN rest | Knob slider | Mapping from CueAir comp settings to knob % undefined; Ch 5–7 have no comp |
| 5 | Gate / expander | None | UN | None | Must be shown as "not available on FLOW 8", never faked |
| 6 | Low cut (HPF) | CC 9, Ch 1–4 | HV (prior docs) | Slider + preset use | Ch 5–7 none (UN) |
| 7 | Preserve Levels | App logic | AO | Always on in practice; the dialog checkbox is a no-op (D-12) | UI is dishonest; behaviour correct only because presets never write level params |
| 8 | Pre-change snapshot ("BEFORE PRESET", "BEFORE AI") | App-side | AO | Not implemented; `SceneManager` stores fader/pan/mute only (D-04) | Snapshot-before-apply missing; scenes ignore EQ/comp/sends; scenes not persisted |
| 9 | Scene save / recall / advance | Hardware snapshot recall PC 1–15 on Ch 16 (PC 16 = mixer reset, forbidden) | AO (store/resend), PS (hardware recall) | RAM-only scenes of fader/pan/mute | Persistence, DSP coverage, scene cards, advance |
| 10 | Undo / redo | App-side with exact inverse | AO | Done; exact-value, atomic | Inspector slider batching (D-03) |
| 11 | FX starting points (48 CueAir presets) | FX1/FX2 slot select via Program Change Ch 13/14 (S0 correction from 14/15); Parameter 1 (CC 1) and Parameter 2 (CC 2) documented, meaning unconfirmed | PS (slot select); UN (decay, size, pre-delay) | 5 FX preset records; slot select not verified | Need slot table, mapping of CueAir `algorithm`/`use` to a real slot; honest "nearest slot" UX |
| 12 | Aux (monitor) sends | CC 14/15, Ch 1–7 | HV (prior docs) Mon 1; PS Mon 2 | Sliders in Inspector | OK; scene coverage missing |
| 13 | FX sends | CC 16/17 | PS | Sliders in Inspector | Not verified |
| 14 | Bus masters (Mon 1/2, FX 1/2) | Ch 9–12 CC 7 | PS | Allowlisted, no UI (D-08) | UI and service wrapper missing |
| 15 | Main fader / balance | Ch 8 | HV (prior docs) | Done | Inbound unverified |
| 16 | Preamp gain | CC 8, Ch 1–4 | HV (prior docs) write | Gated (disabled) in UI (D-07) | Gate decision needed |
| 17 | +48V phantom | CC 12, Ch 1–2 | HV (prior docs) | Confirmation dialog, never in undo/scenes | Keep as is; never automated |
| 18 | Solo / PFL | CC 6 defined, not allowlisted | PS | Absent | Not verified; no feature until tested |
| 19 | Output GEQ (9-band) and limiter on Main/Mon | Ch 8 CC 8, 11–19 per compatibility doc | PS (ASSUMPTION: from documents, not tested) | Absent | Candidate, low priority |
| 20 | Live metering / meters | No meter data over MIDI; USB audio stream carries audio | UN over MIDI; PS via USB audio | "NOT INTEGRATED" | Needs WASAPI capture, not started |
| 21 | State read-back of the whole mixer (`/xremote`, queries) | Write-only; only fader/pan/mute from USB TX | UN (full), PS (fader/pan/mute) | Provenance model (UNSYNCED/COMMANDED/OBSERVED) | Works as designed; inbound blocked today |
| 22 | Network discovery (UDP/OSC) | USB only | UN | WinMM enumeration | n/a |
| 23 | Agent/MCP automation (`propose_changes`, confirm, rollback) | App-side | AO | `CommandLedger` rollback exists; no proposal/preview layer | Staged-plan workflow missing |
| 24 | CueAi recommendations (natural language to parameters) | App-side | AO | None | Research gap (logic unknown), see below |
| 25 | EZ-Gain | Console/BLE only | UN | None | n/a |
| 26 | Multi-channel recording | USB audio 10-in/4-out class driver | PS | None | Out of scope for the stated priorities |

## 2. Features that can be implemented independently

Items 1, 2 (as projection), 3, 7, 8, 9, 10, 11 (slot mapping), 14, 23, plus analysis built on the USB audio stream (20).

## 3. Features that need an alternative workflow

- **CueAir presets with gate and full dynamics:** show a "FLOW 8 fit" report per preset (what is applied, what is approximated, what is dropped).
- **Real measurement:** meters and analysis need the USB audio stream, not MIDI.
- **Mixer state at connect:** no read-back; the app must say "unknown until you move the control" and offer a deliberate "send my values to mixer" action instead of showing guesses.

## 4. Unsupported (do not build, do not show as controls)

Gate/expander parameters, EQ frequency/Q/filter-type, compressor threshold/ratio/attack/release, continuous FX parameters, EZ-Gain remote trigger, SysEx interrogation, network control, phantom on Ch 3–8, gain and low cut on Ch 5–7.
