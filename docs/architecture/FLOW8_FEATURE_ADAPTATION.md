# Phase 4: FLOW 8 Feature Adaptation Specification

**Document ID:** `FLOW8_FEATURE_ADAPTATION`  
**Goal:** Concrete technical specification for porting verified CueAir capabilities into the existing Python/Tkinter `flow8` application.

---

## 1. Feature 1: CueAir Preset Library Integration (`flow8/presets.py`)

### 1.1 Technical Design
- Create `flow8/presets.py` containing:
  1. A structured catalog of curated audio engineering presets derived from CueAir (`cuetone-basic.cueairpreset` and `cuetone-fx-xair.json`).
  2. Presets categorized into:
     - **Vocals:** Speech/Podcasting, MC Wireless Handheld, Male Lead Vocal, Female Lead Vocal, Worship Ballad, Rap/Punchy Vocal.
     - **Acoustic & String Instruments:** Acoustic Guitar Strum, Acoustic Guitar Fingerstyle, Electric Guitar Clean, Bass DI.
     - **Drums & Percussion:** Kick Punch, Snare Crack, Hi-Hat Sizzle, Overhead Cymbal Clean.
     - **FX Starting Points:** MC Room Reverb, Vocal Plate Reverb, Warm Hall Reverb, Slapback Echo, Stereo Delay.
- **Level Preservation Guarantee:**
  Every preset defines target DSP parameters (HPF, EQ Low, Low-Mid, Hi-Mid, Hi, Compressor). Fader level, Pan position, and Preamp gain are explicitly ignored to protect acoustic balance and prevent sudden loud audio spikes.

---

## 2. Feature 2: High-Level Preset Service Methods (`flow8/service.py`)

### 2.1 Technical Design
- Add to `Flow8Service`:
  - `list_presets(category: Optional[str] = None) -> List[PresetSummary]`
  - `get_preset(preset_id: str) -> Optional[Preset]`
  - `apply_preset(channel_index: int, preset_id: str, preserve_levels: bool = True) -> bool`
  - `apply_fx_preset(fx_slot: int, fx_preset_id: str) -> bool`
- **Safety Integration:**
  Before applying any multi-parameter preset, `Flow8Service` automatically calls `self.scenes.capture_snapshot(f"BEFORE_{preset_id.upper()}")` so the engineer can undo the entire preset application with a single click or with `Ctrl+Z`.

---

## 3. Feature 3: Preset Selector UI Component (`flow8/ui/components/preset_picker.py`)

### 3.1 Technical Design
- Implement a modern CyberNeon preset browser in `flow8/ui/components/preset_picker.py`:
  - Category filtering tabs: `All`, `Vocal`, `Speech`, `Acoustic`, `Drums`, `FX`.
  - Preset description card showing acoustic engineering notes (e.g., "Cuts boxiness at 250 Hz, tames proximity effect").
  - "Apply to Selected Channel" button with instant preview and Level Preservation toggle.
  - One-click "Undo Preset" fallback.

---

## 4. Feature 4: Interactive Channel EQ Visualizer Enhancement (`flow8/ui/components/channel_detail.py`)

### 4.1 Technical Design
- Render parametric frequency response curves in `ChannelDetail` using Tkinter vector canvas:
  - Low band ($f_1 \approx 80 \text{ Hz}$), Low-Mid ($f_2 \approx 250 \text{ Hz}$), High-Mid ($f_3 \approx 2.5 \text{ kHz}$), High ($f_4 \approx 10 \text{ kHz}$).
  - Live response curve drawn in neon cyan `#00F0FF` with smooth gradient fill.
  - Interactive knob controls for Gain, Low Cut, and Compressor.

---

## 5. Architectural Non-Regression Invariant
All existing 303 test cases must remain 100% green. The new preset engine, service methods, and UI components must be covered by thorough unit tests in `tests/test_presets.py` and `tests/test_preset_service.py`.
