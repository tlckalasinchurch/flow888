# CueAir MCP Tools and Recommendation Logic: Research Addendum

Date: 2026-11-18. Closes the two research gaps listed in `CUEAIR_RESEARCH_STATUS.md` §4.

## Method and limits

- **Method (VERIFIED, run this session):** printable-string extraction from `cueair_extracted/CueAir.app/Contents/MacOS/cueair-mcp` (12,229 unique strings) and from the main `CueAir` binary, plus reading Swift type-reflection names (field and type names). No decompilation, no network traffic captured, no running of CueAir.
- **What this gives:** names, field structure and the shape of the workflow. **What it does not give:** exact request/response JSON, server behaviour, or the complete prompt.
- **Content handling:** the binaries contain CueAir's instructional text for its language model. This document records what the text does (behavioural rules) in our own words and does not reproduce it. Per the project decision, nothing here is a source of copied values or text for our presets.
- Labels: VERIFIED = seen in the strings this session. ASSUMPTION = inferred from names.

## 1. MCP tool list (`cueair-mcp`)

| Tool name | Evidence | Role (ASSUMPTION unless noted) |
|---|---|---|
| `mixer_status` | string seen with text "structure"/"capabilities" (VERIFIED) | Read: overall connection/capability summary |
| `mixer_overview` | truncated inline string `mixer_ov…` (ASSUMPTION on the full name) | Read: all strips with names and known fields only |
| `strip_detail` | VERIFIED | Read: detailed values for selected strips |
| `fx_catalog` | VERIFIED | Read: available FX starting points |
| `fx_detail` | VERIFIED | Read: values of one FX |
| `propose_changes` | VERIFIED | Write-intent: propose parameter changes with a reason; does not apply |
| `propose_fx_preset` | VERIFIED | Write-intent: propose an FX starting point |
| `scene_list`, `scene_card`, `scene_save`, `scene_advance` | truncated inline strings `scene_li/ca/sa/ad` (ASSUMPTION on the full names; `scene_save`, `scene_card`, `scene_advance` seen in full) | Scene listing, scene summary card, save, step to next scene |
| (other) | `tf_clear_cue_plans` appears in strings | Yamaha TF specific; not relevant to FLOW 8 |

Error/status strings: `unsupported_mixer`, `unsupported_tool`, `no_mixer`, `request_conflict`, `confirm_overwrite`, `confirm_sceneload`. The tool set is read-heavy; there is no direct "set value" tool. Writes go only through the propose tools and the app's own confirmation.

## 2. Recommendation workflow (how "CueAi" works)

**Architecture (VERIFIED by structure, ASSUMPTION on details):** the recommendation is produced by a language model, not by local signal analysis. The app (or MCP) builds a **snapshot** of mixer state and sends it with the user's message. Evidence: request model fields `session, venue, context, message, history, snapshot, answer, corrections, retryOf, capabilities, eventNotes, done`; account text about paid requests, held credits and settlement; an embedded read-only, no-approval CLI configuration for an LLM runner. So the "logic" is prompt plus data plus client-side validation. We cannot and should not copy the prompt; we can copy the **workflow concepts**.

**Concepts observed:**

1. **Overview first, detail on demand.** The snapshot carries all strips as id+name, with detailed values only for selected strips (size limit). The model is told not to judge strips it has no detail for and to ask for more (`finish.more` / `finish.next`). It must state exactly what was read.
2. **Missing means unknown.** Fields that are unavailable are omitted; the model must never assume defaults.
3. **Capabilities are data.** `MixerCapabilities` / `Feature` carry per-parameter: title, address, format, `readOnly`, `writable`, `requiredLink`, `warning`, `note`, `models`, `risk`. A `Value` carries `canWrite`, `allowedValues`, `reasonKey`, `readbackOf`, `revision`, `state`. Proposals must stay inside device limits; the app clamps anything outside.
4. **Proposal object.** `Proposal` has label, what, before, after, reason, state, `needsHostReview`. Proposals are grouped (`GroupRisk`), carry ids, and belong to an **epoch**.
5. **Gate.** `CueAIProposalGate` validates proposals. Proposals on linked channels or buses are rejected and described as manual steps. If mixer values changed since the proposal, **nothing is applied** and the model must re-read (`strip_detail`/`fx_detail`) and re-propose (`invalidatePendingProposals`, epoch).
6. **Cards.** Visual summary cards (`Card`: title, kind, summary, before/after, marks, min/max/unit, samples, counts, channel) show the effect of a proposal, including sample/meter-like data.
7. **Apply flow.** `applyMode`, `Step`, `Confirm`: staged apply with confirmation; verification failure means "No changes were sent".
8. **Phantom as a separate choice.** A preset `Plan` has `includePhantom`; the preset text says level/gain/trim/fader/phase/patch/send are kept, compressor makeup is included, and 48V is a separate opt-in after the device is checked.
9. **Scene safety.** Overwrite and scene-load confirmations are distinct messages.
10. **Meters.** `MixerCapabilities.MeterTarget` exists: CueAir reads meter data from mixers that provide it over OSC.

## 3. Implications for FLOW 8 (feeds the architecture review)

| CueAir concept | FLOW 8 consequence |
|---|---|
| Local cloud-LLM recommendation | **Out of scope.** No cloud dependency or paid service is planned. Recommendations will be deterministic, rule-based and explainable |
| Capabilities as data | Adopt: a `FLOW 8 capability table` (parameter, channels, range, writable, readable, verification class, risk). Single source for UI and the proposal gate |
| Proposal + gate + epoch | Adopt. On FLOW 8 "before" is often unknown (no read-back); "values changed" can only be detected from app-known changes and observed events |
| Overview vs detail honesty | Adopt: recommendations state which inputs they used (commanded values, observed values, USB audio analysis) |
| Meters | FLOW 8 sends no meters over MIDI (UNSUPPORTED); only a USB audio stream could provide levels, not yet proven |
| `includePhantom` separate | Keep: phantom is never part of a plan |
| Linked-channel rejection | FLOW 8 stereo pairs (5/6, 7/8) share controls; proposals must respect pair semantics |

## 4. Remaining unknowns

Exact JSON schemas of the tools; the full prompt (deliberately not extracted); how CueAir pairs the audio-meter data with advice; server-side rules. NEXT only if needed: decode the Swift reflection field types for `Proposal`/`Card` more precisely. Not required for our design.
