# FLOW 8 Stage 2: Component Architecture
**Document ID:** STAGE2-ARCH-01  
**Project:** Behringer FLOW 8 Digital Mixer Workstation  
**Harness:** Antigravity Engineering Agent  
**Branch:** `stage2-mixer-workstation`  
**Status:** Implemented & Verified  

---

## 1. Architectural Overview & Design Pattern

The FLOW 8 workstation adheres strictly to a unidirectional, layered architecture:

```
+-------------------------------------------------------------------------+
|                         PRESENTATION LAYER                              |
|   MixerConsole         ChannelStripWidget         ChannelDetailPanel    |
|   - Strip Grid         - Fader, Pan, Mute         - [PREAMP & +48V]     |
|   - Scene Bar          - Live Provenance          - [4-BAND EQ]         |
|   - Undo / Redo Btns   - Readout Display          - [HPF & COMP]        |
|                                                   - [AUX SENDS]         |
+-------------------------------------------------------------------------+
                                    |
                           Invokes Public API
                                    v
+-------------------------------------------------------------------------+
|                         APPLICATION SERVICE                             |
|                           Flow8Service                                  |
|   - set_fader()        - set_eq_band()            - undo() / redo()     |
|   - set_pan()          - set_low_cut()            - capture_scene()     |
|   - set_mute()         - set_compressor()         - recall_scene()      |
|   - set_phantom()      - set_send()               - connect()           |
+-------------------------------------------------------------------------+
       |                                                |
       v                                                v
+-----------------------------+           +-------------------------------+
|       COMMAND LEDGER        |           |       PARAMETER ENGINE        |
|   - Exact-Value History     |           |   - Domain-Model Mapping      |
|   - Non-Undoable Defaults   |           |   - Unit Conversions (dB, Hz) |
|   - Compensating Rollback   |           |   - Channel Prefix Resolution |
+-----------------------------+           +-------------------------------+
                                                        |
                                                        v
                                          +-------------------------------+
                                          |       COMMAND BOUNDARY        |
                                          |   - Active Allowlist Gate     |
                                          |   - Range / Type Validation   |
                                          |   - Audit Logging             |
                                          +-------------------------------+
                                                        |
                                                        v
                                          +-------------------------------+
                                          |       WINMM MIDI OUT          |
                                          |   - midiOutShortMsg           |
                                          +-------------------------------+
```

---

## 2. Component Breakdown

### 2.1 `ChannelDetailPanel` (`flow8/ui/components/channel_detail.py`)
The right-hand docked inspector provides exhaustive control over the selected logical strip (1–7) or the Main L/R master bus.

#### A. Header & Preset Launcher
- Displays selected target name (`CHANNEL 01` .. `07` or `MAIN L/R`), logical role (`Mic 1`, `Line 3`, `USB / BT`), and hardware MIDI channel (`1` .. `8`).
- Preset launcher button (`★ ACOUSTIC PRESETS (CueAir)`): Opens `PresetPickerDialog` for input channels; disabled for Main L/R.
- Close button (`CLOSE ✕`): Clears active selection and closes inspector.

#### B. Tabbed Pro-Console Navigation Bar
To prevent visual clutter and guarantee zero-clipping on all supported screen sizes (including standard 1366×768 laptop screens), controls are grouped into four specialized tabs:
1. **`[PREAMP & +48V]`**:
   - `+48V PHANTOM POWER`: Available on MIC 1 and MIC 2 only. Protected by two-stage `PhantomPowerConfirmationDialog` token gate.
   - `ANALOG GAIN · PREVIEW ONLY`: Raw 0–127 slider with approximate dB readout. Dispatches are gated pending factory calibration curve.
2. **`[4-BAND EQ]`**:
   - 4-Band Parametric EQ with Low (80 Hz, CC 1), Low-Mid (400 Hz, CC 2), Hi-Mid (2.5 kHz, CC 3), and High (10 kHz, CC 4).
   - Sliders provide center detent at 64 (0.0 dB) across a -15.0 dB to +15.0 dB range.
   - "RESET FLAT (0 dB)" button dispatches neutral raw 64 to all 4 bands in a single batch.
   - Provenance badge indicates aggregated EQ status (`COMMANDED`, `OBSERVED`, `UNSYNCED`, `DISPATCH_FAILED`).
   - Disabled on Main L/R with explicit `— N/A` badge.
3. **`[HPF & COMP]`**:
   - `LOW CUT / HPF`: Channels 1–4 only. 20 Hz to 600 Hz (CC 9, raw 0–127). Includes `BYPASS (20 Hz)` button (raw 0).
   - `1-KNOB COMPRESSOR`: Channels 1–4 only. 0% to 100% intensity (CC 11, raw 0–100). Includes `BYPASS (0%)` button (raw 0).
   - Both sections display individual provenance badges and indicate `N/A — AVAILABLE ON CH 1–4 ONLY` on stereo channels.
4. **`[AUX SENDS]`**:
   - Aux Sends to Monitor 1 (CC 14), Monitor 2 (CC 15), FX 1 Reverb (CC 16), and FX 2 Delay (CC 17).
   - Each send features a unipolar slider (0–127) with decibel readout (-inf to +10 dB).
   - Provenance badge indicates aggregated send state. Disabled on Main L/R.

### 2.2 `MixerConsole` (`flow8/ui/components/mixer_console.py`)
Houses the 7 logical input channel strips, the Main L/R master strip, console header, and command log.

#### A. Banner Controls
- **History Controls:** Visual `↶ UNDO` and `↷ REDO` buttons dynamically enabled/disabled based on `service.ledger.can_undo` and `service.ledger.can_redo`. Keyboard accelerators (`Ctrl+Z`, `Ctrl+Y`, `Ctrl+Shift+Z`) remain synchronized.
- **Scene Snapshot Bar:** 8 snapshot slots with `CAPTURE` and `RECALL` workflows.
- **Telemetry Notice:** Clear indication of parameter status: `"UNSYNCED · COMMAND VALUES ONLY"`.

#### B. Channel Strip Widget (`ChannelStripWidget`)
- High-contrast strip header with channel index (`01` .. `07`, `MAIN`), input type badge (`XLR`, `COMBO`, `TRS`, `USB`, `MASTER`), and selection trigger.
- Pan/Balance horizontal slider (`HorizontalSlider`) with center detent at 64 (`C`, `L1` .. `L100`, `R1` .. `R100`).
- Mute toggle button (`MUTE` / `MUTED` in vibrant danger red).
- Fader readout displaying approximate dB (`+db.d dB` / `-inf`), raw MIDI value (`MIDI raw/127`), and provenance indicator.
- Vertical Volume Fader (`VerticalFader`) with calibrated dB scale ticks (+10, 0 Unity, -10, -20, -40, -inf).

### 2.3 Controls Library (`flow8/ui/components/controls.py`)
- `VerticalFader`: Smooth canvas-rendered vertical fader with double-click reset to Unity (raw 101 / 0 dB).
- `HorizontalSlider`: Canvas-rendered horizontal slider with physical center detent at raw 64 (0 dB / Center pan).
- `UnipolarSlider`: Canvas-rendered unipolar horizontal slider (0 to maximum) for sends, low cut, and compressor.
- `ProvenanceBadge`: Standardized 5-tier provenance status indicator:
  - `● OBS` (#26E07F Success Green): Confirmed physical hardware inbound telemetry.
  - `▲ CMD` (#FFB020 Warning Amber): Accepted software command dispatched to driver.
  - `○ UNSYNC` (#64748B Muted Gray): Default uncommanded software baseline.
  - `✕ FAIL` (#F43F5E Danger Red): Driver rejected or dispatch failed.
  - `— N/A` (#2E3646 Border Gray): Unsupported on this channel/target.
  - `⚠ WARN` (#F43F5E Danger Red): Divergent or uncertain state.
