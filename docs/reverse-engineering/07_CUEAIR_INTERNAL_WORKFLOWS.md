# Phase 2: CueAir Internal Workflows

**Document ID:** `07_CUEAIR_INTERNAL_WORKFLOWS`  
**Target:** `CueAir.app` & `cueair-mcp`  
**Status:** RECONSTRUCTED & VERIFIED

---

## 1. Trace: User Action to Hardware Interaction

For each core feature, the complete causal chain from UI event to hardware transmission is detailed below:

### Workflow 1: Dynamic Fader Movement
```
[USER ACTION]         User drags Channel 1 virtual fader to -10 dB.
  ↓
[UI EVENT]           `Slider.onDrag` in SwiftUI / Canvas.
  ↓
[FUNCTION]           `MixerController.setChannelFader(channelId: 1, db: -10.0)`
  ↓
[INTERNAL PROCESSING]1. Clamps value between -inf and +10 dB.
                     2. Converts dB to normalized float [0.0..1.0] using non-linear audio taper.
                     3. Updates cached channel state in `MixerStateModel`.
  ↓
[STATE CHANGE]       Channel 1 dirty flag raised; UI repaints fader cap and level label.
  ↓
[OUTPUT]             Framer encodes OSC message: `/ch/01/mix/fader` with float payload.
  ↓
[HARDWARE INTERACT]  Transmitted over UDP socket to mixer IP:10023.
```

### Workflow 2: Audio Engineering Preset Recall
```
[USER ACTION]         User taps "Vocal Ballad" in Preset Picker.
  ↓
[UI EVENT]           `PresetButton.onClick` emits preset identifier `vocal-ballad`.
  ↓
[FUNCTION]           `PresetEngine.applyChannelPreset(channel: 1, presetId: 'vocal-ballad')`
  ↓
[INTERNAL PROCESSING]1. Executes auto-snapshot of current state: `SceneManager.quickSave('BEFORE_PRESET')`.
                     2. Loads preset values from `cuetone-basic.cueairpreset`.
                     3. Executes level-protection filter:
                        `filtered_values = {k: v for k, v in preset.items() if k not in ['gain', 'fader', 'pan']}`
                     4. Converts human engineering units:
                        - Low cut: 100 Hz
                        - EQ 1: 180 Hz, -2 dB, Q 1.2
                        - EQ 2: 1.2 kHz, +1.5 dB, Q 2.0
                        - EQ 3: 4.5 kHz, +2.0 dB, Q 1.5
                        - EQ 4: 10.0 kHz, +1.0 dB, Q 0.7
                        - Compressor: Thr -18 dB, Ratio 2.5:1, Attack 15ms, Release 200ms
  ↓
[STATE CHANGE]       In-memory `ChannelState[1]` updated with new DSP parameters.
  ↓
[OUTPUT]             Emits bundle of parameter commands.
  ↓
[HARDWARE INTERACT]  Mixer DSP executes EQ/Dynamics updates seamlessly without audio dropout.
```

### Workflow 3: +48V Phantom Power Toggle (Safety Critical)
```
[USER ACTION]         User clicks "+48V" button on Mic 1.
  ↓
[UI EVENT]           Button click triggers warning interceptor.
  ↓
[FUNCTION]           `SafetyDialogs.promptPhantomPowerConfirmation(channel: 1)`
  ↓
[INTERNAL PROCESSING]1. Modal dialog displayed: "WARNING: +48V Phantom Power can damage unbalanced ribbon mics or line-level equipment. Ensure microphone is connected and compatible."
                     2. User clicks "Confirm / Enable +48V".
  ↓
[STATE CHANGE]       `ChannelState[1].phantom_power = True`.
  ↓
[OUTPUT]             Encodes hardware power toggle message.
  ↓
[HARDWARE INTERACT]  Mixer relay energizes +48V rail on Input 1.
```

### Workflow 4: Multi-Step Undo / Redo
```
[USER ACTION]         User presses Ctrl+Z (or Cmd+Z on macOS).
  ↓
[UI EVENT]           Window keydown handler calls `HistoryController.undo()`.
  ↓
[FUNCTION]           `CommandLedger.popUndo()`
  ↓
[INTERNAL PROCESSING]1. Retrieves top record from undo stack (e.g. `FaderChange(ch=2, old=-15.0, new=-6.0)`).
                     2. Generates inverse command with `old` value (-15.0 dB).
                     3. Pushes forward command to redo stack.
  ↓
[STATE CHANGE]       `ChannelState[2].fader = -15.0 dB`.
  ↓
[OUTPUT]             Encodes mixer parameter update.
  ↓
[HARDWARE INTERACT]  Mixer fader returns to exact previous position.
```
