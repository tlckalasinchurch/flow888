# Architecture Review and Prioritized Implementation Proposal

Date: 2026-11-18. Inputs: the four product documents, `CUEAIR_MCP_AND_RECOMMENDATION_RESEARCH.md`, all existing CueAir research under `docs/reverse-engineering`, `docs/architecture`, `docs/testing`, the extracted CueAir files, current `flow8/` source. No source code was changed. Classes (HV / PS / AO / UN) are defined in `CUEAIR_FEATURE_GAP_MATRIX.md`.

## 0. Decisions applied

| Decision | Effect |
|---|---|
| Option A for presets | Original FLOW 8 presets; CueAir is a concept reference only; no copied values, descriptions or text; rationale recorded per preset |
| Gain stays gated | No gain control until mapping, range, safety and physical operation are independently verified |
| Hardware investigation paused | D-01 BLOCKED, D-02 NOT TESTED, D-05 NOT TESTED on hardware. No listener changes without new evidence |
| Offline development continues | Every inbound/hardware claim keeps its honest class |

## 1. Contradictions and problems found

| # | Finding | Evidence | Resolution |
|---|---|---|---|
| C1 | **Existing 13 presets claim to be "ported and adapted from CueAir"** (`flow8/presets.py` docstring; `FLOW8_FEATURE_ADAPTATION.md`) | VERIFIED by reading the module header | Conflicts with Option A. Treat them as *legacy, provenance unaudited*. Stage S3 replaces them with original presets that each carry a rationale; until then they are not marketed as CueAir-derived |
| C2 | Inventory says 50 presets; file has 58 | VERIFIED | Recorded in `CUEAIR_RESEARCH_STATUS.md`; the original inventory file `03_CUEAIR_APP_INVENTORY.md` still says 50 and is not edited |
| C3 | `HARDWARE_VERIFICATION_MATRIX.md` shows presets "VERIFIED ON REAL HARDWARE", but DSP cannot be read back | `KNOWN_LIMITATIONS.md` §1.1 | Downgrade wording to "dispatched and operator-observed (prior documents, evidence not located)" until raw evidence is found |
| C4 | The old compatibility document lists a 9-band GEQ/limiter and Program-Change FX slots as available | `CUEAIR_TO_FLOW8_COMPATIBILITY.md` | Class PS only; not in the verified matrix; no UI until verified |
| C5 | The extraction README in `capture/` is a clean-room notice for a different product (Mixing Station) | VERIFIED by reading it | Not applicable to CueAir; flagged so nobody applies it by mistake |
| C6 | `Preserve Levels` dialog checkbox does nothing (D-12) while docs say levels are guaranteed | `service.py:434-471` | Stage S2 |
| C7 | Scenes labelled as mixer state but hold only commanded values of fader/pan/mute | `scenes.py`, D-04 | Stage S4 wording and coverage |
| C8 | App does not detect USB unplug | ASSUMPTION from reading `app.py`; not reproduced | Recorded as an open item, not worked on (hardware paused) |

## 2. Missing research

| Item | Status | Owner action |
|---|---|---|
| MCP tool list and recommendation logic | **Done** (`CUEAIR_MCP_AND_RECOMMENDATION_RESEARCH.md`). Result: cloud LLM + client gate; concepts are reusable, logic is not | none |
| FLOW 8 EQ band centre frequencies, Q, CC→dB curve | Open. Current UI labels (80 Hz / 400 Hz / 2.5 kHz / 10 kHz) are not backed by a cited source | Read the official FLOW 8 manual/MIDI specification, cite page; compare with `parameter_mapping.py` |
| FLOW 8 FX slot names (16 per FX) and Program-Change numbering | Open | Same sources; mixer confirmation deferred (hardware paused) |
| Compressor 1-knob behaviour (what CC 11 changes) | Open | Official documentation; no inference from CueAir |
| Low-cut range and curve | Existing mapping 20–600 Hz | Confirm against the official specification |
| USB audio stream access | Enumeration only: capture endpoints `Mic 1`, `Mic 2`, `Mic/Line 3/4`, `Line 5/6`, `Line 7/8`, `Main L/R`, `Multi In 1-10` report status OK (VERIFIED by PnP query this session). **No audio has been captured.** No capture library is installed (`sounddevice` and `pyaudiowpatch` both missing) | Stage S9 spike; dependency decision first |
| Signal point of the USB streams (pre/post EQ, fader, compressor) | Unknown | Must be measured in S9 before any analysis claim |
| Original preset authoring basis | Needs a short, citable engineering reference list (typical HPF ranges, mud/boxiness regions, sibilance regions) | Part of S3 |

## 3. Technical dependencies

```
S1 capability table ──┬─> S2 Preserve Levels
                      ├─> S4 snapshots/scenes ──┐
                      ├─> S3 preset engine ─────┼─> S5 Propose→Preview→Confirm→Apply ─> S6 recommendations (rule-based)
                      └─> S7 EQ visual (needs cited band centres)
S8 FX slot research (docs only) ─────────────────────────────> FX feature
S9 audio-stream spike (independent) ─> optional analysis input to S6
```

S4 and S5 depend on the existing `CommandLedger` batch/rollback (done) and the provenance model (done). S3 depends on S1 for what can be written and on the research in §2 for cited constants.

## 4. Product risks

| Risk | Impact | Mitigation |
|---|---|---|
| Presets sound wrong on a real mixer and cannot be read back | Bad tone, user distrust | Every preset has a stated intent and "starting point" wording; undo and pre-apply snapshot always available; no "verified on hardware" label without raw evidence |
| EQ band centres/Q are guesses | A drawn curve misleads | S7 draws only what is cited; otherwise per-band gain markers, not a response curve |
| Snapshot read as mixer state | User trusts a stale value | Wording "values this app commanded"; unknown shown as unknown; UNSYNCED after disconnect (already implemented) |
| Proposal "before" is unknown for most parameters | Weak diff | Show provenance next to every "before"; require explicit confirm for unknown-before changes |
| Rule-based recommendations over-claim | False advice | Each recommendation states its inputs and confidence; no audio-based claim before S9 proves stream access |
| Preset content resembles CueAir | IP exposure | Authoring from engineering principles; provenance record per preset; legacy 13 replaced; no copying of text or numbers |
| Inbound telemetry still blocked | Observed values unavailable | Application stays command-driven; observation features labelled unverified |
| Scope creep into defects | Product stalls | Defects fixed only when they block a stage (listed per stage) |

## 5. Original FLOW 8 Preset Engine: design

**Principle:** presets are authored in FLOW 8 native terms (per-band dB at the four fixed bands, low-cut Hz, compressor percent), not projected from CueAir parameters. Nothing is "identical to a CueAir preset" and the UI never says so.

**Data model (`OriginalPreset`):** `id`, `name`, `category`, `intent` (one sentence), `applies_to` (allowed channels), `eq_db` {low, low_mid, hi_mid, hi}, `low_cut_hz` or none, `comp_percent` or none, `rationale` (one entry per written parameter: why this number, in engineering terms), `inspired_by` (CueAir concept names such as category, "correction preset", "levels preserved", "why note"; no values), `fit` (what FLOW 8 can/cannot express for this intent, e.g. "no gate on FLOW 8"), `provenance` (author, date, basis references), `status` (`draft`, `reviewed`; never "hardware verified" without evidence).

**Categories (concept parity with CueAir):** speech/MC, vocal, drums, guitar/bass, keys, backing/BGM, correction (boom, mud, nasal, harsh, sibilance, plosive, level), utility.

**Rules enforced in code (later stage):** a preset cannot contain fader, pan, gain, phantom or send fields (structural Preserve Levels); every written parameter must have a rationale; channel applicability checked (low cut/comp only Ch 1–4); presets validated against the capability table.

**Applying:** goes through the S5 workflow (propose → preview → confirm → apply), after an automatic application-held snapshot, as one undo step.

## 6. Prioritized implementation proposal

Stage order follows your Decision 4. Each stage is one reviewable change; stop for approval between stages. Every stage ends with the full regression result reported as passed / failed / skipped / expected-failure, hardware tests reported separately (currently BLOCKED or NOT TESTED), and documents updated.

### S0. Research closure (docs only)
- **Scope:** cite FLOW 8 EQ centres/Q/curve, compressor knob meaning, low-cut range, FX slot list, from official documentation; correct C3/C4 wording; record sources.
- **Acceptance:** each constant used by later stages has a citation or is marked UNCONFIRMED; no code change; contradictions C1–C8 each have a recorded status.

### S1. Capability table (single source of truth)
- **User problem:** UI and gates disagree about what is real.
- **CueAir reference:** `MixerCapabilities` / `Feature` (writable, readOnly, risk, requiredLink).
- **Hardware:** records classes HV/PS/AO/UN per parameter and channel, including "readable: no".
- **Approach:** a data module generated from existing verified matrix + `command_boundary` allowlist; read-only consumers first.
- **Acceptance:** test proves every allowlisted parameter has an entry and class; test fails if the UI offers a control whose class is UN; gain entry is `gated` with reason; +48V entry is `confirmation required, never automated`; a parameter without an entry cannot be proposed.

### S2. Honest Preserve Levels (D-12)
- **Approach:** remove the checkbox; show a fixed statement; structural guarantee that preset application cannot issue fader/pan/gain/phantom commands.
- **Acceptance:** test records every command emitted while applying every preset to every allowed channel and asserts only EQ/low-cut/compressor commands; the dialog has no toggle; docs no longer imply a toggle.

### S3. Original Preset Engine and library
- **Scope:** data model of §5; at least the categories listed, each preset with rationale; legacy 13 marked legacy then replaced after review.
- **Acceptance:** schema validation test (every written parameter has a rationale; channel applicability; ranges in FLOW 8 terms); provenance and `inspired_by` fields present and contain no CueAir numbers or text (automated check against the extracted corpus: no preset notes copied verbatim, no identical value sets); picker shows intent, rationale, fit limits and "starting point, not measured"; user review sign-off recorded before status `reviewed`; undo restores exact commanded values (existing behaviour tested).

### S4. Application-managed snapshots and scenes (D-04)
- **Approach:** snapshot = *values this app has commanded or observed*, with provenance per value; unknown excluded and listed; automatic snapshot before preset/scene recall/plan apply; JSON persistence; scene cards show contents; overwrite and load confirmations distinct.
- **Acceptance:** UI and files never say "mixer state"; round-trip test covers EQ, low cut, comp, sends, fader, pan, mute; phantom and gain excluded; restart keeps scenes; recall is one undo step and reports parameters not sent; after disconnect, recall is blocked or clearly warned.

### S5. Propose → Preview → Confirm → Apply
- **CueAir reference:** `Proposal`, `CueAIProposalGate`, epochs, `needsHostReview`, apply steps.
- **Approach:** a `ChangePlan` object (parameter, before with provenance, after, reason, risk); gate checks capability table, ranges, channel applicability, stereo-pair rules; epoch invalidated by disconnect, undo, or any command on the same parameters; preview sends nothing; commit uses ledger batch and an S4 snapshot.
- **Acceptance:** preview emits zero MIDI (test); stale plan refuses to apply (test: change a value after propose); unknown-before shown as "unknown" and needs explicit confirm; partial failure rolls back; one undo step; phantom and gain can never appear in a plan.

### S6. Rule-based recommendations (deterministic)
- **Scope:** takes user-selected symptom (boomy, muddy, harsh, sibilant, plosive, level) and channel; returns an S5 plan from S3 correction presets; states inputs used; no claim from audio.
- **Acceptance:** each symptom gives the documented plan for the channel type; the explanation lists inputs and limits ("based on your choice, not on a measurement"); no network use.

### S7. EQ visualisation
- **Approach:** if S0 confirms band centres and shape, draw a response curve labelled "commanded, modelled"; if not, draw per-band gain markers only. Grey when provenance is UNSYNCED.
- **Acceptance:** drawing function unit-tested against the cited model; updates on undo/redo/preset without rebuilding; shows absent features (no comp on Ch 5–7); screenshots from the running app at 1600×900 and 1366×768.

### S8. FX slot mapping research and design
- **Scope:** documentation of the 16 slots per FX from official sources; a mapping from original FX recommendations ("small room for speech", "plate for vocal") to slots; Program Change sent only after hardware verification (paused), so this stage ships as design plus offline data.
- **Acceptance:** slot table cited; UI design states "slot selection only; parameters fixed by firmware"; no continuous FX controls designed.

### S9. Audio-stream analysis feasibility (spike, no product claims)
- **Scope:** prove or disprove that the app can open a FLOW 8 USB capture endpoint and read samples; measure signal point (pre/post fader and EQ) with controlled tests; check coexistence with other software (exclusive access).
- **Dependencies:** decision to add a capture dependency; operator at the mixer.
- **Acceptance:** a recording of at least 10 s from one named endpoint with level shown; a written statement of the signal point backed by an A/B test; if either fails, the analysis feature is recorded as NOT FEASIBLE or BLOCKED. No analysis feature ships before this passes.

## 7. Defects allowed during these stages

D-12 (S2), D-04 (S4), D-03 (S3/S5 undo quality for inspector edits), D-06 (inspector fit for S5/S7), D-14 (only if it breaks tests). Everything else is deferred. D-07 gain stays gated. D-08 bus masters and solo wait for verified hardware.

## 8. First actions (proposed, awaiting approval)

1. S0 documentation research with citations (no code).
2. Then S1 and S2, which are small and unblock the rest.

Stop condition: no implementation until you approve this proposal.
