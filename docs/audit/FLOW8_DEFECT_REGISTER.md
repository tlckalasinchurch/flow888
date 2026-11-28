# FLOW 8 Defect Register (v3 web console)

- Opened: 2026-11-27, Phase 2 (`FLOW8_FUNCTIONAL_AUDIT.md`). Base `6a9b8c6` + working tree of 2026-11-27.
- Earlier registers: `REAL_WORLD_DEFECT_REGISTER.md` covers the removed Tkinter UI and is not continued here.
- Severity: P0 safety/hardware risk · P1 core function broken · P2 major UI/workflow defect · P3 minor UI/UX · P4 enhancement.
- Status: all **OPEN — reported, not fixed** (Phase 2 forbids source changes). Evidence paths are under `docs/audit/phase2_2026-11-27/`.
- P0: none found. P1: none found. Every defect reproduced on desktop 1366×768 and iPad 1024×768.

| ID | Sev | Page / component | Summary |
|---|---|---|---|
| V3-D01 | P2 | SHOW · cue name | Text being typed is wiped by the next re-render — **FIXED 2026-11-27 (TASK 02), uncommitted** |
| V3-D02 | P2 | MIX · mute groups | Group ON/OFF is client-only and optimistic: wrong after reload, on other devices, and after rejected mutes — **FIXED 2026-11-27 (TASK 01), uncommitted** |
| V3-D03 | P3 | MIX · group editor | Name field loses focus on every re-render — **FIXED 2026-11-27 (TASK 02), uncommitted** |
| V3-D04 | P3 | OUTPUT · GEQ | Bands are announced as sliders but ignore the keyboard — **FIXED 2026-11-27 (TASK 04), uncommitted** |
| V3-D05 | P3 | SHOW · save cue | SAVE CURRENT MIX works while the device is LOCKED — **FIXED 2026-11-27 (TASK 03), uncommitted** |
| V3-D06 | P3 | MIX · strip MUTE | Sends while NO MIXER; error toast instead of the usual guard — **FIXED 2026-11-27 (TASK 03), uncommitted** |
| V3-D07 | P3 | Header · LOCK | Lock is lost on reload |
| V3-D08 | P4 | Navigation | Browser Back leaves the console |
| U-1 | P3 (UX) | MIX at 768 px height | Bottom row (strip MUTE, groups, PRESET, FX 2) 7 px below the fold; needs a scroll — **FIXED 2026-11-28 (UI refinement F3), uncommitted** |
| V3-D09 | P2 | MIX · fader, EQ node, send cell | Keyboard step drops focus to `<body>`; the second arrow press does nothing — **FIXED 2026-11-28 (UI refinement F18), uncommitted** |
| V3-D10 | P3 | Hub session · EQ provenance | One EQ provenance per channel, read from LOW: other bands restart at 0 dB while LOW is unknown — **OPEN, backend (out of UI scope)** |

---

### V3-D01 — Cue name wiped while typing (P2)
- **Reproduce:** SHOW → type "Worship set" in *Name this cue* → wait 5 s, or let another device send any command → field is empty.
- **Expected:** typed text stays until SAVE or the user clears it.
- **Actual:** `''` after another client's event and after 5.6 s idle (both viewports). `desktop/S2_cue_name_after_reload.png`.
- **Root cause:** `render()` rebuilds the page with `innerHTML` (`flow8/web_ui/v3/v3.js:849-850`), triggered by the 5 s `loadSession` poll (`v3.js:889`) and by every non-meter SSE event (`v3.js:886`). `#cue-name` is created empty (`v3.js:718`) and its value is not kept in `ui`. Focus is restored by id (`v3.js:852`) but the value is not.
- **Impact:** during a show, naming a cue fails unpredictably, more often with several devices connected.
- **Proposed fix:** keep the draft in `ui.cueDraft` (`oninput`) and render it as the input's value; or skip re-render while a text field has focus and re-render on blur.
- **Regression test:** Playwright: type, broadcast a `state` event, wait 5.5 s, assert value; plus a static check that `#cue-name` renders `ui.cueDraft`.
- **Fix (2026-11-27, TASK 02):** the typed name lives in `ui.cueDraft` (`oninput`) and is rendered as the field's value; SAVE reads it, sends the same `librarySave {name}` payload, and clears it only on success (a refused save now keeps the text; before, any reload wiped it). Changing page clears the draft, as before. `render()` now restores the caret/selection of the focused field, not only focus. Tests: `tests/test_v3_text_inputs.py`.

### V3-D02 — Mute group state disagrees with the mixer (P2)
- **Reproduce:** (a) group A = ch1+2, tap A → muted, A lit; reload → A unlit, ch1/ch2 still muted. (b) open on a second device → A unlit. (c) take the mixer offline after the page shows CONNECTED, tap group B (ch3) → hub 503, B lit; reconnect → B still lit, ch3 unmuted.
- **Expected:** a group's lamp shows whether its channels are muted; a rejected command never turns it on.
- **Actual:** as above. `desktop/S4_group_B_after_rejection.png`, `desktop/S4_group_B_after_reconnect.png`.
- **Root cause:** `toggleGroup` flips `g.on` before sending and never reads the results (`v3.js:431-443`); `on` is stripped on save and reset on load (`v3.js:71-73, 422`); state is per browser (`localStorage`), not on the hub.
- **Impact:** an engineer can believe a group is muted when it is not (or the reverse), and the next tap sends the opposite of what they intend. Mixer channel state itself is correct and visible on the strips.
- **Proposed fix:** derive the lamp from session state (ON when every member's mute is known and true); decide the toggle target from that; leave the lamp unchanged when any `setMute` fails. Sharing group definitions across devices is a separate decision (would need a hub-side store).
- **Regression test:** Playwright: (a) reload keeps A lit while members are muted; (c) a 503 on tap leaves B unlit. Unit: a pure `groupOn(groups, channels)` function.
- **Fix (2026-11-27, TASK 01):** `groupState(g)` in `v3.js` derives the lamp from the session's `mute` + `muteProvenance` of each member: ON (all known and muted), OFF (all known, one unmuted), UNKNOWN (`aria-pressed="mixed"`, dashed border) when any member is not OBSERVED/COMMANDED. The browser keeps only names and members. `toggleGroup` picks its target from that state and keeps the old "held by another ON group" rule; the lamp changes only after the reloaded session confirms the mutes. Hub, safety layer, allowlist and payloads unchanged. Tests: `tests/test_v3_mute_groups.py` (9; browser tests skip without Playwright).

### V3-D03 — Group name field loses focus (P3)
- **Reproduce:** hold a group 0.6 s → editor; click the name field; any re-render → focus on `<body>`.
- **Expected:** focus stays. **Actual:** focus `grp-name` → body; text kept. `desktop/S3_group_name_focus.png`.
- **Root cause:** the input has no `id` (`v3.js:397`); `render()` restores focus by id only (`v3.js:848, 852`).
- **Proposed fix:** give it `id="grp-name"`. **Regression test:** Playwright focus check across a broadcast.
- **Fix (2026-11-27, TASK 02):** `id="grp-name"`; caret restored by `render()`; the field keeps exactly what is typed while editing (the old per-keystroke trim/uppercase dropped a trailing space and moved the caret on re-render) and the name is tidied (trim, uppercase, `GROUP` if empty) on DONE. Tests: `tests/test_v3_text_inputs.py`.

### V3-D04 — GEQ ignores the keyboard (P3)
- **Reproduce:** OUTPUT → Tab to a GEQ band (announced as slider) → ArrowUp ×3 → nothing sent.
- **Expected:** ±0.5 dB per arrow, like the EQ nodes. **Actual:** 0 `setBusGeq`; EQ node control sends 1 `setEqBand`.
- **Root cause:** `.geq-well` has `role="slider"` and `tabindex="0"` (`v3.js:627`) but no `onkeydown` (`v3.js:642-660`).
- **Impact:** keyboard and switch-access users cannot set the GEQ; the role misleads screen readers.
- **Proposed fix:** add an `onkeydown` mirroring `wireEqNodes` (`v3.js:597-603`) with `setBusGeq`. **Regression test:** Playwright ArrowUp → one `setBusGeq` with the expected raw value.
- **Fix (2026-11-27, TASK 04):** each band gets `id="geq-N"` (so focus survives the reload after each command), `aria-valuemin=-15`, `aria-valuemax=15`, `aria-valuenow` (omitted while the value is unknown; otherwise the visible label's 0.1 dB value) and `aria-valuetext`. Mouse and keyboard share one `set(db)` (clamp ±15, 0.5 dB grid, `dbToEqRaw`). Keys: ArrowUp/Right +0.5 dB, ArrowDown/Left −0.5 dB, Home −15 dB, End +15 dB; handled keys never scroll; nothing is sent while LOCKED or with no mixer. Same `setBusGeq {bus, band, value}` payload, no new send path. Tests: `tests/test_v3_geq_keyboard.py`.

### V3-D05 — Cue can be saved while LOCKED (P3)
- **Reproduce:** hold LOCK → SHOW → name → SAVE CURRENT MIX → saved (HTTP 200).
- **Expected:** LOCK ("Controls locked on this device") blocks every control. **Actual:** `librarySave` sent, 200; faders correctly blocked. `desktop/S6_save_while_locked.png`.
- **Root cause:** `#cue-add` handler has no `ui.locked` check (`v3.js:746-752`).
- **Impact:** a stray touch adds a cue to the show list. No mixer change (offline action).
- **Proposed fix:** `if (ui.locked) return toast(...)`. **Regression test:** Playwright locked save → no `librarySave`.
- **Fix (2026-11-27, TASK 03):** the handler refuses while `ui.locked` (toast "Locked. Hold LOCK to unlock first.", typed name kept); the button renders `disabled` while locked (`.mini:disabled` style) and LOCK toggling now re-renders so it follows. Payload and save path unchanged. Tests: `tests/test_v3_guards.py`.

### V3-D06 — Strip MUTE sends while NO MIXER (P3)
- **Reproduce:** mixer offline (header NO MIXER) → tap a strip MUTE → request sent, hub 503, error toast.
- **Expected:** same guard as every other control: nothing sent while not ready. **Actual:** `setMute` → 503, 0 MIDI. `desktop/S7_mute_while_no_mixer.png`.
- **Root cause:** `toggleMute` checks `ui.locked` but not `mixerReady()` (`v3.js:424-429`).
- **Impact:** confusing error toast; safety unaffected (hub refuses, no MIDI).
- **Proposed fix:** add `|| !mixerReady()` with the MUTE ALL toast text. **Regression test:** Playwright offline mute → no request.
- **Fix (2026-11-27, TASK 03):** `toggleMute` refuses when `!mixerReady()` with the MUTE ALL text ("The FLOW 8 is not connected. Nothing was sent."); strip MUTE carries `aria-disabled` from the same state (visual state unchanged: existing `body.offline` style). `mixerReady()` reads the latest session, which the hub pushes on disconnect (`link` event). Between an unannounced unplug and the next update the page cannot know; the hub still answers 503 and sends no MIDI (tested). Tests: `tests/test_v3_guards.py`.

### V3-D07 — LOCK lost on reload (P3)
- **Reproduce:** hold LOCK → reload → unlocked.
- **Expected:** to be decided by the owner. A locked stage device that reloads (sleep, Wi-Fi drop) should probably stay locked. **Actual:** `aria-pressed` true → false.
- **Root cause:** `ui.locked` starts `false` and is never stored (`v3.js:70, 814-820`).
- **Proposed fix (needs owner decision):** persist in `localStorage` per device. **Regression test:** Playwright reload keeps the lock.

### V3-D08 — Browser Back leaves the console (P4)
- **Reproduce:** open `/v3/` from another page, tap FX, press Back → previous site.
- **Root cause:** page changes create no history entry (`go`, `v3.js:199`).
- **Proposed fix:** `history.pushState({page})` in `go` and a `popstate` handler (or a URL hash). **Regression test:** Playwright Back returns to MIX.

### U-1 — Bottom row below the fold at 768 px height (P3, UX)
- At 1366×768 and 1024×768 the Mix page stage is 664 px tall in a 622 px area; strip MUTE bottoms are at 775 px in a 768 px viewport, and the FX 2 bus button and PRESET are cut off. Scrolling reveals them (verified). For live use, MUTE should be fully visible without scrolling. Evidence: `desktop/PAGE_mix.png`, `ipad/PAGE_mix.png`, `*/REG_mute_reach.png`. Belongs to the Phase 5 UX audit; listed here so it is not lost.

### V3-D09 — Keyboard step drops focus (P2)
- **Reproduce:** MIX → focus a strip fader (or an EQ node, or a MON SEND cell) → ArrowUp ×3 → one command sent, `document.activeElement` is `<body>`.
- **Root cause:** each step reloads the session and `render()` rebuilds the page; focus is restored by id only (same mechanism as V3-D03), and these controls had no id.
- **Fix (2026-11-28):** stable ids `fdr-<strip>`, `eqn-<band>`, `cell-<ch>-<mix>`. Payloads unchanged. Test: `tests/test_v3_keyboard_focus.py` (3, failed before the fix: 1 of 3 presses sent).

### V3-D10 — EQ provenance is per channel, read from LOW (P3, backend)
- **Observed:** `lan_hub.py` session sets `eqProvenance` from `ch{n}.eq_low` only. With LOW unknown, a LOW MID/HI MID/HIGH value the app sent is still shown as unknown, and each keyboard or drag edit of those bands starts again from 0 dB.
- **Not fixed:** the UI task forbids backend changes. Proposed fix: per-band provenance in the session (`eqProvenance` per band), then `procView`/`pageChannel` read it per node. Owner decision.

## Not defects
- **S1** (range slider during re-render): disproved, VERIFIED PASS on both viewports.
- Console 503s, `ERR_FAILED`, SSE `ERR_ABORTED`: caused by deliberate test steps or reloads (`FLOW8_FUNCTIONAL_AUDIT.md` §5).
