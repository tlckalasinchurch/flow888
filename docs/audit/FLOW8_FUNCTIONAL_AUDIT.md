# FLOW 8 Functional Audit

## Phase 2 — Playwright integration audit of the v3 console (2026-11-27)

- Base: `main` at `6a9b8c6` plus the uncommitted working tree of 2026-11-27 (`FLOW8_FULL_UI_INVENTORY.md` §0). No source file was changed in this phase.
- Scope approved by the owner: real `Flow8LanHub` + `Flow8Service` in the test process, fake MIDI OUT from `tests/_safety_helpers.py::fake_open_port`, in-memory library and show modes, Chromium (Playwright 1.65.0) at desktop 1366×768 and iPad 1024×768.
- Harness: `docs/audit/phase2_2026-11-27/phase2_harness.py` (copy of the scratchpad original). Raw results: `phase2_report.json`. Screenshots: `desktop/`, `ipad/`.
- Hardware: none. Real MIDI hardware not opened, nothing sent to a FLOW 8. Hardware test **not authorised**.

### How "no physical port" was proven

Before any `flow8` import, the harness replaces `winmm.midiOutOpen`, `midiInOpen`, `midiOutShortMsg` and `midiOutLongMsg` with functions that count the call and raise. MIDI OUT gets the fixture's `MagicMock` driver. MIDI IN is marked open with a fake handle and never touches winmm; inbound messages are injected by calling `Flow8MidiIn._internal_c_callback` directly. The run ends by printing the counter.

**Result: physical MIDI calls = 0** (both viewports). VERIFIED (`PHYSICAL MIDI CALLS: 0`, `phase2_report.json` → `physicalMidiCallCount`).

### Status vocabulary
VERIFIED PASS · VERIFIED FAIL · BLOCKED · NOT VERIFIED · NOT APPLICABLE. "VERIFIED" here means observed in the browser against the real hub with a fake MIDI driver. It never means the mixer applied anything.

### 1. S1–S9 results

| ID | Check | Desktop | iPad | Evidence (actual) |
|---|---|---|---|---|
| S1 | Range slider (LOW CUT) dragged while the page re-renders: plain drag, drag with another client's command mid-drag, drag held 6 s across the 5 s reload | VERIFIED PASS | VERIFIED PASS | 1 / 1 / 1 `setLowCut` sent; each value reached MIDI (CC9 ch1 = 84, 57, 72). The detached slider still fires `change`. Suspicion disproved. |
| S2 | Cue name being typed survives a re-render | VERIFIED FAIL | VERIFIED FAIL | After another client's event: `''`; after 5.6 s idle: `''`. `S2_cue_name_after_reload.png` |
| S3 | Group-name input keeps focus across a re-render | VERIFIED FAIL | VERIFIED FAIL | focus `grp-name` → `''` (body); typed text kept (`GROUP AX`). `S3_group_name_focus.png` |
| S4 | Mute group state vs. mixer | VERIFIED FAIL | VERIFIED FAIL | Tap A: begin, setMute 1, setMute 2, end — all 200. After reload A shows OFF while ch1/ch2 stay muted. Tap B while hub returns 503: B shows ON; after reconnect B still ON, ch3 unmuted. `S4_group_B_after_rejection.png`, `S4_group_B_after_reconnect.png` |
| S5 | GEQ band operable from the keyboard | VERIFIED FAIL | VERIFIED FAIL | `role="slider"`, 3× ArrowUp → 0 `setBusGeq`. Control: EQ node ArrowUp → 1 `setEqBand`. |
| S6 | SAVE CURRENT MIX while LOCKED | VERIFIED FAIL | VERIFIED FAIL | LOCK on; `librarySave` sent, HTTP 200. Control: fader drag while locked sent 0. `S6_save_while_locked.png` |
| S7 | Strip MUTE while NO MIXER | VERIFIED FAIL | VERIFIED FAIL | `setMute` sent → 503, 0 MIDI, error toast. Control: fader drag sent 0. No safety impact. `S7_mute_while_no_mixer.png` |
| S8 | LOCK survives a reload | VERIFIED FAIL | VERIFIED FAIL | before reload `aria-pressed=true`, after `false`. `S8_lock_after_reload.png` |
| S9 | Browser Back after changing page | VERIFIED FAIL | VERIFIED FAIL | URL after Back: `about:blank` (left the console) |

### 2. Desktop / iPad parity
Every S-result, payload check and regression check gave the same status on both viewports. No horizontal overflow on any page at either size (scrollWidth = clientWidth for MIX, FX, MY MON, SHOW, OUTPUT, SETUP, SENDS, CHANNEL). At 768 px height the Mix page's bottom row (strip MUTE, mute groups, PRESET, FX 2 bus) sits 7 px below the fold: the stage scrolls (`overflow-y: auto`, scrollHeight 664 vs clientHeight 622) and the row becomes fully visible after scrolling (VERIFIED PASS for reachability; see UX note U-1 in the defect register).

### 3. Actual MIDI payload audit (fake driver)
22 controls driven by real pointer or keyboard input on each viewport. For each, the hub's received payload and the MIDI bytes handed to the (fake) driver were captured and compared with the allowlist (`FLOW8_FULL_UI_INVENTORY.md` §2). **22/22 VERIFIED PASS on both viewports.**

| Control | Payload (last) | MIDI out | Status |
|---|---|---|---|
| MIX fader CH1 (MAIN) | `setFader {channel 1, value 68}` | CC7 ch1 = 68 | PASS |
| MIX strip MUTE CH2 | `setMute {2, false}` | CC5 ch2 = 0 | PASS |
| MIX master MAIN | `setFader {8, 77}` | CC7 ch8 = 77 | PASS |
| EQ node LOW CH1 | `setEqBand {1, low, 110, raw}` | CC1 ch1 = 110 | PASS |
| EQ FLAT (two taps) | `resetEqFlat {1}` | CC1–4 ch1 = 64 | PASS |
| MON SEND cell CH1→MON1 | `setSend {1, mon1, 12}` | CC14 ch1 = 12 | PASS |
| MIX master MON1 | `setBusFader {mon1, 62}` | CC7 ch9 = 62 | PASS |
| Bank fader CH1 on MON1 | `setSend {1, mon1, 52}` | CC14 ch1 = 52 | PASS |
| LOW CUT CH1 (keyboard) | `setLowCut {1, 73}` | CC9 ch1 = 73 | PASS |
| COMP CH1 (keyboard) | `setCompressor {1, 1}` | CC11 ch1 = 1 | PASS |
| OUTPUT GEQ band 1 MAIN | `setBusGeq {main, 1, 89}` | CC11 ch8 = 89 | PASS |
| OUTPUT LIMITER MAIN | `setBusLimiter {main, 126}` | CC8 ch8 = 126 | PASS |
| OUTPUT GEQ band 9 MON2 | `setBusGeq {mon2, 9, 89}` | CC19 ch10 = 89 | PASS |
| FX1 preset 3 | `setFxPreset {fx1, 3}` | Program Change ch13 = 3 | PASS |
| FX2 PARAM1 | `setFxParam {fx2, 1, 1}` | CC1 ch14 = 1 | PASS |
| FX1 VARIANT B | `setFxParam {fx1, 2, true}` | CC2 ch13 = 127 | PASS |
| MY MON CH1→MON1 | `setSend {1, mon1, 68}` | CC14 ch1 = 68 | PASS |
| MY MON master MON1 | `setBusFader {mon1, 78}` | CC7 ch9 = 78 | PASS |
| MUTE ALL (hold) / again | `muteAll {true}` / `{false}` | CC5 ch1–7 = 127 / 0 | PASS |
| UNDO / REDO | `undo` / `redo` | replays CC5 ch7→1 / ch1→7 | PASS |
| CHANNEL preset (two taps) | `applyPreset {1, speech-mc-handheld}` | CC1–4, CC9, CC11 ch1 | PASS |

Across the whole run: 142 (desktop) / 141 (iPad) MIDI messages, **0 outside the map, 0 on channels 15–16, 0 gain (CC8 ch1–4), 0 +48V (CC12 ch1–2)**. Drags send ≈9 requests (70 ms throttle) inside one gesture = one undo step.

Values are what the fake driver received. Whether the mixer applies them is **NOT VERIFIED** (no hardware). FX Program Change on channels 13/14 is itself unconfirmed on the mixer (`docs/product/FLOW8_UNRESOLVED_CONFLICTS.md`).

### 4. Regression checks

| Check | Desktop | iPad | Actual |
|---|---|---|---|
| Inbound hardware move (CC7 ch1 = 90) shows as LIV with the value | PASS | PASS | `LIV`, `-7.6` |
| Meter renders a frame, falls to zero 2 s after the feed stops (synthetic levels, rendering only) | PASS | PASS | `--clip` 10% → 100% |
| Mixer disconnect → NO MIXER + offline note; reconnect → CONNECTED | PASS | PASS | — |
| Host unreachable (API blocked) → NO HOST PC; recovers | PASS | PASS | — |
| Gain and +48V POSTed directly → 403, no MIDI | PASS | PASS | HTTP 403, 403 |
| All 8 pages render without horizontal overflow | PASS | PASS | — |
| Strip MUTE reachable at 768 px height | PASS (needs scroll) | PASS (needs scroll) | see U-1 |

### 5. Console / network

| Item | Count per viewport | Classification |
|---|---|---|
| Uncaught page errors | 0 | — |
| Console `503 (Service Unavailable)` × 2 | 2 | Expected: S4/S7 deliberately took the mixer offline |
| Console `net::ERR_FAILED` × 1 | 1 | Test environment: the host-unreachable check aborts requests on purpose |
| `requestfailed` on `/api/events` (`ERR_ABORTED`) | ~10 | Test environment: the browser aborts the open SSE stream on every reload/navigation |
| HTTP ≥ 400 | 2 (both the deliberate 503s) | Expected |
| Requests | ≈287 (≈141 POST, 146 GET) | — |

No app error surfaced in the console.

### 6. Test-environment issues (not app defects)
1. First run: `.chrow` channel buttons are `display:none` above 760 px by design (phone-only), so harness clicks on them timed out. Fixed in the harness by selecting through the strip head.
2. First run: the rig did not register `Flow8Service._on_midi_in_event` (normally done by `connect()`), so the inbound check read UNK. Fixed in the harness; not an app defect.
3. First run: iPad S6 hit a fader re-created mid-measure (`bounding_box` None). Harness now waits for visibility and retries.

### 7. Not verified in Phase 2
v2 console (`/`) behaviour; touch (pointer events were mouse); real audio meters; anything on real hardware; v3 `sends`/`channel` page interactions beyond render, presets and EQ; long sessions.
