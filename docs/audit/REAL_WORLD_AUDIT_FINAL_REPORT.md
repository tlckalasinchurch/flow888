# FLOW 8 Real-World UX/UI & Functionality Audit — Final Master Report

**Document ID:** AUDIT-FINAL-REPORT  
**Repository:** `https://github.com/tlckalasinchurch/flow888`  
**Audited Branch / Commit:** `stage2-mixer-workstation` (`456fd5a`)  
**Target Hardware:** Physical Behringer FLOW 8 Digital Mixer (`FLOW 8 MIDI OUT` ID 1, `FLOW 8 MIDI IN` ID 0)  
**Audit Date:** 2026-11-18  

---

## A. Product Verdict

> ### **VERDICT: B+ / C- Border — A Partially Functional Hardware Controller (`Classification B` approaching `C`), NOT Yet a Production-Ready Live Mixer Workstation (`D`).**

### Evidence for Classification:
1. **Why it is MORE than a visual prototype (`A`):**
   - It has a real, thread-safe Windows Multimedia (`winmm.dll`) USB MIDI engine (`Flow8MidiOut`, `Flow8MidiIn`), a strict 85-parameter allowlist boundary (`Flow8CommandBoundary`), a 5-tier provenance state store (`Flow8StateStore`), a compensating transaction ledger (`CommandLedger`), and real UI controls that transmit verified Control Change messages (`CC 1–5`, `7`, `9–12`, `14–17`) to a connected physical Behringer FLOW 8 mixer.
2. **Why it is NOT yet a reliable bidirectional controller (`C`) or production-ready live workstation (`D`):**
   - **Broken Inbound UI Sync (`D-01`):** Moving a physical fader, pan, or mute on the FLOW 8 updates `Flow8StateStore`, but `MixerConsole` never subscribes to `service.add_listener()`, so the on-screen faders never move.
   - **Stale Inspector UI on Preset Apply & Undo (`D-02`):** Applying a CueAir preset or clicking `↶ UNDO` / `↷ REDO` updates the hardware and `StateStore`, but the open `ChannelDetailPanel` sliders and readouts remain frozen at their old values until the user manually clicks another channel and comes back.
   - **Incomplete Scene Capture (`D-04`):** Clicking `CAPTURE` on a Scene saves *only* `fader`, `pan`, and `mute`, silently discarding all 4-Band EQ, Low Cut HPF, Compressor, and Aux Send (`Mon 1`, `Mon 2`, `FX 1`, `FX 2`) settings!
   - **Blocked Preamp Gain (`D-07`) & Missing Bus Masters (`D-08`):** Input Preamp Gain is permanently disabled in the UI (`APPLY — GATED`), and there are no master faders for `MON 1`, `MON 2`, `FX 1`, or `FX 2` busses anywhere in the UI.
   - **Horizontal Strip Clipping When Inspector Opens (`D-06`):** At `1366×768`, opening the Inspector squeezes all 8 channel strips to `100–106 px`, clipping their labels (`132–142 px` requested width).

---

## B. Functionality Score

Across **64 distinct control groups (112 total interactive widget instances)**:

| Status Category | Control Groups | Widget Instances | Percentage (by Group) |
|---|---|---|---|
| **1. WORKING** (Complete path verified) | 32 | 73 | **50.0%** |
| **2. PARTIALLY WORKING** (Outbound works; inbound sync, batching, or UI refresh missing) | 16 | 23 | **25.0%** |
| **3. UI ONLY** (Disabled nav items, gated gain preview, no-op preset checkbox) | 7 | 7 | **10.9%** |
| **4. MOCKED** (Fake data / simulated hardware) | 0 | 0 | **0.0%** *(Zero fake telemetry!)* |
| **5. UNSUPPORTED** (Hardware/protocol limitation properly blocked in UI) | 5 | 5 | **7.8%** |
| **6. BROKEN** (`sync_fader`/`sync_pan`/`sync_mute` unwired; `fader_badge` dead check) | 4 | 4 | **6.3%** |
| **7. UNVERIFIED** | 0 | 0 | **0.0%** |
| **TOTAL** | **64** | **112** | **100.0%** |

---

## C. UX/UI Score

- **Nielsen 10 Heuristics Score:** **`25 / 40` (62.5% — Acceptable, Needs Targeted Fixes)**
- **Impeccable 5-Dimension Technical Score:** **`13 / 20` (65.0% — Acceptable)**

| Dimension | Score | Summary |
|---|---|---|
| **Usability & Learnability** | **2.5 / 5** | Channel headers lack visual affordance showing they open EQ/Dynamics/Sends; protocol jargon (`CMD`, `OBS`, `APPLY — GATED`) confuses beginners. |
| **Clarity & Honesty** | **4.0 / 5** | Exemplary honesty about unconfirmed hardware state (`HW APPLIED: UNKNOWN`) and `+48V` safety warnings, marred by stale Inspector values after Preset/Undo. |
| **Accessibility** | **2.0 / 5** | Good keyboard/wheel support on sliders, but `7–8pt` fonts and `20px`-tall buttons are too small for live stage operation at arm's length. |
| **Live Mixing Workflow** | **2.5 / 5** | Blocked preamp gain, missing Monitor/FX master faders, and 1-band-per-undo on `RESET FLAT` slow down a real sound engineer during rehearsal. |
| **Responsive Layout** | **2.0 / 5** | Fits at `1600×900` (closed) and `1366×768` (closed), but clips all 8 strips at `1366×768` when Inspector opens, and overflows at `1280×720` / `1024×768`. |
| **Visual Quality** | **3.5 / 5** | Cohesive dark studio Cyber Neon palette (`#080B12` / `#131A28` / `#00E5FF`) and crisp custom Canvas sliders/faders. |

---

## D. Hardware Score

- **Physical Hardware Tested:** Behringer FLOW 8 (`FLOW 8 MIDI OUT` WinMM ID 1, PID `0x0066`; `FLOW 8 MIDI IN` WinMM ID 0, PID `0x0067`).
- **Allowlisted & Verified Protocol Parameters:** **85 parameter IDs** across MIDI Channels `1–12`.
- **UI-Reachable Hardware Parameters:** **76 / 85 (89.4%)** reachable (`ch1..7` fader, mute, pan, 4-band EQ, 4 sends; `ch1..4` low cut, compressor; `ch1..2` phantom; `main` fader, balance).
- **Backend-Only (Unreachable from UI):** **9 / 85 (10.6%)** (`ch1..4.gain` gated in UI; `mon1.fader`, `mon2.fader`, `fx1.fader`, `fx2.fader` missing from UI; `global.ez_gain` unspecified).
- **Hardware Telemetry Coverage:** Truthfully reflects FLOW 8 USB MIDI limitations (no meter stream, no initial state dump, write-only EQ/Dyn/Sends). However, inbound CC telemetry for Fader/Pan/Mute (`USB TX: ON`) is dropped between `Flow8StateStore` and `MixerConsole` (`Defect D-01`).

---

## E. Critical Defects (P0 & P1)

- **P0 Blocking Defects:** **0** (No unsafe hardware behavior or crash).
- **P1 Major Defects:** **8**
  1. **`D-01 [P1]`:** Inbound hardware MIDI CCs (`fader`, `pan`, `mute`) update `Flow8StateStore` but never update `MixerConsole` channel strips (`sync_fader`/`sync_pan`/`sync_mute` are never called in production).
  2. **`D-02 [P1]`:** Applying a CueAir preset or clicking `↶ UNDO` / `↷ REDO` updates `Flow8StateStore` and hardware, but leaves the open `ChannelDetailPanel` sliders, readouts, and badges frozen at stale values.
  3. **`D-03 [P1]`:** Inspector sliders (`EQ`, `HPF`, `Comp`, `Sends`) and `RESET FLAT (0 dB)` do not batch transactions (`begin_batch`/`end_batch`), flooding the undo stack and requiring 4 separate undos to revert `RESET FLAT`.
  4. **`D-04 [P1]`:** Scene `CAPTURE` and `RECALL` only save/restore `fader`, `pan`, and `mute`, silently discarding all EQ, Low Cut, Compressor, and Aux Send settings (and scenes are lost on app exit).
  5. **`D-05 [P1]`:** Disconnecting/reconnecting hardware resets `Flow8StateStore` provenance to `UNSYNCED`, but leaves `▲ CMD` badges displayed in `ChannelDetailPanel` and leaves pre-disconnect undo history active in `CommandLedger`.
  6. **`D-06 [P1]`:** Opening `ChannelDetailPanel` at `1366×768` clips all 8 channel strips horizontally (`105 px` actual width vs `132–142 px` requested width).
  7. **`D-07 [P1]`:** Preamp Gain (`CC 8`, Ch 1–4) is permanently gated/disabled in the UI (`APPLY — GATED`), preventing software preamp gain adjustment.
  8. **`D-08 [P1]`:** Monitor 1, Monitor 2, FX 1, and FX 2 Bus Master faders (`Ch 9–12, CC 7`) and Channel Solo (`CC 6`) are missing from the UI.

---

## F. UI-Only and Non-Operational Elements

1. **Left Navigation Rail — `Routing` (`NOT IMPLEMENTED`):** Disabled button (`navigation.py:30`).
2. **Left Navigation Rail — `FX` (`NOT IMPLEMENTED`):** Disabled button (`navigation.py:31`), even though `list_fx_presets` exists in `Flow8Service`.
3. **Left Navigation Rail — `Scenes` (`NOT IMPLEMENTED`):** Disabled button (`navigation.py:32`), contradicting the active `SceneBar` in the console banner.
4. **Left Navigation Rail — `Recording` (`NOT IMPLEMENTED`):** Disabled button (`navigation.py:33`).
5. **Inspector `ANALOG GAIN · PREVIEW ONLY` Slider & `APPLY — GATED` Button:** Moves preview text on screen (`channel_detail.py:552`), never sends MIDI.
6. **`PresetPickerDialog` — `Preserve Fader & Gain (Safe Mix)` Checkbox:** Checking or unchecking changes nothing because `apply_channel_preset` (`service.py:434`) ignores the `preserve_levels` parameter and never touches fader/gain either way.
7. **`ChannelStripWidget` — `self.fader_badge` Checks:** `mixer_console.py` checks `if hasattr(self, "fader_badge"):` in 4 places, but never creates `self.fader_badge`.

---

## G. Real Musician & Sound Engineer Experience Summary

- **What works well:** Connecting the FLOW 8 is non-blocking and fast; dragging faders, panning, muting, dialing in the 4-band EQ, sweeping the Low Cut filter, adding 1-knob compression, and adjusting Monitor/FX sends all transmit clean, byte-accurate MIDI CCs to the hardware. The `+48V` confirmation dialog prevents accidental condenser phantom power blasts.
- **What frustrates a real user during rehearsal:**
  1. You cannot adjust Mic 1–4 preamp gain from the app (`APPLY — GATED`).
  2. You can turn up Ch 1's send to Monitor 1, but there is no Monitor 1 Master Fader in the app to turn up the stage wedge!
  3. When you apply a vocal preset or hit `Ctrl+Z`, the EQ sliders you are looking at on screen don't move—making you think the preset or undo didn't work!
  4. When you save a Scene after spending 15 minutes EQing the band, recalling that Scene only restores faders, pan, and mutes—losing your entire EQ, compression, and monitor mix!

---

## H. Test Evidence Summary

- **Automated Test Suite (`python -m unittest discover tests`):**
  - `351` tests executed: **`339` passed**, **`7` expected failures** (new defect reproduction suite in `tests/test_real_world_audit_defects.py`), **`5` hardware tests** (passed when run with `FLOW8_HW_TESTS=1 FLOW8_HW_TESTS_MUTATE=1`).
- **Live Hardware Sweep (`run_deep_audit.py`):**
  - Verified 15 outbound Control Change messages across Ch 1 (`CC 1, 2, 3, 4, 5, 7, 9, 10, 11, 14, 15, 16, 17`) and Ch 8 (`CC 10`) on physical `FLOW 8 MIDI OUT` (Device ID 1).

---

## I. Final Recommendation

> ### **RECOMMENDATION: REQUIRE TARGETED P1 FIXES BEFORE ACCEPTING STAGE 2 AS PRODUCTION-READY**
>
> The architectural foundation (Stage 1 provenance model, command boundary, parameter engine, WinMM driver, and Stage 2 tabbed DSP controls) is **sound and should be preserved**. However, **Stage 2 should not be signed off as production-ready until Defects `D-01` through `D-08` are resolved** in a focused Stage 2.1 remediation pass.


---

## Stage 1 Addendum — State Synchronisation & Integrity (D-01, D-02, D-05)

**Scope:** only D-01, D-02, D-05. No UI expansion, no new hardware features, no MIDI mapping changes. Stage 2/3 not started.

**Files modified:** `flow8/service.py` (`RECONCILE_EVENT`, `STATE_CHANGED_EVENT`, notifications), `flow8/state_model.py` (`reconcile_reconnect` clears commanded state), `flow8/ledger.py` (`reconcile_connection` clears undo), `flow8/ui/components/mixer_console.py` (queue + listener + `reset_unsynced`, inspector refresh), `flow8/ui/components/channel_detail.py` (`on_applied`). Tests: new `tests/test_stage1_state_sync.py`; `tests/test_real_world_audit_defects.py` (removed `expectedFailure` from D-01, D-02a/b, D-05; test now drains the UI queue). Docs: this file, the defect register, the test results.

**Results:** 366 run, 358 passed, 0 failed, 5 skipped (hardware, not enabled), 3 expected failures (D-03, D-04, D-06). Hardware tests: not run.

**Remaining limitations:**
1. No physical-hardware verification of inbound sync or reconnect this stage (ASSUMPTION: real `winmm` callbacks behave like the offline handler feed).
2. Only fader/pan/mute (+Main fader/balance) have inbound telemetry paths in the service; phantom/gain observations refresh the inspector only. Other parameters cannot be observed (no protocol evidence).
3. Disconnect also resets the commanded `+48V` display to OFF; the real mixer state is unknown after a disconnect.
4. Status bar feedback text is not cleared on disconnect. Tcl teardown warnings (D-14) remain. D-03/D-04/D-06 (inspector undo batching, scene coverage, strip clipping) remain open.
5. After reconnect the UI shows app defaults as UNSYNCED, not the mixer's real values; no state read-back exists in the protocol.
