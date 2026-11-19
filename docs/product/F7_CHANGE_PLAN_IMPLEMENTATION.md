# F7: Staged Change Plan — Implementation Report

**Status:** Implemented, offline-verified, browser-verified (simulated connection).
**Date:** 2026-11-19.
**Branch:** `stage2-mixer-workstation`.
**Companion documents:** `FLOW8_PRODUCT_ROADMAP.md` (F7), `IMPLEMENTATION_PRIORITY.md` (P6),
`FLOW8_SAFETY_POLICY.md`, `docs/hardware/FLOW8_PARAMETER_MAP.md`.

## 1. Why

The FlowAi drawer used to apply each suggestion immediately. An engineer could not see
what would change, could not compare it with the current mix, and could not refuse one
line of a multi-parameter suggestion. F7 makes every multi-parameter change a reviewed
object instead of a sequence of commands:

1. **Propose** — a list of (channel, parameter, value, reason, risk). Building a plan sends nothing.
2. **Preview** — each line is shown against the current *known* value with its provenance
   (`OBSERVED`, `COMMANDED`, `UNSYNCED`, ...). An unknown current value is shown as
   `unknown`, never as an invented default.
3. **Confirm / commit** — one request sends every changed value as a single ledger
   transaction, after capturing the known mix state.

## 2. Architecture

| Layer | File | Responsibility |
|---|---|---|
| Plan model | `flow8/change_plan.py` | `PlannedChange`, `ChangePlan`, `PreviewRow`, `ChangePlanResult`; validation against the command-boundary allowlist |
| Service | `flow8/service.py` | `preview_change_plan`, `commit_change_plan`, `_rollback`, `pre_change_snapshot`, `restore_pre_change` |
| LAN API | `flow8/lan_hub.py` | actions `previewChangePlan` (allowed offline) and `commitChangePlan` (needs the mixer) |
| Console UI | `flow8/web_ui/{index.html,app.js,styles.css}` | review drawer with the diff, `COMMIT` / `DISCARD`; FlowAi cards now open a plan instead of applying |

Data flow: UI → `/api/action` → `Flow8LanHub.dispatch_action` → `Flow8Service.commit_change_plan`
→ public `set_*` methods → `Flow8CommandBoundary` → MIDI. There is no new write path.

## 3. Safety invariants

1. **Allowlist, not a second opinion.** A change is accepted only when its parameter id is in
   `Flow8CommandBoundary.ACTIVE_ALLOWLIST`; gain is absent there, so a plan can never carry it.
   `phantom` is not a reversible parameter, so +48V is refused in the model and again in the hub (403).
2. **Preview is read-only.** `preview_change_plan` reads the state store and returns rows; it
   dispatches nothing (asserted by a test that the command log stays empty).
3. **One commit, one undo step.** All changed values are sent inside one ledger batch, so one
   `UNDO` restores every line of the plan.
4. **Snapshot before change, without evicting user scenes.** The known mix state is stored as
   `Flow8Service.pre_change_snapshot` (`BEFORE <title>`), separate from the 15 user scene slots,
   so an automatic snapshot can never push a saved scene out of its ring.
5. **Fail closed.** Validation of the whole plan happens before the first command. If a dispatch
   still fails midway, the batch is cancelled and the values already sent are re-sent from the
   preview's `from` values; the plan then reports `rolled_back`. Values whose previous state was
   unknown cannot be restored, and the result says so instead of claiming a clean rollback.
6. **No fabricated undo.** When a value's current state is unknown, the commit still sends the
   requested value, but `undo_ready` is false and the UI states "previous value unknown, so UNDO
   cannot restore it". The ledger never invents a previous value.

## 4. API

`POST /api/action`

```json
{"action": "previewChangePlan", "title": "FlowAi · CH 01",
 "changes": [{"channel": 1, "parameter": "eq_low_mid", "value": 56,
              "reason": "Take out boxiness", "risk": "medium"}]}
```

Response: `{ok, planId, title, willSend, rows[]}` where each row carries
`channel, parameter, parameterId, parameterLabel, from, fromProvenance, to, status, note, reason, risk`.

```json
{"action": "commitChangePlan", "title": "FlowAi · CH 01", "changes": [ ... ]}
```

Response: `{ok, planId, applied, skipped, rolledBack, snapshot, undoReady}`.
A failed commit answers **409** with the same fields plus `failed[]`; a plan containing
gain or +48V answers **403**; a malformed plan answers **400**; a commit while the mixer is
not connected answers **503** `not_connected`.

## 5. Tests

`tests/test_change_plan.py` — 19 tests:

| Area | Test |
|---|---|
| Model | gain/+48V refused; unsupported (channel, parameter) pairs refused; verified pairs accepted; value/risk/duplicate validation |
| Preview | sends nothing and reports `UNSYNCED`; shows the current value and marks a no-op |
| Commit | one undo step restores every value; pre-change snapshot content; no-op plan stores nothing; partial failure rolls back and leaves no undo step; mute plan |
| LAN | preview rows; 403 for gain; commit applies; 400 for malformed; 503 when offline; preview allowed offline |
| Console contract | review panel elements exist; the console calls preview then commit and never posts a FlowAi command directly |

Full suite: 484 tests before this stage → **503 tests** with the new file (reported in §6).

## 6. Verification evidence

Automated (offline, `Flow8Service(auto_connect=False)`):

```
python -m unittest tests.test_change_plan
Ran 19 tests ... OK

python -m unittest discover -s tests -p "test_*.py"
Ran 503 tests ... OK (skipped=5)
```

Browser (Chromium/Playwright against a local hub with a simulated connected service, no hardware):

```
BEFORE eq_low 64 send_fx1 0
PREVIEW_SUB Preview only — 4 of 4 changes will be sent on COMMIT
PREVIEW_FROM 43 Hz
TOAST Plan committed · 4 changes sent · UNDO restores the mix in one step
AFTER  eq_low 64 eq_low_mid 56 eq_hi_mid 70 low_cut 18 send_fx1 76
UNDO   eq_low 64 eq_low_mid 64 eq_hi_mid 64 low_cut 5  send_fx1 0
CONSOLE_ERRORS []
```

The commit changed four parameters; **one** undo restored all four. Screenshots were captured
from the running console at `tools/output/plan-panel.png` (preview) and
`tools/output/plan-committed.png` (after commit); that folder is git-ignored, so the files stay
local evidence rather than repository content.

Not hardware-verified: the mixer was not connected during this stage, so no claim is made
about the physical effect. The dispatch path is the same boundary every other control uses.

## 7. Known limitations

- **Staleness.** A preview is a read at that moment. If the mix changes between preview and
  commit, the commit still sends the reviewed values; the undo step is built from the values
  that were true at commit time. There is no "plan expired" lock.
- **No recommendation engine.** F6 (analysis) is still out of scope: FlowAi's rules are the
  current source of suggestions. F7 is the gate they must pass.
- **Desktop Tk surface.** The service API is shared, but the Tk interface has no plan panel yet;
  the console web UI is the surface this stage delivered.
- **Plans are not persisted.** A plan lives in the browser until committed or discarded.

## 8. Next

1. P7 / F4 — EQ curve drawn from commanded values, sharing the projection maths.
2. P8 — inspector fit at 1366×768, batch gestures.
3. P9 / F5 — FX slot mapping needs a hardware Program Change test.
4. P0 / F0 — inbound telemetry and unplug detection remain the blocker for any OBSERVED claim.
