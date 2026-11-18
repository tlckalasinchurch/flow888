# FLOW 8 Real-World Audit — Phase 5: State & Data Integrity Audit

**Document ID:** AUDIT-P5-STATE  
**Target Branch:** `stage2-mixer-workstation` (`456fd5a`)  
**Modules Audited:** `flow8/state_model.py`, `flow8/ledger.py`, `flow8/service.py`, `flow8/scenes.py`, `flow8/presets.py`, `flow8/ui/components/channel_detail.py`, `flow8/ui/components/mixer_console.py`  

---

## 1. Stage 1 Ten-Point Provenance & Undo Integrity Verification

We audited each of the 10 mandatory state integrity rules against both backend (`Flow8StateStore`, `CommandLedger`, `Flow8Service`) and frontend (`MixerConsole`, `ChannelDetailPanel`) execution paths:

| # | Integrity Requirement | Backend Verdict | UI Verdict | Evidence & Findings |
|---|---|---|---|---|
| **1** | **`COMMANDED` is never presented as `OBSERVED`** | **PASS** | **PASS** | `set_commanded_value` sets `provenance = ParameterProvenance.COMMANDED` (`▲ CMD` in amber). Only `set_observed_value` (called exclusively from `_on_midi_in_event`) sets `provenance = ParameterProvenance.OBSERVED` (`● OBS` in green). |
| **2** | **Missing telemetry is never fabricated** | **PASS** | **PASS** | `hardware_applied` in `CommandLogEntry` is hardcoded to `None` (`UNKNOWN` in `CommandLogPanel`). Write-only parameters (EQ, HPF, Comp, Sends, Gain, +48V) never set `observed_value`. |
| **3** | **Reconnection invalidates stale hardware state** | **PARTIAL** | **FAIL (D-05)** | **Backend:** `service.reconcile_connection()` resets all `ParameterState.provenance` to `UNSYNCED` and clears `observed_value` and `ledger._redo`, **but leaves `ledger._undo` populated (`can_undo == True`)** even though all parameters are now `UNSYNCED`! <br>**UI:** `Flow8App._on_connection_result` does not refresh `ChannelDetailPanel` or `MixerConsole`, leaving `▲ CMD` badges displayed after disconnect/reconnect! |
| **4** | **Unsupported parameters cannot be operated** | **PASS** | **PASS** | `Flow8CommandBoundary.ACTIVE_ALLOWLIST` rejects unsupported parameters (`Flow8CommandRejectedError`). `ChannelDetailPanel` hides EQ/Sends on Main L/R, hides HPF/Comp on Ch 5–8, and disables `+48V` on Ch 3–8 with `— N/A` badges. |
| **5** | **Failed commands do not appear successful** | **PASS** | **PASS** | When `midi_out.send_cc` raises `Flow8MidiError`, `CommandBoundary.execute_command` calls `state_store.set_dispatch_failed(param_id)` (`provenance = DISPATCH_FAILED`, `✕ FAIL`), does not commit `commanded_value`, and `ChannelStripWidget` rolls back the slider to `_last_fader_val` / `_last_pan_val`. |
| **6** | **State uncertainty is visible** | **PASS** | **PARTIAL (D-06)** | Inspector and Command Log show `UNSYNCED` / `UNKNOWN`, **but** individual `ChannelStripWidget` strips lose their `DEFAULT` label after the first fader move (showing only `MIDI 80/127`) and never instantiate `self.fader_badge`. |
| **7** | **UI refresh does not send duplicate MIDI commands** | **PASS** | **PASS** | `_BaseControl` in `controls.py` only invokes `self.command` on user input events (`_on_pointer`, `_on_reset`, `_on_wheel`, `_on_key`), never on `variable.set()`. Furthermore, `ChannelStripWidget._is_updating` and `ChannelDetailPanel._is_updating_controls` guard programmatic updates. Selecting channels or switching tabs sends **0 MIDI messages**. |
| **8** | **Undo / Redo uses valid historical state** | **PASS** | **FAIL (D-02)** | **Backend:** `CommandLedger` replays exact `previous_value` in reverse chronological order on `undo()` and `new_value` in forward order on `redo()`. <br>**UI:** `MixerConsole._run_history` only calls `self._refresh_strips()`, **failing to refresh `self.inspector` (`ChannelDetailPanel`)**! Thus undoing an EQ, HPF, Compressor, Send, or Preset change updates the hardware and `StateStore`, while the open Inspector UI shows stale values! |
| **9** | **Unknown baseline does not produce fabricated undo values** | **PASS** | **PASS** | `Flow8Service._known_value` returns `None` when `state.provenance == ParameterProvenance.UNSYNCED`. `CommandRecord.undoable` is `False` when `previous_value is None`. The first write to an uncommanded parameter establishes the baseline without pushing a fake default undo record. |
| **10** | **Failed rollback is explicitly reported** | **PASS** | **PASS** | In `CommandLedger.undo()` / `redo()` (`ledger.py:152-166`), if a multi-record transaction fails mid-flight and compensating rollback also fails, it raises `RuntimeError("... Rollback compensation also failed; mixer in indeterminate state.")`, which `MixerConsole._run_history` surfaces in the Status Bar and Command Log. |

---

## 2. Preset & Scene Operations Audit

### 2.1 Channel Presets (`flow8/presets.py`, `flow8/ui/components/preset_picker.py`)

| Operation | Supported? | Execution & Integrity Audit | Defects Found |
|---|---|---|---|
| **List / Filter / Inspect** | **Yes** | 10 curated CueAir-adapted presets across 6 categories (`Speech`, `Vocal`, `Acoustic`, `Bass`, `Drums`, `Utility`). Displays exact EQ dB, Low Cut Hz, Compressor %, and acoustic rationale. | None. |
| **Apply / Load Preset** | **Yes** | `service.apply_channel_preset(ch, preset_id)` wraps all 4 EQ bands + Low Cut (Ch 1–4) + Compressor (Ch 1–4) inside `begin_batch()` / `end_batch()` as a single atomic ledger transaction. | **Defect D-02 (P1):** Applying a preset in `PresetPickerDialog` does not refresh the open `ChannelDetailPanel` behind it (`ChannelDetailPanel._on_open_presets` never passes `on_applied` to `PresetPickerDialog`, and `Flow8Service` never calls `_notify_listeners` on outbound writes).<br>**Defect D-07 (P2):** `Preserve Fader & Gain (Safe Mix)` checkbox has no effect because `ChannelPreset` has no fader/gain fields and `preserve_levels` is unused in `apply_channel_preset`. |
| **Save / Update / Delete Custom Preset** | **No** | Presets are read-only static dataclasses in `flow8/presets.py` (`CHANNEL_PRESETS`). Users cannot save, update, or delete custom channel presets. | Feature limitation (static preset library only). |
| **Undo / Redo Preset Application** | **Yes** | If EQ/HPF/Comp had a known commanded baseline prior to applying the preset, `service.undo()` restores all 6 parameters in reverse order in one step. | Backend passes; Inspector UI does not refresh on Undo (Defect D-02). |

---

### 2.2 Scene Snapshots (`flow8/scenes.py`, `flow8/ui/components/scene_bar.py`)

| Operation | Supported? | Execution & Integrity Audit | Defects Found |
|---|---|---|---|
| **Capture (Save) Scene (`SCENE 1..8`)** | **Partial** | `Flow8Service.capture_scene` iterates channels `1..8` and captures known (`COMMANDED` or `OBSERVED`) parameters into `SceneManager`. Rejects capture with `SCENE CAPTURE REJECTED — NO KNOWN PARAMETERS` if nothing has been commanded/observed yet. Never captures `+48V`. | **Defect D-04 (P1 — Critical Mix Loss):** `REVERSIBLE_PARAMETERS` (`service.py:38`) and `SceneManager.ALLOWED_PARAMETERS` (`scenes.py:25`) are hardcoded to `("fader", "pan", "mute")`! **Capturing a scene completely discards all 4-Band EQ, Low Cut HPF, Compressor, and Aux Send (`mon1`, `mon2`, `fx1`, `fx2`) settings!**<br>**Defect D-08 (P2):** Scenes are stored only in RAM (`self._snapshots = {}`) and are wiped when the application closes. |
| **Overwrite (Update) Scene** | **Yes** | Capturing into an already-populated slot overwrites it and reports `SCENE OVERWRITTEN — SCENE X · N VALUES`. | No confirmation prompt before overwriting an existing scene slot during live performance. |
| **Recall (Load) Scene** | **Partial** | `Flow8Service.recall_scene` replays stored `fader`, `pan`, `mute` values inside `begin_batch()` / `end_batch()` and refreshes channel strips. Reports partial failures (`X SENT · Y NOT SENT`) if any command fails. | Only recalls `fader`, `pan`, `mute` (ignores EQ, HPF, Comp, Sends — Defect D-04). |
| **Delete Scene** | **Backend Only** | `SceneManager.delete_snapshot(name)` exists in `flow8/scenes.py:65`, **but there is no UI button or context menu in `SceneBar` to clear/delete a scene slot.** | Missing UI action. |
| **Undo / Redo Scene Recall** | **Yes** | Recalling a scene over previously commanded channels pushes 1 coalesced transaction to `CommandLedger`; `undo()` restores all affected strips in 1 step. | Verified working for `fader`, `pan`, `mute`. |
