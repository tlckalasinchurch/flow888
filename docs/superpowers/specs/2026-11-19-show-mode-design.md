# Show Mode (one-tap changeover) - design

Date: 2026-11-19. Status: DRAFT, awaiting owner approval. Nothing is built.

## Intent and why

A solo live engineer (or a musician mixing themselves) runs 4-8 piece gigs from an iPad, with the PC beside the mixer. Between "MC / speaking" and "BAND / live" they currently do four things by hand, in this order, to avoid feedback and reverb on speech:

1. Pull the vocal FX sends to 0.
2. Mute the instrument channels (Ch 2-6 / line in).
3. Unmute the MC mic and raise its fader to speaking level.
4. Bring background music (BT / USB, Ch 7) up quietly.

BAND is the reverse. The pain is time pressure and the fear of a mistake mid-show. Show Mode turns this sequence into one control on the main mixer view, in the safe order, with one-step undo.

## Goals

- Two ready modes on the top bar of the main view: `MC` and `BAND`. Touch targets >= 44 px.
- A mode is an ordered list of steps. It writes only the parameters it lists; every other channel keeps its live value.
- Fixed safe execution order, independent of how the list is written: cut-down group first, bring-up group second.
- A short editor on iPad and PC to change channels, values and steps.
- One undo step restores everything a mode changed.
- Works today: no BLE read-back, no audio stream needed.

## Non-goals (v1)

- Crossfade or timed ramps. Instant write only. A ramp for the BGM fader is a possible follow-up, limited by the MIDI rate limit.
- Hardware snapshot recall (PC 1-15) and anything that reads the mixer's own state.
- Feedback detection / Clip Guard (phase 2, needs `audio_meter.py` wired in).
- Routing, EQ frequency or Q (not writable on FLOW 8).

## Anti-goals

- A mode must never touch +48V phantom or preamp gain, not even through a bad edit or an imported file.
- A mode must never overwrite a value it does not list.
- The screen must never imply the mixer confirmed a change. Values are COMMANDED, not observed (existing provenance rule).

## Constraints (verified in code, 2026-11-19)

- `flow8/change_plan.py`: a plan is up to 64 changes, one per (channel, parameter); parameters limited to `REVERSIBLE_PARAMETERS` (fader, pan, mute, EQ gains, low cut, compressor, FX/Mon sends); each must be on the command-boundary allowlist; phantom and gain are rejected. Commit needs a live preview and is rejected as stale if the mix changed after the preview.
- `Flow8Service.commit_change_plan` runs as one ledger transaction with a pre-change snapshot, so one undo restores it.
- `Flow8Service.recall_scene` iterates a dict, so it has no safe ordering and writes every stored value in scope. This is why Show Mode does not reuse snapshots.
- Capture only stores values the app knows; UNSYNCED values are never captured. A mode therefore carries its own explicit values.
- Values are raw 0-127 (mute is boolean).

## Approaches considered

- A. Top-bar buttons that recall two existing snapshots. Least new code, but overwrites everything in scope, has no safe order, and needs complete captured state (blocked while read-back is unavailable). Rejected.
- B. Mode = ordered macro list on top of `change_plan.py`. Touches only listed parameters, reuses validation, allowlist and undo. **Chosen by the owner.**

## Design (B)

- **Mode model.** `{id, name, steps[]}`; a step is `{action, channels[], value}`. Actions map to existing parameters: mute on/off, fader to value, FX/Mon send to value. Stored as JSON on the host (same place and style as the snapshot library) so PC and iPad see the same modes.
- **Compile.** Steps are flattened to `PlannedChange`s, then ordered: phase 1 = mute-on and any value 0; phase 2 = everything else (unmute, raises). Order inside a phase follows the list. Duplicate (channel, parameter) is merged or rejected, as `make_plan` already requires.
- **Run.** One tap compiles, previews and commits in one server request, so the stale window does not apply. The UI shows a toast with an UNDO button for a few seconds and lists anything the boundary rejected (reported, never hidden).
- **Default templates.** `MC` and `BAND` ship with the step structure and channel roles but **no invented values**. Each step shows NOT SET until the owner sets it, with a "use current value" button that takes the value the app currently knows. A mode with unset steps cannot run.
- **Safety.** Phantom and gain are impossible at the plan layer (validated again on load and import). Show Mode adds no new parameters.

## Decisions the owner has made

- Approach B; instant recall, no crossfade; Show Mode excludes +48V and Preamp Gain; templates `MC / พิธีกร` and `BAND / วงเล่นสด` on the main top bar; single-step undo.

## Calls made by me (to check while reading)

- Ordering rule: phase 1 = mute-on or value 0, phase 2 = the rest, because the current value may be unknown.
- No invented default values; unset steps block running.
- Modes stored on the host as JSON, not in the browser.
- v1 instant only; ramp deferred.

## Owner decision on triggering (2026-11-19)

- Both `MC` and `BAND` run on a short hold (~0.4-0.5 s) with the progress bar (`holdToConfirm`, same helper as MUTE ALL), to stop accidental touches mid-song. An UNDO button stays on screen right after every switch.

Status: APPROVED by the owner on 2026-11-19, including my four calls above.

## Left to the builder

- Exact JSON schema and file location; editor layout; toast timing; how the server request is named.
- Confirm commit dispatch follows the plan's list order (assumed, not yet checked).
- Tests: ordering, no-overwrite of unlisted parameters, phantom/gain rejection (including via a hand-edited file), unset step blocks run, one undo restores all.
