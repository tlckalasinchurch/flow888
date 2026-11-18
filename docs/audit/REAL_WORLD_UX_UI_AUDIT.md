# FLOW 8 Real-World Audit — Phase 1 & 2: UX, UI Architecture & Visual Audit

**Document ID:** AUDIT-P1-P2-UX-UI  
**Target Branch:** `stage2-mixer-workstation` (`456fd5a`)  
**Visual Reference:** CueAir Professional Digital Mixer Interface  
**Audit Frameworks:** Nielsen 10 Heuristics, Impeccable 5-Dimension Technical Scan, Hallmark Craft Floor  

---

## 1. Phase 1 — Real User UX Audit (Roleplay & Scenario Evaluation)

### 1.1 Scenario A: First-Time User ("Jordan" — Beginner / Volunteer Sound Operator)

| Evaluation Question | Verdict | Evidence & Usability Findings |
|---|---|---|
| **Can a new user understand the interface without reading documentation?** | **PARTIAL** | The 7 input strips + Main L/R strip layout is familiar, but there is **no visual cue** that clicking a channel strip's top header opens the Channel Detail Inspector (`EQ`, `DYN`, `SENDS`). Clicking anywhere on the fader, pan, mute, or readout area does *not* select the channel (`_bind_header_selection` only binds the header frame). A beginner looking for EQ or Reverb sends can stare at the main mixer screen without realizing an inspector panel exists. |
| **Is it obvious how to connect the mixer?** | **YES** | Top-right `CONNECT`, `DISCONNECT`, and `RETRY` buttons next to the status pill (`MIDI PORTS CLOSED` / `MIDI PORTS OPEN`) are clear and immediate. |
| **Can the user identify the selected channel?** | **PARTIAL** | When selected, a strip receives a `2px` cyan border (`#00E5FF`). However, the `Main L/R` strip *always* has a `1px` cyan border (`highlightbackground=colors["cyan"] if is_master else colors["border"]` in `mixer_console.py:88`), making an unselected Main strip look nearly identical to a selected input strip. |
| **Can the user distinguish input channels from stereo channels?** | **YES** | Badges (`XLR`, `COMBO`, `TRS`, `USB`, `MASTER`), subtitles (`Midas Preamp`, `Mic / Line`, `Stereo Line / Hi-Z`, `Audio Return`), and `PAN` vs `BAL` labels clearly differentiate mono vs stereo strips. |
| **Are all controls clearly named & technical terms understandable?** | **NO (Jargon Heavy)** | Labels such as `CMD = last software command · OBS = device input only · HW APPLIED: UNKNOWN`, `APPLY — GATED`, `▲ CMD`, `○ UNSYNC`, and `MIDI 0/127 DEFAULT` read like internal protocol engineering diagnostics rather than musician-friendly audio terms. |
| **Are important functions easy to find?** | **NO** | 1. **EQ, Compressor, HPF, and Aux Sends** are completely hidden until a user discovers they must click a strip's header text. <br>2. **Left Navigation Rail** displays `Scenes — NOT IMPLEMENTED`, while `SCENES 1..8 CAPTURE / RECALL` is simultaneously active in the top banner! This directly contradicts itself. |
| **Is the interface too crowded?** | **YES (at ≤1366px)** | The permanent left Navigation Rail (`WORKSPACE: Mixer, Routing, FX, Scenes, Recording`) has 4 dead buttons (`NOT IMPLEMENTED`) that consume 113px (and were intended in `theme.py` to consume 232px) of horizontal width on every screen, while the `COMMAND LOG` panel consumes 174px of vertical height at the bottom of a live mixing console. |

---

### 1.2 Scenario B: Live Rehearsal ("Alex" — Sound Engineer Mixing a Band)

We executed the exact 14-step Live Rehearsal workflow against the running `Flow8App` and connected physical Behringer FLOW 8 hardware:

| Step | Action | Clicks / Gestures | Actual Result | Pass / Fail |
|---|---|---|---|---|
| **1** | Launch application | 1 command | Window opens at `1600×900` (clamped to screen). | **PASS** |
| **2** | Connect FLOW 8 | Auto or 1 click | Opens `FLOW 8 MIDI OUT` (ID 1) and `FLOW 8 MIDI IN` (ID 0) on worker thread. Status shows `MIDI PORTS OPEN`. | **PASS** |
| **3** | Select Channel 1 | 1 click (must click header only) | `ChannelDetailPanel` docks on right showing `CHANNEL 01 (Mic 1 · MIDI CH 1)` on `PREAMP` tab. | **PASS** |
| **4** | Adjust input gain | Drag slider + click Apply | **FAIL — BLOCKED:** Slider moves `PREVIEW RAW 80/127 · Approx. +30.4 dB · UNVERIFIED — NOT SENT`, and `APPLY — GATED` button is permanently `disabled` (`AnalogGainSafetyGate.is_verified_mapping_available()` returns `False`). **Engineer cannot adjust preamp gain from software.** | **FAIL (Blocked)** |
| **5** | Adjust EQ | Click `EQ` tab + drag sliders | Dispatches CC 1–4 on MIDI Ch 1 after 30ms debounce. Readout updates (`+3.8 dB · raw 80`), badge changes to `▲ CMD`. *(Defect: dragging creates multiple unbatched undo entries).* | **PARTIAL** |
| **6** | Adjust HPF | Click `DYN` tab + drag Low Cut | Dispatches CC 9 on MIDI Ch 1. Readout updates (`166 Hz · raw 32`), badge changes to `▲ CMD`. | **PASS** |
| **7** | Adjust Compressor | Drag Compressor slider | Dispatches CC 11 on MIDI Ch 1. Readout updates (`45% · raw 45`), badge changes to `▲ CMD`. | **PASS** |
| **8** | Adjust Monitor 1 send | Click `SENDS` tab + drag Mon 1 | Dispatches CC 14 on MIDI Ch 1. Readout updates (`-4.2 dB · raw 95`), badge changes to `▲ CMD`. *(Defect: No Monitor 1 Master Bus fader exists in UI!)* | **PARTIAL** |
| **9** | Mute and unmute Ch 1 | Click `MUTE` twice on Strip 1 | Dispatches CC 5 `127` then `0` on MIDI Ch 1. Button turns red (`MUTED`) then gray (`MUTE`). | **PASS** |
| **10** | Switch to Channel 2 | Click Strip 2 header | Inspector updates to `CHANNEL 02`, showing `64` (`0.0 dB`) EQ, `0` (`20 Hz`) HPF, `0%` Comp, `0` (`-inf dB`) Mon 1. | **PASS** |
| **11** | Return to Channel 1 | Click Strip 1 header | Inspector reads `Flow8StateStore` and restores `eq_low=80`, `hpf=32`, `comp=45`, `mon1=95`. | **PASS** |
| **12** | Confirm displayed state accuracy (Preset / Undo / Inbound MIDI) | Apply preset or press `Ctrl+Z` or move hardware fader | **FAIL — STALE UI:** <br>1. Applying a CueAir preset updates `StateStore` (`eq_low=60, hpf=20, comp=30`), but the open Inspector sliders remain frozen at old values (`80, 32, 45`)!<br>2. Clicking `↶ UNDO` updates `StateStore`, but the open Inspector sliders remain frozen!<br>3. Moving a physical fader on the FLOW 8 sends MIDI IN to `StateStore`, but `MixerConsole` never subscribes to `service.add_listener`, so the on-screen fader never moves! | **FAIL (Major Bug)** |
| **13** | Disconnect mixer | Click `DISCONNECT` | Closes WinMM ports; `state_store.reconcile_reconnect()` resets all `ParameterState.provenance` to `UNSYNCED`. **However, the open Inspector badges stay stuck on `▲ CMD` and `ledger.can_undo` remains `True`!** | **FAIL (Stale State)** |
| **14** | Reconnect mixer | Click `CONNECT` | Reopens WinMM ports. UI still displays pre-disconnect `COMMANDED` values and badges even though hardware state is unknown. | **FAIL (Stale State)** |

---

### 1.3 Scenario C: Emergency Operation (Live Feedback / Overload / Dropouts)

| Emergency Task | Supported? | Speed / Ergonomics | Risk Assessment |
|---|---|---|---|
| **Quickly mute a runaway channel** | **YES** | **Fast (1 click):** `MUTE` buttons are permanently visible on all 7 input strips in the main console. | **Low Risk** (Outbound CC 5 works reliably). |
| **Quickly pull down Master output** | **YES** | **Fast (1 drag):** `Main L/R` fader is permanently docked on the far-right strip (Strip 8). However, **there is no Master Mute button** (FLOW 8 hardware has no Main Mute CC, and no software "dim/cut to 0" button is provided). | **Medium Risk** (Must drag fader to bottom rather than 1-click Master Cut). |
| **Identify clipping or overload** | **NO** | **Impossible:** Zero level meters or clip LEDs exist in the application (`AUDIO TELEMETRY: NO TELEMETRY`). | **High Risk** (Engineer cannot see which mic is clipping without looking at the physical mixer or hearing distortion). |
| **Identify connection failure** | **YES** | **Good (≤2.5s):** If a MIDI dispatch fails with `MMSYSERR_INVALHANDLE` / `MMSYSERR_NODRIVER`, `midi_out.close()` triggers immediately and the 2.5s `_poll_hardware_state` loop updates the header pill to `MIDI PORTS ERROR` / `PARTIAL` in red/amber. | **Low Risk**. |
| **Recognize confirmed vs unconfirmed command** | **PARTIAL** | Command Log and Status Bar state `HW APPLIED: UNKNOWN`, but channel strips lose their provenance label after the first fader move (showing only `MIDI 80/127`). | **Medium Risk**. |

---

## 2. Phase 2 — Visual & UI Architecture Comparison vs. CueAir Reference

### 2.1 Structural Comparison: CueAir Reference vs. FLOW 8 Cyber Neon Workstation

| Design Aspect | CueAir Reference Interface | FLOW 8 Cyber Neon Workstation | Audit Verdict |
|---|---|---|---|
| **Channel Strip Organization** | Clean vertical strips with distinct per-channel color coding, prominent solo/mute buttons, stereo/mono badges, and dedicated bus master section. | 7 input strips + 1 Main L/R strip in a uniform grid. All input strips use identical cyan/purple accents with no per-channel color coding. | **Acceptable**, though lack of channel color coding slows visual scanning on stage. |
| **Fader & Meter Visibility** | Large high-contrast fader caps paired alongside dual real-time LED bar meters (`-60` to `0 dBFS` + Clip LED). | Custom `VerticalFader` canvas (`height=220`, `width=84`) with dB ticks (`+10, 0, -10, -20, -40, -∞`), **but zero level meters**. | **Hardware-constrained** (USB MIDI CC has no meter stream, though UI lacks even activity indicators). |
| **Mute / Solo Ergonomics** | Dedicated `MUTE` (red) and `SOLO` (yellow) buttons stacked per strip. | `MUTE` button only (`pady=4`). `CC_SOLO = 6` is defined in `midi_constants.py` but completely absent from UI and service. | **Incomplete** (`SOLO` missing). |
| **EQ & Dynamics Controls** | Visual EQ curve / clearly labeled frequency + gain controls visible in the channel detail view alongside dynamics threshold/ratio meters. | 4 horizontal sliders (`LOW 80 Hz`, `LOW-MID 400 Hz`, `HI-MID 2.5 kHz`, `HIGH 10 kHz`) on `EQ` tab; `LOW CUT` and `1-KNOB COMPRESSOR` on `DYN` tab. | **Good adaptation** to FLOW 8's fixed-frequency 4-band EQ and 1-knob compressor hardware. |
| **Aux / Monitor / FX Bus Masters** | Dedicated Aux/FX master faders and send-on-fader flip mode. | Per-channel Aux Send sliders (`MON 1`, `MON 2`, `FX 1`, `FX 2`) exist in Inspector `SENDS` tab, **but no Bus Master faders (`mon1.fader`, `mon2.fader`, `fx1.fader`, `fx2.fader`) exist anywhere in the UI!** | **Major Functional Gap** (Allowlisted in backend, absent in UI). |
| **Screen Real Estate Allocation** | 100% of viewport dedicated to mixing controls, metering, and active DSP view. | **~25–30% of viewport wasted** on a dead Left Navigation Rail (4 of 5 items `NOT IMPLEMENTED`) and a permanent 174px bottom `COMMAND LOG` engineering table. | **Poor Operational Space Budget**. |

---

## 3. Multi-Resolution & Responsive Layout Audit (Empirical Measurements)

We measured live Tkinter geometry across all four required target resolutions (`1600×900`, `1366×768`, `1280×720`, `1024×768`):

### 3.1 Empirical Geometry Table

| Viewport Size | Inspector State | Console Width × Height | Strip Actual Width vs. Req Width | Clipped Strips Count | Command Log Height | Banner Overlap / Clipping |
|---|---|---|---|---|---|---|
| **1600 × 900** (Default) | Closed | `1487 × 817 px` | `172 px` vs `132–142 px` | **0 / 8** | `174 px` (Full) | None |
| **1600 × 900** (Default) | **Open (320px)** | `1487 × 817 px` | Inputs: `135 px` vs `132 px`<br>Main: **`129 px` vs `142 px`** | **1 / 8 (Main L/R clipped)** | `174 px` (Full) | None |
| **1366 × 768** (Minimum) | Closed | `1253 × 685 px` | `148 px` vs `132–142 px` | **0 / 8** | `85 px` (2 rows visible) | None |
| **1366 × 768** (Minimum) | **Open (320px)** | `1253 × 685 px` | Inputs: **`105 px` vs `132–134 px`**<br>Main: **`100 px` vs `142 px`** | **8 / 8 (ALL strips clipped)** | `85 px` (2 rows visible) | None |
| **1280 × 720** (HD Laptop) | Closed | `1167 × 637 px` | Inputs: `137 px` vs `132 px`<br>Main: **`131 px` vs `142 px`** | **1 / 8 (Main L/R clipped)** | **`37 px` (Table hidden!)** | `UNDO`/`REDO` clipped (`73px` vs `125px`) |
| **1280 × 720** (HD Laptop) | **Open (295px)** | `1167 × 637 px` | Inputs: **`97 px` vs `132–134 px`**<br>Main: **`92 px` vs `142 px`** | **8 / 8 (ALL strips clipped)** | **`37 px` (Table hidden!)** | `UNDO`/`REDO` clipped (`73px` vs `125px`) |
| **1024 × 768** (4:3 Stage Tablet) | Closed | `911 × 685 px` | Inputs: **`105 px` vs `132 px`**<br>Main: **`99 px` vs `142 px`** | **8 / 8 (ALL strips clipped)** | `85 px` | **`SceneBar` & `UNDO/REDO` collide & clip** |
| **1024 × 768** (4:3 Stage Tablet) | **Open (248px)** | `911 × 685 px` | Inputs: **`71 px` vs `132 px`**<br>Main: **`66 px` vs `142 px`** | **8 / 8 (Fader scales crushed to 52px)** | `85 px` | **`SceneBar` & `UNDO/REDO` collide & clip** |

### 3.2 Root Causes of Layout Defects
1. **`grid_propagate(False)` vs `pack_propagate(False)` Bug (`header.py:30`, `navigation.py:51`, `status_bar.py:21`):**
   - `Header`, `Navigation`, and `StatusBar` call `self.grid_propagate(False)` in `__init__`, but pack all of their internal children using `.pack()`. In Tkinter, `grid_propagate` has zero effect on `.pack()` children! Consequently:
     - `Navigation` ignores `NAVIGATION_WIDTH = 232` and shrinks to `113 px`.
     - `StatusBar` ignores `STATUS_BAR_HEIGHT = 36` and shrinks to `20 px`.
2. **Inspector Open State Not Tested in Strip Clipping Tests:**
   - `test_all_strips_fit_the_window_at_the_minimum_size` (`test_mixer_console.py:102`) and `test_everything_fits_at_1366x768` (`test_scene_ui.py:244`) only assert `strip.winfo_width() >= strip.winfo_reqwidth()` when the `ChannelDetailPanel` is **closed**.
   - Opening the 320px inspector reduces each strip's width from `148 px` to `105 px` at `1366×768`, clipping `MIDI 0/127 DEFAULT` (`132 px` wide) and `MIDI 101/127 DEFAULT` (`142 px` wide) on every strip.

---

## 4. Impeccable & Hallmark Design / Technical Evaluation

### 4.1 Nielsen 10 Usability Heuristics Score (`25 / 40` — 62.5% Acceptable / Needs Work)

| # | Heuristic | Score (0–4) | Key Evidence & Finding |
|---|---|---|---|
| 1 | **Visibility of System Status** | **2 / 4** | Honest port status (`MIDI PORTS OPEN`), **but** open Inspector does not update on Preset apply or Undo, and strips ignore inbound MIDI events. |
| 2 | **Match Between System & Real World** | **2 / 4** | Protocol engineering jargon (`CMD`, `OBS`, `HW APPLIED: UNKNOWN`, `APPLY — GATED`) dominates the UI over standard live-sound terminology. |
| 3 | **User Control and Freedom** | **3 / 4** | Visual `↶ UNDO` / `↷ REDO` buttons, `Ctrl+Z`/`Ctrl+Y`, `RESET FLAT`, `BYPASS`, and `+48V` Cancel work well, though EQ drag gestures are unbatched. |
| 4 | **Consistency and Standards** | **2 / 4** | `Scenes` is marked `NOT IMPLEMENTED` in the left Nav Rail while simultaneously implemented in the top banner; `Main L/R` border mimics selected state. |
| 5 | **Error Prevention** | **4 / 4** | Exemplary `+48V` single-use token confirmation dialog (`PhantomPowerSafetyGate`) and `Preserve Fader & Gain` checkbox in `PresetPickerDialog`. |
| 6 | **Recognition Rather Than Recall** | **2 / 4** | Nothing on a channel strip indicates that clicking its header opens EQ, Compressor, HPF, and Aux Sends. |
| 7 | **Flexibility and Efficiency of Use** | **2 / 4** | Double-click reset to default, Shift+drag fine adjustment, and arrow/wheel support on sliders are great, **but** switching channels + tabs takes too many clicks during live mixing. |
| 8 | **Aesthetic and Minimalist Design** | **2 / 4** | High-contrast Cyber Neon palette is visually cohesive, but dead Navigation Rail items and permanent Command Log clutter the live operating surface. |
| 9 | **Help Users Recover from Errors** | **3 / 4** | Clear error banner in Inspector, status bar, and Command Log when dispatches fail, with automatic fader/pan rollback on driver failure. |
| 10 | **Help and Documentation** | **3 / 4** | Acoustic rationale notes inside `PresetPickerDialog` are genuinely helpful for beginners (`Speech`, `Vocal`, `Acoustic`, `Bass`, `Drums`). |
| **Total** | | **25 / 40** | **Acceptable (Significant UX & state-sync fixes needed before live stage use)** |

### 4.2 Impeccable 5-Dimension Technical Audit Score (`13 / 20` — Acceptable)

| # | Dimension | Score (0–4) | Key Technical Finding |
|---|---|---|---|
| 1 | **Accessibility (A11y)** | **2 / 4** | `8pt` font (`eyebrow`, `caption`, `status_key`) and `7pt` fader scale labels are too small for stage viewing distance (1–1.5m); buttons (`pady=1..2`, height ~20px) fall below the 24–44px target minimum. Good keyboard bindings on `_BaseControl`. |
| 2 | **Performance** | **3 / 4** | Background thread connection (`_connection_worker`) prevents UI freezes; 30ms debounce on sliders prevents MIDI queue flooding. Minor issue: `CommandLogPanel.set_entries` deletes and rebuilds all Treeview rows on every single CC during a fader drag! |
| 3 | **Theming** | **3 / 4** | Centralized `theme.COLORS` and `theme.TOKENS` used across most modules, except `safety_dialogs.py` (`lines 214, 224, 235, 249, 263`) and `controls.py` (`line 170`, `line 293`) which hard-code `("Segoe UI", ...)` instead of `self.fonts`. |
| 4 | **Responsive Design** | **2 / 4** | Passes at `1600×900` (closed) and `1366×768` (closed), but clips all 8 strips at `1366×768` when Inspector opens, and breaks severely at `1280×720` and `1024×768`. |
| 5 | **Implementation Integrity** | **3 / 4** | Strong AST boundary separation (`UI -> Service -> Engine -> Boundary -> WinMM`), undermined by 4 disconnected UI sync paths (inbound MIDI to strips, preset apply to inspector, undo to inspector, disconnect to badges). |
| **Total** | | **13 / 20** | **Acceptable (Requires targeted P1 fixes)** |
