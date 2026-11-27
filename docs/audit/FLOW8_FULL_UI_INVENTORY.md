# FLOW 8 Full UI Inventory (Phase 1)

- Date: 2026-11-27
- Base: `main` at `6a9b8c6`, plus the uncommitted working tree of 2026-11-27 (section 0). Every line reference is to that working tree.
- Method: source read of `flow8/web_ui/v3/{index.html,v3.js}`, `flow8/web_ui/{index.html,app.js}`, `flow8/lan_hub.py`, `flow8/command_boundary.py`. No browser run, no hub run, no MIDI.
- Status of everything below: **NOT VERIFIED** (inventory from code). Behaviour is verified, or not, in Phase 2 (`FLOW8_FUNCTIONAL_AUDIT.md`).
- Supersedes nothing. `docs/audit/REAL_WORLD_*` (commit `5964d6b`, branch `stage2-mixer-workstation`) inventory the removed Tkinter UI; `E2E_UI_AUDIT_2026-11-19.md` covers the v2 web console at `e320bd2`. Neither covers v3.

## 0. Repository baseline (Phase 0, read-only)

| Item | Value | Evidence |
|---|---|---|
| Branch / HEAD | `main` / `6a9b8c6` (merge of PR #16) | `git branch --show-current`, `git log -1` |
| Modified (uncommitted) | `DESIGN.md`, `flow8/{audio_meter,command_boundary,lan_hub,midi_in,service,web_console}.py`, `flow8/web_ui/{app.js,index.html,styles.css}`, `tests/test_web_cache.py` | `git status --short` |
| Untracked | `.fast/`, `.impeccable/…`, `.taste-skill/`, `IMPECKNABLE_AUDIT_*.md`, `impeccable_audit_summary.md`, `design-plans/flow888-v3/`, `docs/architecture/RUST_PORTING_DECISION.md`, `flow8/web_ui/v3/`, `run_flow8.bat`, `tests/test_{instrumentation,live_performance_fixes,ui_provenance_display,v3_console}.py` | same |
| Pending work from earlier rounds | v3 console (untracked), T1/M2 fixes and §7 instrumentation (uncommitted), soak collector (scratchpad, outside the repo); hardware soak not authorised | this session |
| Test suite | 45 entries in `tests/`; last full no-hardware run 487 ran, 0 failed, 5 skipped (hardware), 0 port opens | `python -m tools.run_tests_no_hw`, 2026-11-27 |
| Backend entry | `main.py` → `flow8/web_console.py:main` → `Flow8LanHub` + `Flow8Service` + `Flow8AudioMeter` | code |
| Frontend entry | `/v3/` → `v3/v3.js`; `/` → `app.js` | `lan_hub.py` GET routes |
| Playwright | 1.65.0 installed (used by `E2E_UI_AUDIT_2026-11-19.md`) | `importlib.metadata` |

## 1. Surfaces

| Surface | URL | Files | Role |
|---|---|---|---|
| v3 console (primary) | `/v3/` | `v3/index.html` (65 lines), `v3/v3.js` (897), `v3/v3.css` (396) | Owner-approved primary UI for shows |
| v2 console | `/` | `index.html` (223), `app.js` (3228), `styles.css` | Previous console; still served; the only editor for Show modes, snapshot library management, routing/transport, FlowAi change plans |

Both are plain JS, no framework, no build. One page each; v3 has no URL routing (the page is kept in `localStorage` key `flow888.v3.page`), so browser Back/Forward leaves the app instead of changing page.

## 2. Shared plumbing

| Item | Where | Behaviour from code |
|---|---|---|
| Session read | `GET /api/session` (`lan_hub.py` `session_snapshot`) | Full state: channels (fader, mute, pan, eq, lowCut, compressor, sends + provenance each), buses, busDsp, fxEngines, library, showModes, locked, transport, midiConnected |
| Status read | `GET /api/status` | Link state + instrumentation (meterStats, sse, dispatch, telemetry) |
| Presets | `GET /api/presets`, `GET /api/presets/thai` | Channel presets (EQ, low cut, comp only) |
| Library export | `GET /api/library/export` | v2 only |
| Commands | `POST /api/action` `{action, ..., clientId}` | `Flow8LanHub.dispatch_action` (`lan_hub.py:703`) → `Flow8Service.set_*` → `Flow8CommandBoundary.execute_command` (allowlist 133 params + `safety.authorize_command`) → `TransportRouter.dispatch` → `Flow8MidiOut.send_cc` (`validate_outbound`) |
| Server-side blocks | `dispatch_action` | `setGain`/`gain` → 403 (SR-05); `set48V`/`setPhantom`/`phantom` → 403; change plans with gain/phantom → 403; any non-offline action while the control transport is closed → 503 |
| Offline actions (no MIDI) | `_OFFLINE_ACTIONS` (`lan_hub.py:86`) | setScribble, librarySave/Rename/Delete/Import, setActiveBus, setActiveView, previewChangePlan, begin/endGesture, setTransportMode, bleDumpTrigger, saveShowMode |
| Live events | `GET /api/events?clientId=` (SSE) | `connected`, `meters` (≤30/s, droppable), `state`, `link`, `rx` (hardware moves), `tx` |
| Locks list | `session.locked` = `LAN_LOCKED_FEATURES` (`lan_hub.py:71`) | gain, phantom, solo, fxMute, tap, eqParametric, stereoLink, routing, outputPad, footswitch, hwSnapshots |

### MIDI map in force (`Flow8CommandBoundary.ACTIVE_ALLOWLIST`, 133 entries, read this session)

| Parameter | MIDI channels | CC | UI sender |
|---|---|---|---|
| fader | 1–7 strips, 8 main, 9–12 buses | 7 | setFader / setBusFader |
| mute | 1–7 | 5 | setMute / muteAll |
| pan | 1–7; balance on 8 | 10 | setPan (v2 only) |
| eq_low / low_mid / hi_mid / hi | 1–7 | 1 / 2 / 3 / 4 | setEqBand |
| low_cut | 1–4 | 9 | setLowCut |
| compressor | 1–4 | 11 | setCompressor |
| send_mon1 / mon2 / fx1 / fx2 | 1–7 | 14 / 15 / 16 / 17 | setSend |
| limiter | 8–10 (main, mon1, mon2) | 8 | setBusLimiter |
| geq1–9 | 8–10 | 11–19 | setBusGeq |
| FX param1 / param2 | 13–14 | 1 / 2 | setFxParam |
| FX preset | 13–14 | Program Change 1–16 | setFxPreset |
| gain | 1–4 | 8 | none over LAN (403) |
| phantom | 1–2 | 12 | none over LAN (403) |

## 3. v3 inventory (`/v3/`)

### 3.1 Header (always visible) — `v3/index.html:37-56`, wiring `v3.js:803-837`

| Control | Type | State | API | MIDI | Safety / guard | Feedback | Recovery |
|---|---|---|---|---|---|---|---|
| `#link` status | button | `hubUp`, `mixerReady()` | none | none | — | text CONNECTED / NO MIXER / NO HOST PC; tap shows toast | `renderLink` on SSE open/error and each session load |
| `#midi` transport chip | span | `session.transportMode` | — | — | — | USB MIDI / BLUETOOTH | — |
| UNDO `#btn-undo` | button | — | `undo` | replays recorded values | `ui.locked` | toast "Undone." | `scheduleReload` |
| REDO `#btn-redo` | button | — | `redo` | replays | `ui.locked` | toast | reload |
| LOCK `#btn-lock` | hold 800 ms | `ui.locked` (this device only) | none | none | hold-to-toggle | label LOCKED, body class | not persisted: a page reload unlocks |
| MUTE ALL `#btn-muteall` | hold 600 ms | computed `allMuted()` | `muteAll {value}` | mute CC5 ch1–7, one undo step | locked → toast; not ready → toast, nothing sent | toast | reload |
| Settings `#btn-set` → `#setmenu` | popover | `aria-expanded` | none | — | — | — | closes on outside pointerdown |
| FINE `#btn-fine` | toggle | `ui.fine` (not persisted) | none | — | — | toast | — |
| NIGHT `#btn-night` | toggle | `ui.night` (localStorage) | none | — | — | body class | — |
| Nav `#rail` | 6 buttons | `ui.page` (localStorage) | none | — | — | `aria-current` | — |

Nav pages (`PAGES`, `v3.js:193`): MIX, FX, MY MON (`stage`), SHOW, OUTPUT, SETUP (`safety`). Secondary pages without a tab: `sends`, `channel` (shown as MIX active, `NAV_OF`).

### 3.2 MIX page — `pageMix` `v3.js:340-391`

| Control | Type | API | MIDI | Guard | Notes |
|---|---|---|---|---|---|
| Channel select `#ch-next`, `.chrow [data-ch]`, strip head | buttons | none | — | — | `ui.sel` (not persisted) |
| Processor tabs SOURCE / EQ / COMP / FX SEND / MON SEND `[data-proc]` | buttons | none | — | — | `ui.proc` (localStorage) |
| CHANNEL `#to-channel`, PRESET `#to-presets` | buttons | none | — | — | both open the Channel page |
| Mute groups A–D `.grp` | tap = toggle, hold 600 ms = edit | `beginGesture`, `setMute` × members, `endGesture` | CC5 | `ui.locked`, `mixerReady()` | membership in localStorage; **on/off state client-only, not persisted, not shared** |
| Group editor `.grp-name`, `.grp-ch`, `.grp-done` | inline | none | — | — | saved to localStorage on DONE |
| EQ nodes `.eq-node` (EQ tab) | drag / ArrowUp/Down 0.5 dB | `setEqBand {raw}` via gesture | CC1–4 | locked, ready | snap 0.5 dB, ±15 dB |
| FLAT `#eq-flat` | two-tap | `resetEqFlat` | CC1–4 → 64 | locked, ready | arm toast |
| LOW CUT `#lc` (SOURCE, ch 1–4) | range | `setLowCut` on change | CC9 | locked, ready at change | no gesture/drag guard |
| COMP `#cp` (COMP, ch 1–4) | range | `setCompressor` | CC11 | same | same |
| GAIN, +48V rows (SOURCE) | read-only lock line | none | — | text from `session.locked` | no sender exists |
| Send cells `.cell` (FX SEND / MON SEND) | drag sideways / arrows | `setSend` via gesture | CC14–17 | locked, ready | — |
| ALL SENDS `#all-sends` | button | none | — | — | opens Sends page |
| Fader bank strips `.strip .well` | relative drag / arrows / PgUp/PgDn | MAIN: `setFader ch`; other mix: `setSend` | CC7 / CC14–17 | locked, ready | FINE = quarter travel |
| Strip MUTE `.s-mute` (MAIN mix only) | button | `setMute` | CC5 | `ui.locked` only (no `mixerReady()`; hub returns 503) | "MUTE ?" when unknown |
| Master strip `.mstrip` | fader | MAIN: `setFader 8`; buses: `setBusFader` | CC7 ch8–12 | locked, ready | — |
| Mix buttons `.bus[data-mix]` | buttons | `setActiveBus` (quiet, offline) | none | — | changes what the faders control |
| Meters `.meter[data-sid]` | display | SSE `meters` | — | — | peak only; `ch1..ch6`, `main`; falls to zero 2 s after the feed stops |

### 3.3 SENDS page (secondary) — `pageSends` `v3.js:446-455`
Matrix 7 channels × MON1/MON2/FX1/FX2, `.cell` as in 3.2 (`setSend`, CC14–17).

### 3.4 CHANNEL page (secondary) — `pageChannel` `v3.js:516-559`

| Control | API | MIDI | Guard |
|---|---|---|---|
| Channel buttons `[data-ch]` | none | — | — |
| EQ graph nodes, FLAT | as 3.2 | CC1–4 | locked, ready |
| LOW CUT `#lc`, COMP `#cp` (ch 1–4) | `setLowCut`, `setCompressor` | CC9, CC11 | locked, ready at change |
| GAIN row | none (lock text) | — | — |
| Preset list `.preset` (from `/api/presets`) | two-tap → `applyPreset {channel, presetId}` | CC1–4, 9, 11 (one undo step) | locked, ready |

### 3.5 OUTPUT page — `pageOutput` `v3.js:614-671`

| Control | API | MIDI | Guard | Notes |
|---|---|---|---|---|
| Mix buttons MAIN / MON1 / MON2 | none | — | — | `ui.outMix` |
| GEQ 9 bands `.geq-well` | `setBusGeq {bus, band 1–9, raw}` via gesture | CC11–19 on ch 8–10 | locked, ready | **role=slider + tabindex but no keyboard handler** |
| Limiter `#lim` | `setBusLimiter` on change | CC8 ch 8–10 | locked, ready at change | — |
| Delay calculator `#dm`, `#dt` | none (local maths, localStorage) | none | — | states it sends nothing |

### 3.6 FX page — `pageFx` `v3.js:674-701`

| Control | API | MIDI | Guard |
|---|---|---|---|
| 16 presets × FX1/FX2 `[data-fx]` | `setFxPreset {engine, value}` | Program Change 1–16 on ch 13/14 | locked, ready |
| PARAM 1 `#fx1-p1`, `#fx2-p1` | `setFxParam param 1` on change | CC1 ch 13/14 | locked, ready at change |
| VARIANT A/B `[data-v]` | `setFxParam param 2 bool` | CC2 ch 13/14 | locked, ready |
| TAP, FX MUTE chips | none (lock text) | — | ch 16 forbidden |

The page itself states that FX MIDI channel numbering (13/14 vs 14/15) is unconfirmed.

### 3.7 SHOW page — `pageShow` `v3.js:705-763`

| Control | API | MIDI | Guard | Notes |
|---|---|---|---|---|
| Cue cards `.cuecard` (host snapshot library) | two-tap → `libraryLoad {id}` | many (levels, mutes, EQ, sends; never gain/+48V) | locked, ready | sets `ui.cueNow` (localStorage) on success |
| GO `#go` | two-tap → `libraryLoad` next | same | locked, ready | disabled at end of list |
| Cue name `#cue-name` + SAVE CURRENT MIX `#cue-add` | `librarySave {name}` | none (offline) | name required; **no `ui.locked` check** | writes `~/.flow8/snapshot_library.json` |
| Show modes `.mode` | hold 450 ms → `runShowMode {id}` | many | locked, ready, `m.ready` | editing only in v2 |

### 3.8 MY MON page — `pageStage` `v3.js:766-786`

| Control | API | MIDI | Guard |
|---|---|---|---|
| MON1 / MON2 buttons | none | — | — |
| "I am" buttons `[data-me]` (ch 1–6) | none | — | localStorage |
| Strips: every channel's send to this monitor | `setSend` | CC14/15 | locked, ready |
| "My level" master | `setBusFader mon1/mon2` | CC7 ch 9/10 | locked, ready |

No mutes, EQ or main mix on this page (by design).

### 3.9 SETUP page — `pageSafety` `v3.js:789-800`
Read-only lock cards from `session.locked` plus the FX-channel test card and the mixer-reset card. No controls.

### 3.10 Global behaviour

| Item | Code | Notes |
|---|---|---|
| Re-render | `render()` `v3.js:841` replaces the whole page's `innerHTML` | Triggered by every `loadSession` (every 5 s when not dragging, and 120 ms after any non-meter SSE event or command) |
| Drag guard | `ui.dragging` counts open gestures (faders, cells, EQ nodes, GEQ) | **Range inputs (`#lc`, `#cp`, `#lim`, `#fxN-p1`) and text inputs (`#cue-name`, `.grp-name`, `#dm`, `#dt`) are not guarded** |
| Focus restore | by `id` only | Inputs without an id (`.grp-name`) lose focus on re-render |
| Offline note | `offlineNote()` | shown on every page except SETUP when `mixerReady()` is false |
| Provenance labels | `PROV` | LIV (observed), SNT (commanded), UNK, ERR, N/A |
| SSE reconnect | `sseConnectedOnce` | reloads the session on reconnect (added 2026-11-27, T1) |

## 4. v2 inventory (`/`), control-group level

Navigation: section tabs `#cue-groups` (Mix, Sound, Presets, Setup), view tabs `#cue-tabs` (Faders, Stage, Input, EQ, Comp, Sends, FX, Channel), side nav `#side-nav` (8 items), layer tabs `#layer-tabs`. Drawers: Inspector `#inspector`, FlowAi `#flowai-drawer`, change-plan `#plan-panel`. Modals: `#prompt-modal`, `#scribble-modal`, `#confirm-modal`. Hidden file input `#library-file`.

| Group | Functions (`app.js`) | Actions sent |
|---|---|---|
| Header: status pill, lamps USB / MIDI IN / HUB / RX / meters, scene display, save, settings, clock, LOCK, MUTE ALL | `renderStatusBar` 2681, `applyConnectionState` 295, `attachHold` 634, `toggleMuteAll` 2883 | muteAll |
| Control bar: select badge, Undo/Redo, Copy/Paste DSP, FlowAi, Show modes + undo | `updateSelectBadge` 1790, `renderShowModes` 2952, `runShowMode` 3002 | undo, redo, pasteChannelDsp, runShowMode |
| Fader bank (console) | `renderConsole` 804, `attachVerticalFader` 689 | setFader, setSend, setBusFader, setPan, setMute |
| Stage view | `renderStage` 1295 | setFader / setSend, setMute |
| Channel inspector | `renderChannelInspector` 1030, `phantomKey` 1138 | setMute, setLowCut, setCompressor, setPan, setEqBand, setSend, setPhantom (only when `lanPolicy.phantom`; otherwise locked, toast) |
| Bus inspector | `renderBusInspector` 1161 | setPan ch8, setBusLimiter, setBusGeq, setFxParam, setFxPreset, setBusFader |
| Sound tabs EQ / Input / Comp / Sends / FX / Channel / Presets | `renderCue*Tab` 1844–2194 | setEqBand, setLowCut, setCompressor, setSend, setFxPreset, setFxParam, setBusFader, applyPreset (via plan) |
| Snapshots page | `renderSnapshotsPage` 1443 | captureScene, recallScene (with scope) |
| Library page | `renderLibraryPage` 1503 | librarySave (new / overwrite), libraryLoad (scope), libraryRename, libraryDelete, libraryImport; export via GET |
| Routing / transport page | `renderRoutingPage` 1613 | setTransportMode, bleDumpTrigger |
| Prefs, Info, Inputs pages | `renderPrefsPage` 1590, `renderInfoPage` 1697, `renderInputsPage` 1387 | none / read-only |
| Show modes editor | `showModeEditor` 3027, `renderShowModesPage` 3115 | saveShowMode |
| FlowAi + change plan | `renderFlowAiDrawer` 2388, `previewPlan` 2256, `commitPlan` 2333 | previewChangePlan, commitChangePlan |
| Scribble strip | `openScribbleModal` 2743 | setScribble |
| View sync | `setTopTab` 1819, `setLayer` 2828 | setActiveView, setActiveBus |

The v2 inventory is at group level. A per-element pass for v2 is not done; it is needed only if v2 stays in show use.

## 5. Items to verify in Phase 2 (suspected, not yet defects)

These come from the code read only. Each becomes VERIFIED FAIL or VERIFIED PASS after a browser run against the hub with the existing fake-MIDI fixture.

| # | Suspicion | Code |
|---|---|---|
| S1 | A periodic re-render (every 5 s, or after another client's command) destroys a range input mid-drag: the `change` event never fires and the command is never sent | `render()` + unguarded range inputs, `v3.js:606-611, 889` |
| S2 | Text typed in the cue-name field is wiped by the next re-render | `#cue-name` value not kept in state, `v3.js:718, 889` |
| S3 | Group-name input loses focus on re-render (no id) | `v3.js:397, 852` |
| S4 | Mute group on/off state is client-only: lost on reload, not shared between devices, and flipped even when the hub rejects the mutes | `toggleGroup` `v3.js:431-443` |
| S5 | GEQ bands are announced as sliders but cannot be moved from the keyboard | `v3.js:627, 642-660` |
| S6 | SAVE CURRENT MIX works while the device is LOCKED | `v3.js:746-752` |
| S7 | Strip MUTE does not check `mixerReady()` (other controls do); relies on the hub's 503 | `toggleMute` `v3.js:424-429` |
| S8 | LOCK is not persisted: a reload or a second device is unlocked | `v3.js:814-820` |
| S9 | Browser Back/Forward leaves the console instead of changing page | no history entries |
