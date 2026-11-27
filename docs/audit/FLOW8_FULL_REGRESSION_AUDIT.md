# FLOW 8 Full Regression Audit (TASK 05)

- Date: 2026-11-27. Read-only: no source, test, configuration or safety file was changed by this audit.
- Base: `main` at `6a9b8c6` plus the uncommitted working tree (TASK 01–04 and earlier rounds). Nothing committed.
- Evidence folder: `docs/audit/regression_2026-11-27/` (copies of the runs below).
- Labels: **VERIFIED** = observed this session with the command named; **NOT VERIFIED** = no evidence yet.

## 1. Executive Summary

**AUDIT PASSED WITH WARNINGS.**

- Full suite (`python -m tools.run_tests_no_hw`): **530 ran, 525 passed, 0 failed, 0 errors, 5 skipped** (hardware tests, disabled by default), **0 attempted physical port opens**, 125 s. VERIFIED.
- All 43 TASK 01–04 tests pass, three runs in a row (once in the full suite, twice alone). VERIFIED.
- The Phase 2 Playwright harness, rerun after the fixes: S1–S5 VERIFIED PASS on desktop and iPad (S2–S5 were VERIFIED FAIL before), 23/23 payload checks, 14/14 regression checks, 0 physical MIDI calls. VERIFIED.
- Safety layer, MIDI allowlist, channels and CCs unchanged (no diff in `safety.py`, `midi_out.py`, `transport_router.py`, `parameter_mapping.py`, `parameter_engine.py`; allowlist builders identical to `HEAD` by AST). VERIFIED.
- No regression found. Warnings: real **read-only** winmm device-enumeration calls in 27 tests (§6); browser tests depend on an undeclared Playwright install and skip silently without it (§7); the Phase 2 harness is now outdated for S6–S8 (§7); D07/D08 open.

## 2. Repository Integrity

| Check | Result | Evidence |
|---|---|---|
| Branch / HEAD | `main` / `6a9b8c6` | `git branch --show-current`, `git log -1` |
| Modified tracked files | 11: `DESIGN.md`, `flow8/{audio_meter,command_boundary,lan_hub,midi_in,service,web_console}.py`, `flow8/web_ui/{app.js,index.html,styles.css}`, `tests/test_web_cache.py` (680+ / 283−) | `git diff --stat` |
| Untracked | v3 console (`flow8/web_ui/v3/`), tests (`test_v3_{console,mute_groups,text_inputs,guards,geq_keyboard}`, `test_instrumentation`, `test_live_performance_fixes`, `test_ui_provenance_display`), audit docs and evidence, `.fast/`, design/impeccable files, `run_flow8.bat` | `git status --short` |
| TASK 01 present | `groupState`, `GROUP_PRESSED`, no `g.on` (0 matches) | grep `v3.js` |
| TASK 02 present | `ui.cueDraft`, `id="grp-name"`, caret restore `setSelectionRange` in `render()` | grep `v3.js` |
| TASK 03 present | `#cue-add` locked guard + `disabled`; `toggleMute` `mixerReady()` guard; `aria-disabled` on strip MUTE | grep `v3.js` |
| TASK 04 present | `id="geq-N"`, `GEQ_STEP`, shared `set()`, GEQ `onkeydown` | grep `v3.js` |
| Unauthorised changes | None found. Python diffs are: earlier approved rounds (T1 SSE close, M2 bounded log, §7 instrumentation, logging) and uncommitted work that pre-dates this session (gzip, `/v3/` routes, rx `_source` tag, `_notify_listeners(source)`) | `git diff -U0` per file |

The v3 files are untracked, so `git diff` cannot show TASK 01–04 line by line; presence was checked by content.

## 3. TASK 01–04 Regression Matrix

All rows VERIFIED by the full-suite run (verbose, `regression_2026-11-27/winmm_call_audit.txt` run) and two further runs of the four modules (43/43 OK each).

| Defect | Test file | Test functions | Expected | Actual | Status |
|---|---|---|---|---|---|
| D01 cue draft | `tests/test_v3_text_inputs.py` | `test_cue_name_survives_a_local_rerender`, `…_another_devices_command`, `…_the_5_second_reload`, `test_cue_name_caret_is_kept`, `test_save_sends_the_same_payload_and_clears_on_success`, `test_refused_save_keeps_the_typed_name`, `test_empty_name_is_refused_without_a_request`, `test_draft_is_not_saved_by_itself`, `test_cue_name_is_rendered_from_ui_state` | Text and caret survive re-renders; SAVE payload unchanged | As expected | VERIFIED PASS |
| D02 mute group | `tests/test_v3_mute_groups.py` | `test_success_lights_the_lamp_from_confirmed_mutes`, `test_503_does_not_light_the_lamp`, `test_dispatch_error_does_not_light_the_lamp`, `test_reconnect_shows_unknown_not_a_remembered_on`, `test_reload_and_second_device_read_the_hub`, `test_unknown_members_read_unknown_and_tap_mutes`, `test_channel_held_by_another_on_group_stays_muted`, `test_no_client_side_on_flag`, `test_lamp_is_derived_from_channel_mute_provenance` | Lamp from hub mute + provenance; never on after a refusal | As expected | VERIFIED PASS |
| D03 group focus | `tests/test_v3_text_inputs.py` | `test_group_name_keeps_focus_and_caret`, `test_focus_returns_to_the_group_being_edited`, `test_group_name_is_normalised_on_done`, `test_group_name_input_has_a_stable_id` | Focus and caret kept; tidy on DONE | As expected | VERIFIED PASS |
| D04 GEQ keyboard | `tests/test_v3_geq_keyboard.py` | 12: Tab order, Up/Right, Down/Left, repeat, Home/End, limits, ARIA, per-bus payload, mouse unchanged, no-focus, no scroll, locked | Keyboard via the mouse's mapping; ARIA = visible value | As expected | VERIFIED PASS |
| D05 LOCK save | `tests/test_v3_guards.py` | `test_locked_save_button_is_disabled`, `test_locked_handler_refuses_even_if_the_button_is_enabled_by_script`, `test_unlocked_save_works_as_before`, `test_refused_save_shows_no_success` | No `librarySave` while locked | As expected | VERIFIED PASS |
| D06 MUTE ready | `tests/test_v3_guards.py` | `test_disconnected_mute_sends_nothing_and_says_why`, `test_disconnected_mute_handler_refuses_a_scripted_click`, `test_connected_mute_works_as_before`, `test_guard_follows_a_disconnect_after_page_load_and_a_reconnect`, `test_unannounced_drop_is_still_refused_by_the_hub` | No `setMute` while no mixer; hub 503 in the unannounced window | As expected | VERIFIED PASS |
| D07 lock persistence | — | Phase 2 S8 | — | Not rerun (harness S8 blocked, see §7); open by decision | OPEN |
| D08 history | — | Phase 2 S9 | Back stays in the console | `about:blank` (rerun) | OPEN (VERIFIED FAIL, expected) |

Independent end-to-end rerun (`regression_2026-11-27/harness_rerun_report.json`, Phase 2 harness without S6–S8): S1–S5 VERIFIED PASS, S9 VERIFIED FAIL, on both viewports.

## 4. Full Test Suite Results

| Item | Value | Evidence |
|---|---|---|
| Command | `python -m tools.run_tests_no_hw` | `regression_2026-11-27/run_tests_no_hw.log` |
| Ran / passed / failed / errors / skipped | 530 / 525 / 0 / 0 / 5 | same |
| Attempted physical port opens | 0 | same |
| Duration | 125.2 s (`Ran 530 tests in 125.158s`; 137 s wall) | same |
| Skipped | `test_hardware_midi_out`: `TestHardwareEndpointsNonMutating` ×4, `TestHardwareParameterDispatchMutating` ×1. Reason: "Physical hardware tests are disabled by default (nothing was transmitted). Set FLOW8_HW_TESTS=1 …" | `winmm_call_audit.txt` (SKIPPED) |
| Independent run with winmm counting | 530 ran, 0 failed, 0 errors, 5 skipped | `winmm_call_audit.txt` (RESULT) |

## 5. Safety & MIDI Integrity

| Check | Result | Status |
|---|---|---|
| `safety.py`, `midi_out.py`, `transport_router.py`, `parameter_mapping.py`, `parameter_engine.py` | 0 diff lines | VERIFIED |
| Allowlist | 133 entries, channels 1–14 only (no 15/16); `_build_phase_c_allowlist`, `_validate_allowlist`, `_expected_channel_for_param` identical to `HEAD` (AST compare) | VERIFIED |
| `command_boundary.py` diff | Only the log storage (`deque` + counters, `_append`); validation/dispatch path unchanged | VERIFIED (diff read) |
| New MIDI send path | None. v3 sends only through `action()` → `POST /api/action`; action set unchanged (applyPreset, begin/endGesture, libraryLoad/Save, muteAll, undo/redo, resetEqFlat, runShowMode, setActiveBus, setBusFader, setBusGeq, setBusLimiter, setEqBand, setFader, setFxParam, setFxPreset, setMute, setSend, plus setLowCut/setCompressor via `bindRange`) | VERIFIED (grep) |
| Gain / +48V in v3 | 0 matches for `setGain`, `setPhantom`, `set48V`, `includePhantom`; hub refuses both with 403 and no MIDI (harness rerun) | VERIFIED |
| Channel 15/16 output | 0 of 144 messages per viewport in the harness rerun; none outside the map | VERIFIED (fake driver) |
| Guards bypassed | None: TASK 03/04 add guards; the hub's 503/403 paths are still exercised by tests | VERIFIED |
| Business logic | No hub action, safety or routing change in TASK 01–04 (all client-side in `v3.js`/`v3.css`) | VERIFIED |
| Evidence baseline hashes | 31/31 OK | VERIFIED (`sha256sum -c docs/product/evidence_baseline.sha256`) |
| Mixer applies the commands | — | NOT VERIFIED (no hardware) |

## 6. Hardware Safety

| Check | Result | Status |
|---|---|---|
| Tests use fake MIDI OUT | `fake_open_port` (MagicMock driver) in every browser rig and the harness | VERIFIED |
| MIDI IN in the v3 rigs | flagged open with a fake handle; `_winmm` mocked (TASK 03 fix) | VERIFIED: 0 `midiIn*` calls in the counting run |
| Physical port opens / MIDI sends | 0 `midiOutOpen`, `midiInOpen`, `midiOutShortMsg`, `midiOutLongMsg` across 530 tests (all blocked and counted) | VERIFIED |
| Other real driver calls | **Warning:** `midiOutGetNumDevs` ×34 and `midiOutGetDevCapsW` ×102 in 27 tests (`test_lan_hub_*`, `test_status_dispatch`, `test_instrumentation`, `test_snapshots_library`, `test_web_cache`, …). Cause: `/api/status` and `/api/session` call `transport_status()`, which lists MIDI OUT device names when disconnected. Read-only enumeration: no port opened, no MIDI sent, no driver state changed. Not introduced by TASK 01–04 | VERIFIED (`winmm_call_audit.txt`) |
| Hardware test skips | 5, by design (env var gate) | VERIFIED |
| Real FLOW 8 | not connected, not opened | VERIFIED (no open calls) |

## 7. Test Environment

| Check | Finding |
|---|---|
| Playwright / Chromium declared | **No.** The repo has no dependency manifest (no requirements, pyproject, setup or Pipfile). Playwright 1.65.0 and its Chromium are installed on this machine only. |
| Without Playwright | 39 browser tests skip (`skipUnless(BROWSER)`); only 4 static tests still run. A machine without Playwright reports green while testing none of the TASK 01–04 behaviour. **Warning.** |
| Repeatability | 3 consecutive green runs; 78–80 s for the 43 v3 tests. Tests wait with fixed `wait_for_timeout` (38 call sites), so a much slower machine could produce false failures. NOT VERIFIED elsewhere. |
| Driver mocking | MIDI OUT fake; MIDI IN `_winmm` mocked in all four v3 rigs. Enumeration calls (§6) come from hub tests outside TASK 01–04. |
| Can tests pass without real behaviour? | Static tests (4) check source text only. All behaviour claims rest on the 39 browser tests, which drive the real page against a real hub with real pointer/keyboard events. Touch input and Safari/WebKit are not covered. |
| Phase 2 harness (`docs/audit/phase2_2026-11-27/phase2_harness.py`) | **Outdated for S6–S8.** After TASK 03 the SAVE button is `disabled` and strip MUTE is `aria-disabled`, so Playwright refuses the plain clicks; S7's exception leaves the hub disconnected and cascades into S8 and the payload section. The same behaviour is covered by `tests/test_v3_guards.py`; the rerun without S6–S8 passed. It is a historical evidence copy and was not edited. |

## 8. Known Limitations

- No hardware: nothing about the real FLOW 8 (applied values, FX channel 13/14 question, audio meters) is verified.
- Between an unannounced unplug and the next state update, v3 cannot know the mixer is gone; the hub refuses with 503 and sends no MIDI (tested).
- GEQ: after a reload the shown value follows the existing raw mapping (e.g. −1.0 dB → −0.9 dB); mapping unchanged by design.
- Browser tests: Chromium desktop only; mouse, not touch; fixed waits.
- Pre-existing (not TASK 01–04): `Flow8Service._notify_listeners` retries a listener with two arguments when it raises `TypeError`; a listener that raises `TypeError` internally would run twice. Observation only.

## 9. Open Defects D07–D08

| ID | Sev | State |
|---|---|---|
| V3-D07 | P3 | LOCK lost on reload. Needs the owner's decision (persist per device or not). Untouched. |
| V3-D08 | P4 | Browser Back leaves the console. Rerun still VERIFIED FAIL. Planned for the UX phase. |
| U-1 | P3 UX | Bottom row 7 px below the fold at 768 px height. UX phase. |

## 10. Risk Assessment

| Risk | Level | Note |
|---|---|---|
| Regression from TASK 01–04 | Low | All targeted and existing tests green ×3; harness rerun green |
| Safety / MIDI change | Low | No diff in safety path; allowlist identical; fake-driver output inside the map |
| Silent loss of browser coverage | Medium | Undeclared Playwright dependency; skips look like passes |
| Timing flakiness | Low–Medium | Fixed waits; stable on this machine |
| Real driver enumeration in tests | Low | Read-only; present before TASK 01–04 |
| Hardware behaviour | Unknown | Not authorised, not tested |

## 11. Recommended Next Steps

1. Owner decision on V3-D07 (persist LOCK per device or not).
2. Declare the browser-test dependency (a test requirements note, or make the runner report "browser tests NOT RUN" instead of plain skips) so missing Playwright cannot look green.
3. Update the Phase 2 harness S6/S7 to use real-click `force=True` and restore the hub on failure, if it will be reused.
4. Optionally stub `list_device_names` in hub tests to remove the read-only enumeration calls.
5. Then: D08 / U-1 in the UX phase, the commit of TASK 01–04 when the owner asks, and the hardware soak only with explicit per-stage approval.
