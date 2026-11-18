# FLOW 8 Real-World Audit — Phase 8: Prioritized Improvement Roadmap

**Document ID:** AUDIT-P8-ROADMAP  
**Target Branch:** `stage2-mixer-workstation` (`456fd5a`)  

---

## 1. Prioritization Principles

Improvements are strictly ordered by live-audio operational impact:
- **P0 — Safety, Data Integrity & Hardware Correctness:** Prevent unexpected audio surges, false state confidence, or data loss.
- **P1 — Core Mixer Functionality & Synchronization:** Ensure every control works bidirectionally (where supported), updates the UI accurately, and captures complete mixes.
- **P2 — Usability, Layout & Live Workflow Speed:** Eliminate clipping at laptop/tablet resolutions, remove dead navigation clutter, and speed up stage operation.
- **P3 — Visual Polish & Code Hygiene:** Clean up font token usage and Tk shutdown timers.

---

## 2. Actionable Engineering Roadmap

### Tier P1: State Synchronization & Core Mixer Functionality (Immediate Must-Fix Before Stage Acceptance)

1. **[Fix D-01] Wire Inbound Hardware MIDI Events to `MixerConsole` Strips**
   - **Files:** `flow8/ui/components/mixer_console.py`
   - **Action:** Register `self.service.add_listener(self._on_state_event)` in `MixerConsole.__init__` (and remove in `destroy()`). Schedule a main-thread handler via `self.after_idle` that routes `ch{1..7}.fader` -> `strips[n].sync_fader()`, `main.fader` -> `strips[8].sync_fader()`, `ch{1..7}.pan` -> `strips[n].sync_pan()`, `main.balance` -> `strips[8].sync_pan()`, and `ch{1..7}.mute` -> `strips[n].sync_mute()`.

2. **[Fix D-02] Refresh Open `ChannelDetailPanel` on Preset Apply, Scene Recall, and Undo/Redo**
   - **Files:** `flow8/ui/components/channel_detail.py`, `flow8/ui/components/mixer_console.py`
   - **Action:**
     - Pass `on_applied=lambda _preset_id: self._refresh_if_attached()` when opening `PresetPickerDialog` in `ChannelDetailPanel._on_open_presets()`.
     - Call `self.inspector._refresh_if_attached()` inside `MixerConsole._refresh_strips()` so every Undo, Redo, and Scene Recall immediately updates the open Inspector sliders, readouts, and provenance badges.

3. **[Fix D-03] Add Gesture Batching (`begin_batch` / `end_batch`) to All Inspector Sliders & `reset_eq_flat()`**
   - **Files:** `flow8/ui/components/channel_detail.py`
   - **Action:**
     - Bind `<ButtonPress-1>` to `_dispatch_service(self._service, "begin_batch")` and `<ButtonRelease-1>` to flush + `_dispatch_service(self._service, "end_batch")` on `eq_sliders`, `low_cut_slider`, `comp_slider`, and `send_sliders`.
     - Wrap `reset_eq_flat()` in `begin_batch()` / `end_batch()` so resetting 4 EQ bands is a single atomic undo step.

4. **[Fix D-04] Expand Scene Capture & Recall to Include Full Channel DSP & Aux Sends + Disk Persistence**
   - **Files:** `flow8/service.py`, `flow8/scenes.py`
   - **Action:**
     - Expand `REVERSIBLE_PARAMETERS` and `SceneManager.ALLOWED_PARAMETERS` from `("fader", "pan", "mute")` to include `("fader", "pan", "mute", "eq_low", "eq_low_mid", "eq_hi_mid", "eq_hi", "low_cut", "compressor", "send_mon1", "send_mon2", "send_fx1", "send_fx2")`. (Continue strictly excluding `+48V` phantom power).
     - Add optional JSON persistence so scenes survive application restarts.

5. **[Fix D-05] Reconcile UI Provenance Badges & Clear Undo Stack on Hardware Disconnect/Reconnect**
   - **Files:** `flow8/ledger.py`, `flow8/ui/app.py`, `flow8/ui/components/mixer_console.py`
   - **Action:**
     - Clear `self._undo.clear()` in `CommandLedger.reconcile_connection()`.
     - In `Flow8App._refresh_hardware_status()`, notify `self.mixer_console` to refresh its history buttons, strip provenance labels, and open `ChannelDetailPanel` badges so `▲ CMD` resets to `○ UNSYNC` on disconnect.

6. **[Fix D-07] Enable Confirmed Staged Dispatch for Preamp Gain (`CC 8`, Ch 1–4)**
   - **Files:** `flow8/ui/safety_dialogs.py`, `flow8/ui/components/channel_detail.py`
   - **Action:** Replace the permanently disabled `APPLY — GATED` button with a staged `APPLY GAIN` confirmation workflow (with a safety warning if gain increases by `> +6 dB`) that calls `Flow8Service.set_gain(ch, raw, unit="raw")`.

7. **[Fix D-08] Expose Monitor 1, Monitor 2, FX 1, FX 2 Bus Master Faders (`Ch 9–12, CC 7`) & Channel `SOLO` (`CC 6`)**
   - **Files:** `flow8/service.py`, `flow8/command_boundary.py`, `flow8/ui/components/mixer_console.py`, `flow8/ui/components/channel_detail.py`
   - **Action:**
     - Add `set_bus_fader(bus_name, raw_value)` to `Flow8Service` and expose Monitor 1/2 & FX 1/2 master faders in the UI (either in the Master strip inspector or a Bus Master strip/drawer).
     - Add `ch1..7.solo` (`CC 6`) to `Flow8CommandBoundary.ACTIVE_ALLOWLIST`, `Flow8ParameterEngine`, `Flow8Service`, and channel strips.

---

### Tier P2: Responsive Layout & Live Usability Improvements

8. **[Fix D-06 & D-10] Reclaim Horizontal & Vertical Space for `1366×768` and `1280×720` Operation**
   - **Files:** `flow8/ui/app.py`, `flow8/ui/components/navigation.py`, `flow8/ui/components/mixer_console.py`, `flow8/ui/components/command_log.py`
   - **Action:**
     - Collapse or remove the dead Left Navigation Rail (where 4 of 5 buttons say `NOT IMPLEMENTED`), freeing `113–232 px` of horizontal width so all 8 strips + the `320 px` Inspector fit at `1366×768` and `1280×720` with zero clipping (`strip.winfo_width() >= strip.winfo_reqwidth()`).
     - Shorten strip MIDI readout from `"MIDI 101/127 DEFAULT"` (`142 px`) to `"RAW 101 · UNSYNC"` (`~100 px`) and restore a compact provenance indicator on each strip.
     - Make `CommandLogPanel` collapsible (`[▲ SHOW / ▼ HIDE COMMAND LOG]`) so faders get an extra `140 px` of vertical throw during live mixing.

9. **[Fix D-09, D-11, D-12] Fix `pack_propagate`, Compressor Slider Maximum (`100`), and Preset Checkbox**
   - **Files:** `header.py`, `navigation.py`, `status_bar.py`, `channel_detail.py`, `preset_picker.py`
   - **Action:**
     - Call `self.pack_propagate(False)` on fixed-height/width frames that use `.pack()`.
     - Set `self.comp_slider.maximum = 100` in `ChannelDetailPanel._build_dyn_tab()`.
     - Replace the no-op `Preserve Fader & Gain` checkbox in `PresetPickerDialog` with an informative badge (`" Safe Mix Guarantee: Presets only modify EQ, HPF & Compressor — Fader & Gain are never altered"`).

---

### Tier P3: Visual & Lifecycle Polish

10. **[Fix D-13 & D-14] Standardize Font Tokens & Cancel Pending `after_idle` Handles on Destroy**
    - **Files:** `flow8/ui/safety_dialogs.py`, `flow8/ui/components/controls.py`, `flow8/ui/components/channel_detail.py`, `flow8/ui/components/mixer_console.py`
    - **Action:** Replace hard-coded `("Segoe UI", ...)` tuples with `self.fonts[...]` tokens, and store/cancel `after_idle` handles inside `destroy()` to eliminate Tcl `invalid command name "<lambda>"` warnings on shutdown.
