# CueAir Research Status

Date: 2026-11-18. Scope: audit of existing CueAir reverse-engineering work. No new REA analysis was run. No source code was changed.

Evidence labels: **VERIFIED** = read or run this session. **ASSUMPTION** = believed, not checked. **BLOCKER** = stops progress. **NEXT** = one concrete action.

## 1. What has been researched (existing documents)

| Area | Document | State |
|---|---|---|
| App inventory, bundle layout, binaries | `docs/reverse-engineering/03_CUEAIR_APP_INVENTORY.md` | Complete |
| Technology stack (SwiftUI, XAirCore, `cueair-mcp`) | `04_CUEAIR_TECHNOLOGY_STACK.md` | Complete |
| Subsystems A–M (discovery, state, EQ, dynamics, FX, scenes, safety, CueAi) | `05_CUEAIR_FUNCTION_ANALYSIS.md` | Complete, string-table evidence |
| Call graph, user-action-to-hardware workflows | `06_…CALL_GRAPH.md`, `07_…INTERNAL_WORKFLOWS.md` | Complete, reconstructed (not decompiled line by line) |
| Finding ledger (FIND-01..12) | `08_CUEAIR_FEATURE_MATRIX.md` | Complete |
| CueAir → FLOW 8 class mapping (A–E) | `docs/architecture/CUEAIR_TO_FLOW8_COMPATIBILITY.md` | Complete |
| FLOW 8 protocol and hardware limits | `docs/hardware/*`, `docs/testing/KNOWN_LIMITATIONS.md` | Complete |
| Hardware verification claims | `docs/testing/HARDWARE_VERIFICATION_MATRIX.md` | See §3 |

## 2. Extracted CueAir data (VERIFIED by reading the files this session)

Location: `cueair_extracted/CueAir.app/Contents/Resources/`.

- `cuetone-basic.cueairpreset`: **58 channel presets** (13 stereo), not the "50 + 8 trims" stated in `03_CUEAIR_APP_INVENTORY.md`. Every preset has `preserveLevels: true`, `sections`, `values` (OSC-style keys), `notes` (rationale per parameter) and `why`. Notes and summaries are in Korean.
- Categories and counts: mc, speech, vocal, drums, guitar, keys, bgm, video, correction (`fix-boom`, `fix-mud`, `fix-nasal`, `fix-harsh`, `fix-sibilance-eq`, `fix-plosives`, `fix-peaks`, `fix-speech-level`).
- Per-preset values: 4-band EQ (frequency, gain, Q, type PEQ/shelf), compressor (threshold, ratio, knee, attack, release, makeup, detector, sidechain filter), gate/expander (threshold, range, attack, hold, release, mode), preamp high-pass (`/preamp/hpf`, `/preamp/hpon`), `#headamp/phantom` suggestion.
- FX starting points: `cuetone-fx.json` has **20** and `cuetone-fx-xair.json` has **28**, with algorithm (ROOM, etc.), group (reverb/delay/modulation), `placement`, `use` tags and algorithm-specific values (size, decay, pre delay, hi/lo cut). Vendor files exist for WING, Soundcraft Ui, Allen & Heath CQ and Yamaha TF.
- `cueair-mcp` tools seen in existing documents: `mixer_status`, `strip_detail`, `propose_changes`, `propose_fx_preset`, `scene_save`, `scene_advance`, `scene_card`. The full tool schema list was **not** extracted (see §4).

## 3. Discrepancies found in the existing work

1. **Preset count:** 58 in the file vs "50" in the inventory document. ASSUMPTION: the inventory counted before reading the file.
2. **FLOW 8 presets are not CueAir ports.** `flow8/presets.py` has 13 channel presets and 5 FX presets with ids such as `vocal-worship-ballad` and `speech-mc-handheld`. None of those ids exist in `cuetone-basic.cueairpreset` (VERIFIED by comparing the id list). The module docstring says "ported and adapted"; the values are hand-authored approximations. ASSUMPTION: no automated conversion exists.
3. **"VERIFIED ON REAL HARDWARE" claims for presets** (`HARDWARE_VERIFICATION_MATRIX.md` §3) cannot be re-checked: the mixer has no read-back, and `MMSYSERR_NOERROR` is not DSP confirmation. Treat as "dispatched, accepted by driver, observed by an operator" until the evidence (logs/recordings) is located. NEXT: locate the raw evidence or downgrade the claim.
4. **Inbound telemetry on this machine today:** two independent captures (application and the read-only `flow8_midi_in_logger.py`) received **0 bytes** in 90 s each (a third, 2026-11-09 Phase 2B, also received none; see E17) while the operator moved controls. See `docs/audit/hw_stage1/`. This matches `KNOWN_LIMITATIONS.md` §1.2 (USB TX must be ON). Cause not isolated. BLOCKER for any claim of hardware-synchronised state.
5. **CueAir EQ/dynamics detail does not fit FLOW 8.** CueAir presets carry frequency, Q, ratio, attack, release, gate parameters. FLOW 8 exposes per-band gain only (fixed centre frequencies per the UI labels, ASSUMPTION: not confirmed against Behringer documentation), Low Cut frequency, and one compressor knob. Any "port" is a lossy projection.

## 4. Research gaps (what is still unknown)

> Update: the first two rows (MCP tool list, CueAi logic) were researched afterwards; see `CUEAIR_MCP_AND_RECOMMENDATION_RESEARCH.md`. Result: tools are read-heavy plus propose-only; recommendations come from a cloud language model with a client-side gate, so only the workflow concepts are reusable. Remaining gaps and the ordering are in `ARCHITECTURE_REVIEW_AND_PROPOSAL.md`.

| Gap | Why it matters | NEXT |
|---|---|---|
| Full `cueair-mcp` tool list and JSON schemas | Defines the propose/preview/confirm workflow to copy | Use REA on `Contents/MacOS/cueair-mcp` (strings and Swift reflection); list tools, arguments, safety rules |
| CueAi recommendation logic (what it analyses, what prompts it uses) | Basis for "channel analysis and recommendations" | Extract embedded prompt text and tool descriptions |
| Whether CueAir reads meters/levels | Decides how analysis is fed | Search strings for meter/level OSC paths (`/meters`) |
| Scene file format and snapshot semantics (`scene_save`, `scene_card`) | Scene import/export design | Inspect strings and any saved-scene samples |
| FLOW 8 FX slot names for Program Change 1–16 | Needed to map CueAir FX presets to real slots | Read Behringer documentation / `docs/hardware/FLOW8_PARAMETER_MAP.md`; confirm on mixer |
| FLOW 8 EQ band centre frequencies and CC value→dB curve | Needed for EQ projection accuracy | Confirm against official FLOW 8 MIDI spec |
| Licensing of CueAir preset data | Copying 58 curated presets and notes may not be allowed | **Decision for the project owner** (see roadmap) |

## 5. Conclusion

The reverse-engineering of structure, workflows and data is largely done. The product-relevant gap is conversion: the CueAir preset corpus is not yet used, and two research items (MCP schemas, recommendation logic) are missing. Hardware-synchronised state is unverified today.
