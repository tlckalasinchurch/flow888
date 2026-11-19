# Implementation Priority

Date: 2026-11-18. Order of work derived from `FLOW8_PRODUCT_ROADMAP.md`. No source code is changed by this document. Each step is one reviewable stage; do not start the next without approval.

## Ranking rule

1. Audio safety and state integrity first.
2. Then features that deliver CueAir's core value: intelligent presets, safe application, snapshots.
3. Then features that need new capability (audio capture, FX slots).
4. Defects only when they block a ranked feature.

## Order

| Rank | Step | Feature | Size | Blocked by | Why this position |
|---|---|---|---|---|---|
| 0 | P0 | F0 inbound telemetry + unplug detection | S–M | Operator and mixer access (BLOCKER: 0 bytes received today) | Without it, no inbound/reconnect claim can be made. Does not block offline work below |
| 1 | P1 | Owner decisions: preset data licensing; keep gain gated or confirmation | none | Owner | Decides F1 data source and D-07 |
| 2 | P2 | Research: `cueair-mcp` tool schemas, CueAi logic, FLOW 8 EQ centres and FX slot names | S | none | Cheap, unblocks F1 accuracy, F5, F6 |
| 3 | P3 | F2 honest Preserve Levels (D-12) | XS | none | Removes a safety-relevant UI lie, independent of data |
| 4 | P4 | F3 snapshot-before-change + full scenes + persistence (D-04) | M | P3 not required | Gives the safety net F1 and F7 depend on |
| 5 | P5 | F1 preset converter and library | L | P1, P2 | Core product value |
| 6 | P6 | F7 staged change plan | M | P4 | Required before any automated recommendation can apply anything |
| 7 | P7 | F4 EQ curve visualiser | M | P2 | Uses F1 projection maths |
| 8 | P8 | F8 inspector fit at 1366×768 (D-06), batching (D-03) | M | none | Makes the inspector usable for F1/F4/F7 |
| 9 | P9 | F5 FX slot mapping | M | P2; mixer test of Program Change | Needs hardware verification |
| 10 | P10 | F6 channel analysis | L | audio capture spike; P5, P6 | Largest unknown; last |
| 11 | later | Bus masters (D-08), solo, GEQ | M | F0 verified | Only after inbound works and CC tested |

## Per-step acceptance gate

Every step ends with: full test suite result with passed/failed/skipped/expected-failure counts reported separately; hardware tests reported separately as PASS / FAIL / BLOCKED / NOT TESTED; screenshots only from the running application; documents updated. A feature is called "Hardware Verified" only with raw logs or recordings that show the physical effect.

## Test classes of evidence

- Offline: unit and GUI tests with the real service, no ports opened.
- Hardware write: operator-observed, records the values restored afterwards. No read-back exists, so "restored" means the app resent known values.
- Hardware read: raw MIDI IN log with timestamps; requires USB TX ON.
- Audio capture (F6): recordings with channel mapping documented.

## Safety rules that stay in force

+48V is never automated, never in undo or scenes, always behind the confirmation dialog. Gain is not written without owner approval. No parameter whose address is unverified is exposed as a control. `MMSYSERR_NOERROR` is never reported as DSP confirmation.

## Immediate next actions (smallest first)

1. Owner: choose the preset data option A/B/C (roadmap).
2. Owner at the mixer: confirm USB TX is ON and re-run the read-only logger, or tell me to stop hardware work for now.
3. Run research P2 (read-only analysis of the existing extraction).
4. Then P3 and P4 (offline, test-covered).

## Status update (2026-11-19)

- **P6 / F7 delivered** on `stage2-mixer-workstation`: plan model, read-only preview against known
  values, one-transaction commit with snapshot-before-change and fail-closed rollback, two LAN
  actions, and a console review panel. 17 new tests. Report:
  `F7_CHANGE_PLAN_IMPLEMENTATION.md`.
- **P3 / F2** needed no further code change: the preset dialog carries no level checkbox, its
  footer states the guarantee, and the apply path contains no fader/pan/gain/phantom command at
  all (asserted by `tests/test_preset_service.py`). Only the dead `preserve_levels` argument
  remains in the service signature for callers.
- **P4 / F3** was already met: scene capture stores EQ, low cut, compressor and sends, and the
  snapshot library persists to JSON, so F7 could rely on it.
- Next ranked step: **P7 / F4** (EQ curve from commanded values). F1 still waits on the owner's
  preset-data decision; F5 waits on a hardware Program Change test.
