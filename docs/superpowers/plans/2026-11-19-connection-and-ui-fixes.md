# Connection Diagnosis and UI Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the console say exactly why the FLOW 8 is not connected (USB first, then BLE), fix the Show Mode editor's UI defects, and produce a short CueAir UI study the owner can choose from.

**Architecture:** No new transport behaviour. The hub gains read-only diagnostics (the Windows MIDI Out device list, a BLE handshake trace) that flow through the existing `transport` snapshot into the existing Routing page and top bar. UI fixes are CSS and small `app.js` changes. Nothing here sends a command to the mixer.

**Tech Stack:** Python 3 (`unittest`, ctypes WinMM, bleak), vanilla JS UI, Playwright for the live check.

**Spec:** None for this plan. The owner's request is the message "ผมอยากแก้การเชื่อมต่อ และ UI ก่อน" plus three answers given in this session: fix USB first and then BLE; fix the white dropdowns, the phone editor, and the connection status display; study the CueAir UI for more.

## Global Constraints

- Do not commit, push or deploy. The owner orders commits. The stray staged file `.impeccable/critique/2026-11-19T14-05-06Z__flow8-web-ui-index-html.md` must never be committed with this work.
- Repo files are CRLF (`index.html` too). Edit in a way that preserves each file's endings. New files may be LF.
- Test suite: `python -m tools.run_tests_no_hw` (last full run: 408 ran, 403 passed, 5 hardware skipped). Single file: `python -m unittest tests.<name>`. JS check: `node --check flow8/web_ui/app.js`.
- UI floor: 44 px touch targets, 12 px minimum font, no horizontal scroll at 390 px.
- Diagnostics only report what was observed. Never show "connected" from a guess. Provenance words stay UNSYNCED / COMMANDED / OBSERVED.
- No secrets, device addresses or personal data in logs or docs.

## Verified Starting Facts (read-only, this session)

- `/api/session` at 22:2x: transport mode `usb_midi`; USB error `Device 'FLOW 8 MIDI OUT' not found in MIDI Out enumeration.`; BLE `connected False`, `authenticated False`, `packetsRx 0`, `packetsTx 0`.
- WinMM lists exactly one MIDI Out device: `Microsoft GS Wavetable Synth`. No FLOW 8 endpoint is present.
- Windows Plug and Play still lists FLOW 8 MIDI IN/OUT and the Streaming audio device, all with status `Unknown`. That means they were seen before and are not attached now: cable out, mixer off, or mixer not in USB mode.
- `flow8/service.py:154` sets `_transport_mode = "usb_midi"` at every start. The mode is not saved, so a restart drops a BLE choice back to USB.
- `flow8/midi_out.py:157` matches the device with `self._target_name in caps.szPname` (substring, exact case).

## Review Focus

1. A device named differently by Windows (for example `MIDIOUT2 (FLOW 8)`): the diagnosis must list every name it saw, so a naming mismatch is visible instead of "not found".
2. `midiOutGetNumDevs()` returns 0, or WinMM is unavailable (non-Windows, offline tests): diagnosis returns an empty list and a clear reason, never raises.
3. BLE trace growth: a long session must not grow without bound (fixed-size ring) and must hold no key material beyond what `AUTH_PACKET` already is in source.
4. Status pill when USB and BLE disagree (USB error plus BLE authenticated in hybrid mode): the pill must show the control path that is actually in use.
5. Show Mode editor with a long step list at 390 px: no horizontal scroll, every control reachable.

---

### Task 1: USB diagnosis in the hub

**Files:**
- Modify: `flow8/midi_out.py` (add a listing method next to `find_device_id`, line 149)
- Modify: `flow8/service.py` (the transport snapshot that builds the `usb` block, near line 359-384)
- Test: `tests/test_midi_diagnosis.py` (new)

**Interfaces:**
- Produces: `Flow8MidiOut.list_device_names() -> list[str]` (all MIDI Out names, empty list when WinMM is unavailable or reports zero devices, never raises).
- Produces: the `usb` block of the transport snapshot gains `devicesSeen: list[str]` and `diagnosis: str`. `diagnosis` is one of `"connected"`, `"no_midi_devices"`, `"flow8_not_listed"`, `"open_failed"` (names are the contract; the UI maps them to text in Task 2).

- [ ] **Step 1: Write failing tests** in `tests/test_midi_diagnosis.py`, using a stub in place of `ctypes.windll.winmm` (the style of the existing midi_out tests): `test_list_device_names_returns_every_name`, `test_list_device_names_empty_when_no_devices` (asserts `[]`), `test_list_device_names_never_raises_without_winmm` (asserts `[]` when `_winmm` is `None`), `test_diagnosis_flow8_not_listed_names_what_was_seen` (stub lists only `Microsoft GS Wavetable Synth`; asserts `diagnosis == "flow8_not_listed"` and `devicesSeen == ["Microsoft GS Wavetable Synth"]`), `test_diagnosis_no_midi_devices`, `test_diagnosis_connected`.
- [ ] **Step 2: Run** `python -m unittest tests.test_midi_diagnosis`. Expected: FAIL (`list_device_names` missing).
- [ ] **Step 3: Implement** `list_device_names` in `flow8/midi_out.py` by reusing the enumeration loop of `find_device_id`; wrap in try/except returning `[]`. Add the two keys to the `usb` snapshot in `flow8/service.py`, deriving `diagnosis` from the open state, the name list and the last error.
- [ ] **Step 4: Run** `python -m unittest tests.test_midi_diagnosis`. Expected: PASS. Then `python -m tools.run_tests_no_hw`. Expected: no failures, 5 skipped.
- [ ] **Step 5: Owner action, then read-only check.** Ask the owner to plug the USB cable into the FLOW 8, power the mixer on, and say when done. Then run `curl -s http://127.0.0.1:8844/api/session` and report `usb.devicesSeen` and `usb.diagnosis` as printed. If `flow8_not_listed` persists with the mixer attached, the printed names decide the next fix (a name mismatch means a one-line change to the match rule, with its own test). Do not change the match rule before seeing the names.

### Task 2: Connection status the player can read

**Files:**
- Modify: `flow8/web_ui/index.html` (top bar lamps near line 19), `flow8/web_ui/app.js` (`renderStatusBar` at line 2702, `renderRoutingPage` at line 1691), `flow8/web_ui/styles.css`
- Test: `tests/test_web_console.py` (static asset guards, same style as `ShowModeAssetsTests`)

**Interfaces:**
- Consumes: `usb.diagnosis`, `usb.devicesSeen` from Task 1; `ble.authenticated`, `ble.connected`, `session.transportMode`.
- Produces: a single top-bar pill `id="link-pill"` with `data-state` of `ok`, `warn` or `down`, and a one-line reason in its `title` and in the Routing page. Tapping it opens Setup, Routing.

- [ ] **Step 1: Write failing asset tests**: index.html has `id="link-pill"`; app.js has `function linkSummary(` and the diagnosis keys `flow8_not_listed` and `no_midi_devices`; app.js no longer renders the bare `OFFLINE` for USB without a reason.
- [ ] **Step 2: Run** `python -m unittest tests.test_web_console`. Expected: FAIL on the new tests only.
- [ ] **Step 3: Implement** `linkSummary(session) -> {state, text}` in `app.js`. Text examples the owner reads: `USB: FLOW 8 not found. Check the cable and that the mixer is on.`; `BLE: connected, waiting for the mixer to confirm (RX 0).`. The pill reflects the control path of the current transport mode only. In the Routing page, list `devicesSeen` under the USB row.
- [ ] **Step 4: Run** `node --check flow8/web_ui/app.js` and `python -m unittest tests.test_web_console`. Expected: PASS.
- [ ] **Step 5: Live check** with a Playwright script in the scratchpad at 1280, 1180 and 390 px: the pill is at least 44 px tall, readable, no horizontal scroll, no JS errors. Report the measured numbers.

### Task 3: BLE handshake trace, then one clean retest

**Files:**
- Modify: `flow8/ble_transport.py` (handshake near line 398-411, the notification handler near line 348, the snapshot near line 203)
- Test: `tests/test_ble_transport_trace.py` (new; use the fake client approach of the existing BLE tests)

**Interfaces:**
- Produces: `ble` snapshot gains `trace: list[{t: float, event: str, detail: str}]`, a ring of at most 50 entries. Events: `connect`, `services`, `write_auth`, `rx` (first byte type and length only, not the payload), `ack_timeout`, `disconnect`.

- [ ] **Step 1: Write failing tests**: `test_trace_records_auth_write_then_timeout` (fake client never answers; asserts the order `write_auth`, `ack_timeout`), `test_trace_records_rx_type_and_length_only` (asserts no payload bytes in `detail`), `test_trace_is_a_bounded_ring` (push 200 events; asserts length 50 and that the newest are kept).
- [ ] **Step 2: Run** `python -m unittest tests.test_ble_transport_trace`. Expected: FAIL.
- [ ] **Step 3: Implement** the ring in `ble_transport.py` and show the last 8 entries on the Routing page under the BLE row.
- [ ] **Step 4: Run** the new tests, then `python -m tools.run_tests_no_hw`. Expected: PASS, no new failures.
- [ ] **Step 5: Owner action and retest.** Ask the owner to fully close the FLOW 8 phone app (force close, and switch the phone's Bluetooth off), restart the mixer, then set the console to BLUETOOTH BLE on the Routing page. Read `ble.trace`, `ble.packetsRx` and `ble.authenticated` from `/api/session` and report them as printed.
- [ ] **Step 6: Decision gate (stop and report).** If `authenticated` is true: BLE is solved, record it. If `rx` events appear but no `0x36`: the mixer answers something else, so report the first byte types. If there are no `rx` events at all: report that the mixer ignores the auth write, and propose comparing `AUTH_PACKET` (`flow8/ble_transport.py:25`) with `docs/product/REA_FLOW_MIX_SPEC.md` section 3 and the captured logs, as a separate plan. Do not edit `AUTH_PACKET` in this plan.

### Task 4: Show Mode editor UI fixes

**Files:**
- Modify: `flow8/web_ui/styles.css` (`.show-step` rules at line 163-165), `flow8/web_ui/app.js` (`showModeEditor`)
- Test: `tests/test_web_console.py`

**Interfaces:**
- Consumes: the existing editor markup (`.show-mode-card`, `.show-step`, `.show-mode-foot`).

- [ ] **Step 1: Write failing asset tests**: styles.css has a rule giving `.show-step select` a dark background and light text, and `color-scheme: dark` for the editor; styles.css has a `max-width: 520px` rule that stacks `.show-step` controls so each is full width.
- [ ] **Step 2: Run** `python -m unittest tests.test_web_console`. Expected: FAIL on the new tests only.
- [ ] **Step 3: Implement** the CSS: dark `select` and `option` colours from the existing tokens, `color-scheme: dark`, and at 520 px and below each step control at `flex: 1 1 100%` with the remove button staying 44 px.
- [ ] **Step 4: Live check** at 390 px with Playwright: the dropdown background is dark (read the computed `background-color`), `document.documentElement.scrollWidth <= window.innerWidth`, every control at least 44 px tall. Take a screenshot into the scratchpad and read it.
- [ ] **Step 5: Run** `python -m tools.run_tests_no_hw`. Expected: no failures.

### Task 5: CueAir UI study (research, no product code)

**Files:**
- Create: `docs/product/CUEAIR_UI_ADAPTATION.md`

**Interfaces:**
- Consumes: `docs/reverse-engineering/03_CUEAIR_APP_INVENTORY.md` (UI icon and tab assets), `05_CUEAIR_FUNCTION_ANALYSIS.md`, `08_CUEAIR_FEATURE_MATRIX.md`, `docs/audit/REAL_WORLD_UX_UI_AUDIT.md` (it audits the old Tk app against CueAir, so its CueAir column is the main written source).
- Produces: a table of at most 10 CueAir UI ideas. Each row: the idea, the evidence (file and line, or the asset name), what it costs in this codebase, and whether the FLOW 8 hardware supports it. Honest gaps are stated (the matrix already says CueAir docs overstate FLOW 8 support).

- [ ] **Step 1: Read** the four sources and extract UI facts only (strip layout, per-channel colour, solo, bus master faders, flip mode, meters, navigation). Mark every item **VERIFIED** (read in a file) or **ASSUMPTION**.
- [ ] **Step 2: Write** the document with a ranked recommendation of the top 3 for this console.
- [ ] **Step 3: Stop.** Hand the document to the owner to choose from. Do not build any of it in this plan.

## Not in this plan (decisions left to the owner)

- Saving the transport mode across restarts (today it resets to USB at every start).
- Changing the device-match rule in `midi_out.py` (only after Task 1 shows the real names).
- Scene Advance / Setlist Cue Card and the Preset Library (queued after the fixes).
- Committing the Show Mode branch.
