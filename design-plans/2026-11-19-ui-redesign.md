# UI redesign: Live Mixer Control Surface (Phases 1-4)

Status: PLAN ONLY. No product source changed. Phase 5 needs owner approval.
Surface: `flow8/web_ui/` (`index.html`, `app.js`, `styles.css`), served by `flow8/lan_hub.py`.
Base commit: main @ 8f47e01 (after PR #6).

## 0. Evidence behind the redesign (rendered 2026-11-19, console on port 8844)
- Mixer tab shows the 7 channels + MAIN twice: overview strips on top, fader bank below (iPad 1024x768).
- Fader bank is fixed in every view. In Setup > Configure Inputs the +48V row is clipped by it.
- Phone 390x844: header chrome = 240px (28% of height), 5 rows; brand wraps; bank shows 5 of 8 strips.
- MC/BAND (run macros) sit inside the navigation row. Undo has text, Redo is icon only.
- No JS errors and no horizontal page scroll at 1440, 1024 and 390 widths.
Not measured: real touch use on a venue iPad, latency, hardware behaviour.

## Decisions needed from owner before Phase 5
- D1 Product name. The brief says "CueAir Pro". `PRODUCT.md:37-38` says CueAir must not appear in user-facing UI (SR-10) and records the title as an unresolved conflict. This plan uses "FLOW 8" + "LIVE CONSOLE" until decided. One string each in `index.html` `<title>` and `.brand-mark`.
- D2 Sound view keeps a compact fader bank (level + mute only) so the engineer hears changes while tuning. Alternative: no bank, channel chips only. Plan assumes the compact bank.
- D3 Setup merges "MIXER SNAPSHOTS" and "SNAPSHOT LIBRARY" into one "Snapshots" page with two tabs. Actions stay separate (`captureScene`/`recallScene` vs `library*`). Alternative: keep 7 pages.
- D4 Accessibility target is undecided (`PRODUCT.md:57`). Plan keeps 44px touch targets and focus rings only.

## Phase 1. UI architecture

Four control classes, each with one fixed home. Never mixed in one row.

| Class | Controls | Home |
|---|---|---|
| Navigation | Mix, Sound, Presets, Setup | Header, centre |
| Show Control | MC, BAND (+ Show Mode UNDO chip) | Control bar, right side; amber (existing) |
| Edit tools | SELECT, Undo, Redo, Copy, Paste, FlowAi | Control bar, Mix and Sound only |
| Safety | LOCK, MUTE ALL | Header, far right, set apart by a gap; MUTE ALL keeps its 0.6 s hold |

Header (one row, 48px): brand | ONE link pill (replaces the 5 lamps; tap opens Setup > Connection via `openRoutingFromPill`; lamp detail moves into that page and the pill tooltip) | section tabs | scene chip | clock | LOCK | MUTE ALL.
Phone (<=760px): row 1 brand + link pill + LOCK + MUTE ALL; row 2 section tabs. Target chrome <= 120px (now 240px).

Layout per section:

| Section | Main area | Fader bank | Sub-views |
|---|---|---|---|
| Mix | The bank is the screen: taller faders; send mini-bars, EQ thumb, LC/48V badges folded into each strip | one, full | Faders, Stage |
| Sound | Selected-channel tools | compact (level + mute) | Input, EQ, Comp, Sends, FX, Channel |
| Presets | Preset list, scope, review | none; channel chips instead | none |
| Setup | Full screen | none | left list: Inputs, Snapshots (D3), Show Modes, Preferences, Connection, Info |

Removed: the duplicate overview pane, the second tab row for Setup, the separate `#setup-view` nav with its own close button, the hidden legacy inspector markup.

## Phase 2. Wireframes (ASCII, not pixel-exact)

iPad 1024x768, Mix
```
[FLOW 8 LIVE] (ONLINE)  Mix|Sound|Presets|Setup   Scene 22:56  [LOCK][MUTE ALL]
[SEL 01][Undo][Redo][Copy]  [FlowAi]                  [MC][BAND] (undo chip)
+--01--+--02--+--03--+--04--+--05--+--06--+--07--+--MAIN--+
| name                                                    |
| sends M1 M2 FX1 FX2 (mini bars) | EQ thumb | LC | 48V   |
| fader (tall)                                            |
| dB   [MUTE]                                             |
+---------------------------------------------------------+
```
iPad, Sound > EQ
```
header + control bar (same)        sub-tabs: Input|EQ|Comp|Sends|FX|Channel
[ EQ graph + band knobs for the SELECTed channel               ]
[ compact bank: 01..07 MAIN, short fader + MUTE                ]
```
iPad, Setup (no bank, no control bar)
```
[Inputs      ] [ page content, full height, scrolls inside ]
[Snapshots   ]
[Show Modes  ]
[Preferences ]
[Connection  ]
[Info        ]
```
Phone 390x844, Mix
```
[FLOW 8][ONLINE][LOCK][MUTE ALL]
[Mix|Sound|Presets|Setup]
[SEL][Undo][Redo][Copy][FlowAi]   [MC][BAND]
strips scroll sideways, 4 visible, tall fader, MUTE under each
```
Phone Setup: the page list becomes a select at the top; content uses the full width.

## Phase 3. Interaction audit (controls that must keep working)
Every control below exists today; the line numbers are current handlers in `app.js`. The redesign moves them but must not change action name, payload or guard. Source: grep of `action: '...'` in `app.js` this session.

| Control | Current handler | Hub action | Guard to keep |
|---|---|---|---|
| Fader (strip) | `attachVerticalFader` (`:945`) | `setFader`, `setBusFader` | beginGesture/endGesture around drag (`:139`, `:162`) |
| Mute | `:1013`, `:1181`, `:1447` | `setMute` | none |
| Pan / Balance | `:1011`, `:1213`, `:1344` | `setPan` | none |
| Send | `:1019`, `:1290`, `:1437`, `:2346` | `setSend` | none |
| EQ band / Low cut | `:1257`, `:2106`, `:2133` | `setEqBand`, `setLowCut` | none |
| Compressor | `:1206`, `:2323` | `setCompressor` | none |
| +48V | `phantomKey` (`:1298`), `:1315` | `setPhantom` | single-use confirm token (SR-06) |
| Gain | knob `:1193` | none (locked) | stays locked (SR-05) |
| MUTE ALL | `:2947` | `muteAll` | hold 0.6 s (`data-hold="arm"`) |
| LOCK | `:2791` | local | blocks stray touches |
| Undo / Redo | `:2962`, `:2963` | `undo`, `redo` | none |
| MC / BAND | `runShowMode` (`:3066`) | `runShowMode` | hold `SHOW_MODE_HOLD_MS = 450`, NOT SET message |
| Show Mode editor | `:3091`, `:3169` | `saveShowMode` | drafts survive reload (`showModeDrafts`) |
| Show Mode UNDO chip | `:3053`-`:3059` | `undo` | hidden after any other change |
| SELECT badge | `:2907` | local | cycles 1-7 |
| Copy / Paste | `:2913`, `:2926` | `pasteChannelDsp` | paste excludes gain and +48V |
| FlowAi, plan review | `:2908`, `:2504` | `previewChangePlan`, `commitChangePlan` | plan staged, commit explicit |
| Presets apply | `renderCuePresetsTab` (`:2142`) | via change plan | presets never touch levels (SR-12) |
| Snapshots | `:1596`, `:1604` | `captureScene`, `recallScene` | as today |
| Library | `:1648`-`:1712`, `:2752` | `librarySave/Load/Rename/Delete/Import` | as today |
| Transport mode, BLE dump | `:1792`, `:1798` | `setTransportMode`, `bleDumpTrigger` | as today |
| Scribble name | `:2844` | `setScribble` | none |
| Bus selector | `:2899` | `setActiveBus` | hub sync |
| View sync | `setTopTab` (`:1955`) | `setActiveView` | values stay `mixer` / `stage` |

Not allowed to change: any `flow8/*.py` file, the `command_boundary` allowlist, `safety.validate_outbound`, `midi_out.py`. The redesign touches `web_ui/` and tests only. `setActiveView` and `setActiveBus` sync UI state between devices; keep payloads identical. Add no control for a parameter outside the allowlist (SR-07).
Not verified: the server-side validation of `setActiveView` values (lan_hub.py not read this session).

## Phase 4. Implementation plan

Work packages, in order; each leaves the suite green:
- W1 Shell: new header + control bar markup in `index.html`. `renderStatusBar` (`:2757`), `applyConnectionState` (`:229`), `linkSummary` (`:182`) feed the single link pill. Keep `status-pill` and `lamp-*` ids until the Connection page reads the same data.
- W2 Layout modes: `body[data-view]` / a new `data-section` drives bank mode (full / compact / none) in `renderView` (`:2688`) and `renderConsole` (`:951`). Delete the duplicate overview in `renderMixerOverview` (`:1981`) and fold its data into the strips.
- W3 Show Control + Safety: relocate `#show-modes`, `#show-mode-undo`, LOCK, MUTE ALL in markup. `renderShowModes` (`:3016`) logic unchanged.
- W4 Setup full screen: remove the nested `#setup-view` nav; Setup renders in the main area with a left list (`SETUP_PAGES`, `:1464`); merge pages per D3.
- W5 Phone / iPad CSS: breakpoints 760 and 1180; 44px targets on coarse pointers; keep `prefers-reduced-motion`.
- W6 Tests and evidence (below).

Files: `flow8/web_ui/index.html`, `app.js`, `styles.css`, `tests/test_web_console.py`, `DESIGN.md` (layout sections), `PRODUCT.md` if D1 changes. No backend files.

Existing tests that assert on the current UI (`tests/test_web_console.py:214-270`) must still pass or be changed deliberately:
- ids `show-modes`, `show-mode-undo`; `data-page="showmodes"` (rename only together with the test).
- `SHOW_MODE_HOLD_MS = 450`, `attachHold(btn, SHOW_MODE_HOLD_MS`, `action: 'runShowMode'`, `action: 'saveShowMode'`, `function hideShowModeUndo`, `showModeDrafts`, `showModeBusy`.
- `function linkSummary(`, `openRoutingFromPill`, `MIDI OUT SEEN`, `.status-pill { min-height: 44px }`.

New regression tests (string guards, same style as above): bank mode per section; Safety controls sit in the header container, not the nav container; Show Control is not inside `#cue-groups`; Setup markup has no `#setup-view`; Redo has a text label; `setActiveView` payload still `mixer` or `stage`.

Verification before merge (report real output, say "not run" otherwise):
1. `python -m tools.run_tests_no_hw` (baseline today: 421 ran, 416 passed, 0 failed, 5 skipped).
2. `node --check flow8/web_ui/app.js`.
3. Playwright pass at 1440x900, 1024x768, 390x844 over Mix, Sound, Presets, Setup: no JS errors, no horizontal scroll, phone header height <= 120px, bank shown only where planned.
4. Hardware smoke on a real FLOW 8 (NOT RUN so far), operated by the owner: fader, mute, MC/BAND, MUTE ALL hold, undo.
Rollback: one PR on its own branch; revert the merge commit.

## Phase 5
Not started. Waits for owner approval and answers to D1-D4.
