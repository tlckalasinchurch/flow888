# FLOW 8 Real-World Audit — Defect Register

**Document ID:** AUDIT-DEFECT-REGISTER  
**Target Branch:** `stage2-mixer-workstation` (`456fd5a`)  
**Total Verified Defects:** 14 (0 P0, 8 P1, 4 P2, 2 P3)  

---

## 1. Defect Summary by Severity

| Severity | Definition | Count | IDs |
|---|---|---|---|
| **P0 — Blocking / Safety Critical** | Causes hardware damage, unsafe phantom/output surges, or prevents application launch | **0** | None *(Safety gates for +48V, CommandBoundary allowlist, and non-undoable unknown baselines are solid)* |
| **P1 — Major Functional / State / Layout Defect** | Breaks expected live-mixing workflows, causes UI/hardware state desynchronization, or clips UI at supported resolutions | **8** | `D-01`, `D-02`, `D-03`, `D-04`, `D-05`, `D-06`, `D-07`, `D-08` |
| **P2 — Minor Usability / Architecture Gap** | Annoyance, dead UI controls, or missing secondary workflow polish | **4** | `D-09`, `D-10`, `D-11`, `D-12` |
| **P3 — Visual / Code Polish** | Hard-coded fonts, shutdown timer warnings (`invalid command name "<lambda>"`) | **2** | `D-13`, `D-14` |

---

## 2. Detailed Defect Register

### [D-01] [P1] **[FIXED — Stage 1, offline-verified]** Inbound Hardware MIDI Events Never Update `MixerConsole` Channel Strips
- **Location:** `flow8/ui/components/mixer_console.py:568-595` (`sync_fader`, `sync_pan`, `sync_mute`) & `642-650` (`MixerConsole.__init__`)
- **Category:** Hardware Synchronization / Implementation Integrity
- **Description:** `ChannelStripWidget` defines `sync_fader()`, `sync_pan()`, and `sync_mute()` to update strip UI and set provenance to `OBSERVED` when inbound MIDI arrives. However, `MixerConsole` never registers a state listener via `self.service.add_listener(...)`.
- **Impact:** When a sound engineer moves a physical fader, pan, or mute on the Behringer FLOW 8 (with `USB TX: ON`), `Flow8StateStore` updates `observed_value`, **but the on-screen fader/pan/mute in `MixerConsole` never moves!**
- **Reproduction Test:** `tests/test_real_world_audit_defects.py::test_d01_inbound_midi_fader_updates_strip_widget`
- **Recommended Fix:** Subscribe `MixerConsole` to `self.service.add_listener(self._on_state_event)`, schedule a main-thread handler via `self.after_idle`, and dispatch `ch{n}.fader` / `main.fader`, `ch{n}.pan` / `main.balance`, and `ch{n}.mute` to the corresponding `ChannelStripWidget.sync_*` method.

---

### [D-02] [P1] **[FIXED — Stage 1, offline-verified]** Open `ChannelDetailPanel` Sliders & Badges Remain Stale After Preset Apply or Undo/Redo
- **Location:** `flow8/ui/components/channel_detail.py:515-526` (`_on_open_presets`), `flow8/ui/components/mixer_console.py:907-923` (`_run_history`), `flow8/service.py:125-133` (`_notify_listeners`)
- **Category:** State Integrity / UI Synchronization
- **Description:**
  1. `Flow8Service._notify_listeners` is only called inside `_on_midi_in_event` (`service.py:268`), never during outbound software commands (`set_eq_band`, `set_low_cut`, `set_compressor`, `set_send`, `apply_channel_preset`, `undo`, `redo`).
  2. `ChannelDetailPanel._on_open_presets` instantiates `PresetPickerDialog` without passing an `on_applied` callback.
  3. `MixerConsole._run_history` calls `self._refresh_strips()` after `undo()`/`redo()`, which only refreshes `ChannelStripWidget`s and never calls `self.inspector._refresh_if_attached()`.
- **Impact:** When a user applies a CueAir preset or clicks `↶ UNDO` / `↷ REDO` while the Channel Detail Inspector is open, the hardware receives the new EQ/HPF/Compressor/Send values, **but the sliders, dB/Hz/% readouts, and provenance badges on screen remain frozen at their previous positions!**
- **Reproduction Tests:** `test_d02a_preset_apply_refreshes_open_inspector_sliders`, `test_d02b_undo_refreshes_open_inspector_sliders`
- **Recommended Fix:** Pass `on_applied=lambda _: self._refresh_if_attached()` in `_on_open_presets()`, and call `self.inspector._refresh_if_attached()` inside `MixerConsole._refresh_strips()`.

---

### [D-03] [P1] Inspector Sliders & `RESET FLAT (0 dB)` Lack Undo Batching (`begin_batch` / `end_batch`)
- **Location:** `flow8/ui/components/channel_detail.py:595-610` (`eq_sliders`), `646-653` (`low_cut_slider`), `695-702` (`comp_slider`), `731-738` (`send_sliders`), `869-881` (`reset_eq_flat`)
- **Category:** Undo / Redo Integrity
- **Description:**
  1. Unlike `ChannelStripWidget` (which binds `<ButtonPress-1>` to `service.begin_batch()` and `<ButtonRelease-1>` to `service.end_batch()`), none of the 10 sliders in `ChannelDetailPanel` batch drag gestures.
  2. `ChannelDetailPanel.reset_eq_flat()` loops over the 4 EQ bands and dispatches `set_eq_band` 4 times without wrapping them in `begin_batch()` / `end_batch()`.
- **Impact:** A single drag of an EQ or Aux Send slider floods the 50-slot `CommandLedger` with dozens of micro-steps, and clicking `RESET FLAT (0 dB)` requires 4 separate clicks of `↶ UNDO` to revert!
- **Reproduction Test:** `test_d03_reset_eq_flat_records_single_atomic_undo_step`
- **Recommended Fix:** Bind `<ButtonPress-1>` and `<ButtonRelease-1>` on all inspector sliders to `begin_batch()` / `end_batch()`, and wrap `reset_eq_flat()` in `begin_batch()` / `end_batch()`.

---

### [D-04] [P1] Scene Capture & Recall Silently Ignore EQ, Low Cut, Compressor, and Aux Sends
- **Location:** `flow8/service.py:38` (`REVERSIBLE_PARAMETERS = ("fader", "pan", "mute")`) & `flow8/scenes.py:25` (`ALLOWED_PARAMETERS = frozenset({"fader", "pan", "mute"})`)
- **Category:** Core Mixer Functionality / Scene Management
- **Description:** `SceneManager` and `Flow8Service.capture_scene` / `recall_scene` were built in Stage 1 when only `fader`, `pan`, and `mute` existed in the UI, and were never expanded in Stage 2 to include `eq_low`, `eq_low_mid`, `eq_hi_mid`, `eq_hi`, `low_cut`, `compressor`, `send_mon1`, `send_mon2`, `send_fx1`, and `send_fx2`.
- **Impact:** A sound engineer who dials in full channel EQ, compression, high-pass filters, and monitor/FX sends and saves a Scene loses all DSP and monitor mix settings upon Scene Recall! Furthermore, scenes exist only in RAM and vanish when the app exits.
- **Reproduction Test:** `test_d04_scene_capture_includes_eq_dynamics_and_sends`
- **Recommended Fix:** Expand `REVERSIBLE_PARAMETERS` and `SceneManager.ALLOWED_PARAMETERS` to include all reversible channel DSP and send parameters (excluding `+48V` phantom power), and add JSON file persistence for scenes.

---

### [D-05] [P1] **[FIXED — Stage 1, offline-verified]** Disconnect / Reconnect Leaves Stale `▲ CMD` Provenance Badges & Undo History Active
- **Location:** `flow8/ledger.py:212-215` (`reconcile_connection`), `flow8/ui/app.py:314-332` (`_on_connection_result`), `flow8/ui/components/channel_detail.py:837-840` (`_refresh_eq_command`)
- **Category:** State Provenance Integrity
- **Description:**
  1. When `service.disconnect()` or `connect()` runs, `state_store.reconcile_reconnect()` resets all parameter provenances to `ParameterProvenance.UNSYNCED`, **but does not clear `commanded_raw_midi`**, and `ledger.reconcile_connection()` clears `self._redo` **but does not clear `self._undo`**.
  2. `Flow8App._on_connection_result` updates the Header and StatusBar, **but never triggers a refresh on `MixerConsole` or `ChannelDetailPanel`**, leaving `▲ CMD` badges displayed on screen while `StateStore` is `UNSYNCED`.
- **Impact:** Violates Stage 1 Requirement 3 ("Reconnection invalidates stale hardware state"). After unplugging and re-plugging the mixer, the UI still claims parameters are `▲ CMD` and allows undoing pre-disconnect history.
- **Reproduction Test:** `test_d05_disconnect_invalidates_open_inspector_provenance_badges`
- **Recommended Fix:** Clear `self._undo` in `CommandLedger.reconcile_connection()`, and invoke `mixer_console.inspector._refresh_if_attached()` and `mixer_console._refresh_history_buttons()` in `Flow8App._refresh_hardware_status()`.

---

### [D-06] [P1] All 8 Channel Strips Clip Horizontally at `1366×768` When Inspector Is Open (and at `1280×720` / `1024×768`)
- **Location:** `flow8/ui/components/mixer_console.py:279-286` (`midi_label_var`), `782-799` (`_inspector_width`)
- **Category:** Responsive Layout
- **Description:** At `1366×768`, opening the `320 px` `ChannelDetailPanel` shrinks the 8 channel strips to `100–106 px` each (`MIN_STRIP_SLOT = 104`), whereas each strip's `winfo_reqwidth()` is `132–142 px` (driven by `"MIDI 101/127 DEFAULT"` and `"Stereo Line / Hi-Z"`). At `1280×720`, `CommandLogPanel` shrinks to `37 px` (hiding the table). At `1024×768`, `SceneBar` and `UNDO`/`REDO` buttons overlap in the banner.
- **Impact:** Clipping of text labels across all 8 strips whenever the Inspector is open on a standard `1366×768` laptop screen.
- **Reproduction Test:** `test_d06_strips_not_clipped_at_1366x768_when_inspector_open`
- **Recommended Fix:** Shorten strip readout strings (e.g., `RAW 101 · UNSYNC`), collapse or remove the dead Left Navigation Rail, and make `CommandLogPanel` collapsible.

---

### [D-07] [P1] Preamp Gain Control Is Permanently Gated / Non-Operational in UI (`APPLY — GATED`)
- **Location:** `flow8/ui/safety_dialogs.py:323-356` (`AnalogGainSafetyGate`), `flow8/ui/components/channel_detail.py:552-560` (`gain_apply_btn`)
- **Category:** Core Mixer Functionality
- **Description:** Although `Flow8Service.set_gain` (CC 8, Ch 1–4) is implemented and allowlisted in `Flow8CommandBoundary`, `AnalogGainSafetyGate.is_verified_mapping_available()` is hardcoded to `return False` and `gain_apply_btn` is permanently `state="disabled"`.
- **Impact:** A sound engineer cannot adjust microphone/line preamp gain from the workstation during rehearsal or performance (Scenario B Step 4 fails).
- **Recommended Fix:** Allow raw MIDI (0–127) or confirmed staged gain dispatch through `Flow8Service.set_gain(ch, raw, unit="raw")` with an explicit confirmation gate similar to `+48V`, clearly labeling the dB readout as approximate.

---

### [D-08] [P1] Missing Bus Master Faders (`MON 1`, `MON 2`, `FX 1`, `FX 2`) & Missing `SOLO` (`CC 6`) in UI
- **Location:** `flow8/command_boundary.py:134-138`, `flow8/midi_constants.py:73`
- **Category:** Core Mixer Functionality
- **Description:** `mon1.fader` (Ch 9, CC 7), `mon2.fader` (Ch 10, CC 7), `fx1.fader` (Ch 11, CC 7), and `fx2.fader` (Ch 12, CC 7) are allowlisted in `Flow8CommandBoundary` and implemented in `Flow8ParameterEngine.set_bus_fader()`, but have no `Flow8Service` wrapper and no UI controls. Similarly, `CC_SOLO = 6` is defined in `midi_constants.py` and permitted in `Flow8MidiOut.send_cc`, but absent from `CommandBoundary`, `Service`, and `UI`.
- **Impact:** Users can adjust per-channel Monitor and FX sends in the Inspector, **but have no way to control the overall Monitor 1, Monitor 2, FX 1, or FX 2 master bus levels**, nor can they Solo a channel.

---

### [D-09] [P2] `Header`, `Navigation`, and `StatusBar` Call `grid_propagate(False)` Instead of `pack_propagate(False)`
- **Location:** `flow8/ui/components/header.py:30`, `flow8/ui/components/navigation.py:51`, `flow8/ui/components/status_bar.py:21`
- **Category:** Layout Implementation
- **Description:** All three widgets lay out their internal children using `.pack()`, but call `self.grid_propagate(False)` in `__init__`. Because `pack_propagate` remains `True`, `Navigation` shrinks from `232 px` to `113 px` and `StatusBar` shrinks from `36 px` to `20 px`.

---

### [D-10] [P2] Contradictory Left Navigation Rail (`Scenes — NOT IMPLEMENTED` vs Active `SceneBar`)
- **Location:** `flow8/ui/components/navigation.py:28-34`
- **Category:** UX Consistency / Space Efficiency
- **Description:** 4 of 5 items in the left Navigation Rail (`Routing`, `FX`, `Scenes`, `Recording`) are permanently disabled and stamped `NOT IMPLEMENTED` in orange, even though `SCENES 1..8 CAPTURE / RECALL` is active in the console banner and `list_fx_presets` exists in `Flow8Service`.

---

### [D-11] [P2] Compressor Slider Track (`UnipolarSlider`) Uses `maximum = 127` While Clamping Value at `100`
- **Location:** `flow8/ui/components/channel_detail.py:695-702` & `933`
- **Category:** Control Precision
- **Description:** `comp_slider` is an instance of `UnipolarSlider` whose `self.maximum` is `127`, while `_on_comp_drag` clamps `raw = max(0, min(100, int(val_str)))`. Dragging across the top 21% of the slider (`100..127`) produces no change (`100%`) and leaves the slider handle at `79%` of the visual track width.
- **Recommended Fix:** Set `self.comp_slider.maximum = 100`.

---

### [D-12] [P2] `Preserve Fader & Gain (Safe Mix)` Checkbox in `PresetPickerDialog` Is a No-Op
- **Location:** `flow8/ui/components/preset_picker.py:196-207`, `flow8/service.py:434-471`
- **Category:** UI Honesty
- **Description:** `apply_channel_preset(self, channel_index, preset_id, preserve_levels=True)` accepts `preserve_levels`, **but never reads or branches on `preserve_levels`** inside the method body (`ChannelPreset` only contains EQ, Low Cut, and Compressor fields). Checking or unchecking the box in `PresetPickerDialog` produces identical behavior.

---

### [D-13] [P3] Hard-Coded `("Segoe UI", ...)` Font Tuples Bypassing `theme.build_fonts()`
- **Location:** `flow8/ui/safety_dialogs.py:214, 224, 235, 249, 263` & `flow8/ui/components/controls.py:170, 293`
- **Category:** Theming Consistency
- **Description:** Uses literal `("Segoe UI", ...)` tuples instead of resolved tokens from `theme.build_fonts(root)`.

---

### [D-14] [P3] Uncancelled `after_idle` Lambda Callbacks Emit Tcl Warnings on Window Destruction
- **Location:** `flow8/ui/components/channel_detail.py:506` (`self.after_idle(self._refresh_if_attached)`), `flow8/ui/components/mixer_console.py:1037` (`self.after_idle(lambda: ...)`)
- **Category:** Lifecycle / Clean Shutdown
- **Description:** Neither `ChannelDetailPanel.destroy()` nor `MixerConsole.destroy()` stores and cancels pending `after_idle` callback IDs, producing `invalid command name "<id><lambda>"` messages on stderr when windows close rapidly during tests or shutdown.


---

## 3. Stage 1 Status (State Synchronisation & Integrity)

| ID | Status | Root cause (verified in code) | Fix |
|---|---|---|---|
| D-01 | **FIXED** (automated + visual, offline; NOT verified on physical hardware this stage) | `MixerConsole` never called `service.add_listener`, so `Flow8Service._on_midi_in_event` notifications reached no strip. | `MixerConsole._on_state_event` only enqueues on a `queue.SimpleQueue` (safe from the MIDI thread); a 25 ms Tk `after` poll drains it (`_drain_ui_queue`, newest value per parameter) and calls `ChannelStripWidget.sync_fader/sync_pan/sync_mute`. Those never dispatch: no outbound MIDI. A parameter with no telemetry keeps `UNSYNCED_DEFAULT`; a reported `0` is `OBSERVED`. |
| D-02 | **FIXED** | (1) `PresetPickerDialog` got no `on_applied`; (2) `_refresh_strips` skipped the inspector; (3) service never notified listeners after software-side bulk changes. | `on_applied` -> `ChannelDetailPanel._refresh_if_attached`; `_refresh_strips` also refreshes the inspector; `Flow8Service` emits `STATE_CHANGED_EVENT` after `apply_channel_preset`/`undo`/`redo`. Refresh updates existing Tk variables, no widget rebuild. |
| D-05 | **FIXED** (offline; real unplug/replug not exercised) | `reconcile_reconnect` reset provenance and observed values only; `commanded_*`/`raw_midi_value` and the undo stack survived; no UI was told. | Store clears `commanded_value/raw`, `raw_midi_value`; `CommandLedger.reconcile_connection` clears undo and redo; service emits `RECONCILE_EVENT`; console resets every strip to `UNSYNCED_DEFAULT`, refreshes inspector and UNDO/REDO buttons. |
| D-03, D-04, D-06..D-14 | **OPEN — out of Stage 1 scope** | — | Not touched. D-03, D-04, D-06 remain `expectedFailure` tests. |
