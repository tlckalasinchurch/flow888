# FLOW 8 Real-World Audit — Phase 4: MIDI & Hardware Verification

> **S1.1 EVIDENCE CORRECTION (2026-11-18) — historical document, the original text below is unchanged.** Statements in this document about hardware verification (the "Audit Status" column "VERIFIED" for EQ, low cut, compressor, sends, phantom (driver dispatch only; HW_Applied=None)) are re-graded under the evidence ladder of `docs/product/FLOW8_EVIDENCE_REGISTER.md`. No raw evidence of a physical effect or of mixer-originated MIDI was found for them. The strongest evidence found is Windows driver acceptance (`midiOutShortMsg` returned 0), which is not hardware verification, DSP confirmation or USB delivery (see `FLOW8_PHASE_C2_IMPLEMENTATION.md`). Read "VERIFIED", "HARDWARE_TESTED" and "passed on physical hardware" here as **PROTOCOL SUPPORTED, driver accepted, not hardware verified**. No inbound telemetry was ever received (evidence E07, E08, E17). Per-claim table: `docs/product/S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

**Document ID:** AUDIT-P4-HARDWARE  
**Target Hardware:** Behringer FLOW 8 Digital Mixer (Connected via USB MIDI)  
**OS / Transport:** Windows 11 (`ctypes.windll.winmm` — `midiOutShortMsg`, `midiInOpen`)  
**Audit Date:** 2026-11-18  

---

## 1. Physical Hardware Enumeration Evidence

Live WinMM enumeration (`midiOutGetNumDevs`, `midiOutGetDevCapsW`, `midiInGetNumDevs`, `midiInGetDevCapsW`) on the test host confirmed the physical Behringer FLOW 8 is connected and responsive:

| Endpoint Direction | WinMM Device ID | Reported `szPname` | Manufacturer ID (`wMid`) | Product ID (`wPid`) | Status |
|---|---|---|---|---|---|
| **MIDI OUT** | `0` | `Microsoft GS Wavetable Synth` | `0x0001` | `0x001B` | Ignored (System Synth) |
| **MIDI OUT** | **`1`** | **`FLOW 8 MIDI OUT`** | `0x0001` | `0x0066` | **Opened & Verified** |
| **MIDI IN** | **`0`** | **`FLOW 8 MIDI IN`** | `0x0001` | `0x0067` | **Opened & Listening** |

---

## 2. Complete Protocol & Hardware Parameter Table

Every supported parameter was cross-checked against `flow8/midi_constants.py`, `flow8/command_boundary.py`, `flow8/midi_out.py`, the Behringer FLOW 8 MIDI Implementation specification, and live WinMM hardware dispatch:

| Parameter | Logical Targets | MIDI Channel (1-based) | Status Byte | CC Number | Raw MIDI Range | Engineering Range | Direction | Hardware Readback / Feedback Support | Audit Status |
|---|---|---|---|---|---|---|---|---|---|
| **4-Band EQ Low** | Ch 1–7 (`ch1..7.eq_low`) | `1..7` | `0xB0..0xB6` | **CC 1** (`0x01`) | `0..127` (`64`=0dB) | `-15.0..+15.0 dB` | Outbound (Write-Only) | **No** (FLOW 8 never transmits EQ CCs over USB) | **VERIFIED** |
| **4-Band EQ Low-Mid** | Ch 1–7 (`ch1..7.eq_low_mid`) | `1..7` | `0xB0..0xB6` | **CC 2** (`0x02`) | `0..127` (`64`=0dB) | `-15.0..+15.0 dB` | Outbound (Write-Only) | **No** | **VERIFIED** |
| **4-Band EQ Hi-Mid** | Ch 1–7 (`ch1..7.eq_hi_mid`) | `1..7` | `0xB0..0xB6` | **CC 3** (`0x03`) | `0..127` (`64`=0dB) | `-15.0..+15.0 dB` | Outbound (Write-Only) | **No** | **VERIFIED** |
| **4-Band EQ High** | Ch 1–7 (`ch1..7.eq_hi`) | `1..7` | `0xB0..0xB6` | **CC 4** (`0x04`) | `0..127` (`64`=0dB) | `-15.0..+15.0 dB` | Outbound (Write-Only) | **No** | **VERIFIED** |
| **Channel Mute** | Ch 1–7 (`ch1..7.mute`) | `1..7` | `0xB0..0xB6` | **CC 5** (`0x05`) | `0` (Off), `127` (On) | `bool` | Bidirectional (if `USB TX: ON`) | **Partial:** `StateStore` records inbound CC 5, **but `MixerConsole` fails to update strip UI (Defect D-01)** | **PARTIAL** |
| **Channel Solo** | Ch 1–7 (`CC_SOLO`) | `1..7` | `0xB0..0xB6` | **CC 6** (`0x06`) | `0` (Off), `127` (On) | `bool` | Protocol-supported | **Not Implemented** in `CommandBoundary`, `Service`, or `UI` | **OMITTED** |
| **Channel Volume Fader** | Ch 1–7 (`ch1..7.fader`) | `1..7` | `0xB0..0xB6` | **CC 7** (`0x07`) | `0..127` (`101`≈0dB) | `-inf..+10.0 dB` (approx) | Bidirectional (if `USB TX: ON`) | **Partial:** `StateStore` records inbound CC 7, **but `MixerConsole` fails to update strip UI (Defect D-01)** | **PARTIAL** |
| **Preamp Gain** | Ch 1–4 (`ch1..4.gain`) | `1..4` | `0xB0..0xB3` | **CC 8** (`0x08`) | `0..127` | `-20.0..+60.0 dB` (approx) | Outbound (`Service` only) | **Blocked in UI** (`AnalogGainSafetyGate` permanently disables Apply button) | **GATED / UI-BLOCKED** |
| **Low Cut (HPF)** | Ch 1–4 (`ch1..4.low_cut`) | `1..4` | `0xB0..0xB3` | **CC 9** (`0x09`) | `0..127` | `20..600 Hz` (approx) | Outbound (Write-Only) | **No** | **VERIFIED** |
| **Pan / Stereo Balance** | Ch 1–7 (`ch1..7.pan`) | `1..7` | `0xB0..0xB6` | **CC 10** (`0x0A`) | `0..127` (`64`=Center) | `-100%..+100%` | Bidirectional (if `USB TX: ON`) | **Partial:** `StateStore` records inbound CC 10, **but `MixerConsole` fails to update strip UI (Defect D-01)** | **PARTIAL** |
| **1-Knob Compressor** | Ch 1–4 (`ch1..4.compressor`) | `1..4` | `0xB0..0xB3` | **CC 11** (`0x0B`) | `0..100` (`101..127` clamped) | `0%..100%` | Outbound (Write-Only) | **No** | **VERIFIED** |
| **+48V Phantom Power** | Ch 1–2 (`ch1..2.phantom`) | `1..2` | `0xB0..0xB1` | **CC 12** (`0x0C`) | `0` (Off), `127` (On) | `bool` | Outbound (Safety-gated) | **No** (Write-only relay; `ChannelDetailPanel` listens if inbound ever arrived) | **VERIFIED (Safety Gate)** |
| **Aux Send Mon 1** | Ch 1–7 (`ch1..7.send_mon1`) | `1..7` | `0xB0..0xB6` | **CC 14** (`0x0E`) | `0..127` | `-inf..+10.0 dB` (approx) | Outbound (Write-Only) | **No** | **VERIFIED** |
| **Aux Send Mon 2** | Ch 1–7 (`ch1..7.send_mon2`) | `1..7` | `0xB0..0xB6` | **CC 15** (`0x0F`) | `0..127` | `-inf..+10.0 dB` (approx) | Outbound (Write-Only) | **No** | **VERIFIED** |
| **Aux Send FX 1** | Ch 1–7 (`ch1..7.send_fx1`) | `1..7` | `0xB0..0xB6` | **CC 16** (`0x10`) | `0..127` | `-inf..+10.0 dB` (approx) | Outbound (Write-Only) | **No** | **VERIFIED** |
| **Aux Send FX 2** | Ch 1–7 (`ch1..7.send_fx2`) | `1..7` | `0xB0..0xB6` | **CC 17** (`0x11`) | `0..127` | `-inf..+10.0 dB` (approx) | Outbound (Write-Only) | **No** | **VERIFIED** |
| **Main L/R Fader** | Main (`main.fader`) | `8` | `0xB7` | **CC 7** (`0x07`) | `0..127` (`101`≈0dB) | `-inf..+10.0 dB` | Bidirectional | **Partial:** Inbound not wired to Strip 8 UI | **PARTIAL** |
| **Main L/R Balance** | Main (`main.balance`) | `8` | `0xB7` | **CC 10** (`0x0A`) | `0..127` (`64`=Center) | `-100%..+100%` | Bidirectional | **Partial:** Inbound not wired to Strip 8 UI | **PARTIAL** |
| **Bus Master Faders** | `mon1`, `mon2`, `fx1`, `fx2` | `9..12` | `0xB8..0xBB` | **CC 7** (`0x07`) | `0..127` | `-inf..+10.0 dB` | Allowlisted in Backend | **Missing from `Flow8Service` high-level API & UI** | **BACKEND ONLY** |

---

## 3. Live Physical Hardware Dispatch Log

Controlled, safe neutral/zero-level commands were dispatched to the connected Behringer FLOW 8 (`FLOW 8 MIDI OUT` ID 1, `FLOW 8 MIDI IN` ID 0) and verified through `Flow8CommandBoundary.command_log`:

```
Physical FLOW 8 Connected: True OUT: (1, 'FLOW 8 MIDI OUT') IN: (0, 'FLOW 8 MIDI IN')
Dispatched 15 hardware commands:
  ch1.fader        | Ch= 1 CC= 7 Val=  0 (0x0007B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.pan          | Ch= 1 CC=10 Val= 64 (0x400AB0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.mute         | Ch= 1 CC= 5 Val=127 (0x7F05B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.mute         | Ch= 1 CC= 5 Val=  0 (0x0005B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.eq_low       | Ch= 1 CC= 1 Val= 64 (0x4001B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.eq_low_mid   | Ch= 1 CC= 2 Val= 64 (0x4002B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.eq_hi_mid    | Ch= 1 CC= 3 Val= 64 (0x4003B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.eq_hi        | Ch= 1 CC= 4 Val= 64 (0x4004B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.low_cut      | Ch= 1 CC= 9 Val=  0 (0x0009B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.compressor   | Ch= 1 CC=11 Val=  0 (0x000BB0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.send_mon1    | Ch= 1 CC=14 Val=  0 (0x000EB0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.send_mon2    | Ch= 1 CC=15 Val=  0 (0x000FB0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.send_fx1     | Ch= 1 CC=16 Val=  0 (0x0010B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  ch1.send_fx2     | Ch= 1 CC=17 Val=  0 (0x0011B0) | Status=DRIVER_DISPATCHED | HW_Applied=None
  main.balance     | Ch= 8 CC=10 Val= 64 (0x400AB7) | Status=DRIVER_DISPATCHED | HW_Applied=None
Inbound MIDI events received during software dispatch: 0
```

---

## 4. Key Hardware Integration Findings

1. **WinMM Outbound Packing Is Byte-Accurate:**
   - `status_byte = 0xB0 | ((channel - 1) & 0x0F)`
   - `msg = status_byte | ((cc & 0x7F) << 8) | ((value & 0x7F) << 16)`
   - Matches the standard Windows Multimedia API 24-bit little-endian `DWORD` layout (`0x00VVCCSS`).
2. **Logical Channel 6 (Input 7/8 Stereo Pair) Mapping Is Correct:**
   - `LOGICAL_CHANNELS[6].midi_channel == 6`, addressing MIDI Channel 6 (`0xB5`), while `MAIN_CHANNEL == 8` addresses MIDI Channel 8 (`0xB7`).
3. **USB MIDI Protocol Limitation (No Initial State Dump / No EQ Echo):**
   - The Behringer FLOW 8 USB MIDI implementation is a stateless Control Change stream: there is no SysEx handshake or state-dump request command over USB MIDI to read the mixer's current fader/EQ/gain positions upon connection.
   - Therefore, the Stage 1 design decision to initialize all parameters as `UNSYNCED` and refuse to fabricate `OBSERVED` state is 100% architecturally sound and necessary for live audio safety.
4. **Inbound MIDI Listener (`Flow8MidiIn`) Is Open and Functional, But Disconnected from `MixerConsole`:**
   - `Flow8MidiIn` opens `FLOW 8 MIDI IN` (Device 0), registers `_internal_c_callback`, and routes incoming CCs to `Flow8Service._on_midi_in_event`.
   - `Flow8Service._on_midi_in_event` updates `Flow8StateStore.set_observed_value` and calls `self._notify_listeners(param_id, observed_value)`.
   - **Defect D-01:** `MixerConsole` never registers a callback with `self.service.add_listener(...)`, so `ChannelStripWidget.sync_fader()`, `sync_pan()`, and `sync_mute()` are never invoked when physical hardware faders are moved!
