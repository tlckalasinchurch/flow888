# FLOW 8 Hardware Verification Report
**Target:** Behringer FLOW 8 Digital Mixer  
**Phase:** Phase 0.5 — Hardware & Protocol Verification  
**Date:** 2026-11-09  
**Status:** VERIFIED (USB Hardware Connected & Active)  

---

## 1. Executive Hardware Detection Summary

Direct Plug and Play (PnP), Windows Multimedia (WinMM), and driver store interrogation confirmed that the **Behringer FLOW 8 physical hardware is currently connected, powered on, and operational** on this Windows workstation via USB.

| Hardware Metric | Verified Specification / Value | Status |
|---|---|---|
| **Device Presence** | Physical USB Device Present & Active (`Present: True`, `Status: OK`) | VERIFIED |
| **Vendor ID (VID)** | `0x1397` (Behringer / Music Tribe) | VERIFIED |
| **Product ID (PID)** | `0x050C` (FLOW 8 in **Recording Mode**) | VERIFIED |
| **Device Instance ID** | `USB\VID_1397&PID_050C\70-B9-50-66-4D-68` | VERIFIED |
| **Unique Hardware Identifier** | `70-B9-50-66-4D-68` (Hardware MAC / EUI-48 identifier) | VERIFIED |
| **Active Mode** | **Recording Mode** (10 In / 4 Out multi-channel audio topology) | VERIFIED |
| **Streaming Mode ID** | `VID_1397&PID_050D` (`Present: False` — inactive while in Recording Mode) | VERIFIED |
| **Driver Package** | `BEHRINGER FLOW USB Audio Driver v5.72.0` (Thesycon class driver) | VERIFIED |
| **Driver Location** | `C:\Program Files\BEHRINGER\FLOW-USB_Audio_Driver\` | VERIFIED |
| **Connection Errors** | None observed; all endpoints report `Status: OK` | VERIFIED |

---

## 2. Windows Plug and Play Device Hierarchy

PnP entity interrogation via PowerShell `Get-PnpDevice` established the following live device tree:

```mermaid
flowchart TD
    USB["USB Root Hub 3.0 (Intel eXtensible Host Controller)"] --> Hub["Generic USB Hub (VID_1A40&PID_0101)"]
    Hub --> F8["Behringer FLOW 8 Hardware<br/>USB\VID_1397&PID_050C\70-B9-50-66-4D-68<br/>[Status: OK | Present: True]"]
    
    F8 --> AudioDrv["TUSBAUDIO Driver: flow-usb_audio.sys<br/>BEHRINGER FLOW 8 (Recording)"]
    F8 --> MidiSub["USB MIDI Subdevice (MI_03 / MI_04)"]
    
    MidiSub --> MidiIn["FLOW 8 MIDI IN [0]<br/>SWD\MMDEVAPI\MIDII_741EBCB3.P_0001<br/>[Status: OK | Present: True]"]
    MidiSub --> MidiOut["FLOW 8 MIDI OUT [0]<br/>SWD\MMDEVAPI\MIDII_230BE120.P_0000<br/>[Status: OK | Present: True]"]

    AudioDrv --> MultiIn["Multi In 1-10 (Channels 1-10)"]
    AudioDrv --> Mic1["Mic 1 (Ch 1)"]
    AudioDrv --> Mic2["Mic 2 (Ch 2)"]
    AudioDrv --> Mic3["Mic/Line 3 (Ch 3)"]
    AudioDrv --> Mic4["Mic/Line 4 (Ch 4)"]
    AudioDrv --> Line56["Line 5/6 (Ch 5-6)"]
    AudioDrv --> Line78["Line 7/8 (Ch 7-8)"]
    AudioDrv --> MainRec["Main L/R (Ch 9-10)"]
    AudioDrv --> UsbOut12["USB Out 1/2 (Playback Ch 1-2)"]
    AudioDrv --> UsbOut34["USB Out 3/4 (Playback Ch 3-4)"]
```

---

## 3. USB MIDI Endpoint Inspection

Inspection of Windows Multimedia (`winmm.dll`) device enumeration verified that the MIDI endpoints are active, exposed to the OS, and ready for communication:

### 3.1 MIDI In Device Table
- **Device Count:** 1
- **Device Index:** `0`
- **Device Name:** `FLOW 8 MIDI IN`
- **PnP Instance ID:** `SWD\MMDEVAPI\MIDII_741EBCB3.P_0001`
- **Status:** `OK` (`Present: True`)
- **Driver Provider:** Microsoft MMDEVAPI / Thesycon USB MIDI
- **Confidence:** VERIFIED

### 3.2 MIDI Out Device Table
- **Device Count:** 2 (Device 0: `Microsoft GS Wavetable Synth`, Device 1: `FLOW 8 MIDI OUT`)
- **Device Index:** `1`
- **Device Name:** `FLOW 8 MIDI OUT`
- **PnP Instance ID:** `SWD\MMDEVAPI\MIDII_230BE120.P_0000`
- **Status:** `OK` (`Present: True`)
- **Driver Provider:** Microsoft MMDEVAPI / Thesycon USB MIDI
- **Confidence:** VERIFIED

---

## 4. USB Audio Endpoint Inspection (WASAPI & ASIO)

All 8 recording endpoints and 2 playback endpoints defined in the driver profile are currently instantiated and active in the Windows Audio Endpoint subsystem:

### 4.1 Playback Endpoints (Host to Mixer)
| Endpoint Name | Channels | Pin Index | Windows Device ID | Status |
|---|---|---|---|---|
| **USB Out 1/2** | 2 | Ch 0, 1 | `SWD\MMDEVAPI\{0.0.0.00000000}.{545C9DCC-1DF6-46CF-AE1D-FBA203FC8682}` | OK / True |
| **USB Out 3/4** | 2 | Ch 2, 3 | `SWD\MMDEVAPI\{0.0.0.00000000}.{D4BC27A5-CA4D-4D81-BAF7-2D59E323C1C6}` | OK / True |

### 4.2 Recording Endpoints (Mixer to Host)
| Endpoint Name | Channels | Pin Index | Windows Device ID | Status |
|---|---|---|---|---|
| **Mic 1** | 1 (Mono) | Ch 0 | `SWD\MMDEVAPI\{0.0.1.00000000}.{D5F2678B-FF5B-4DC3-9BD4-0988CD87E0A0}` | OK / True |
| **Mic 2** | 1 (Mono) | Ch 1 | `SWD\MMDEVAPI\{0.0.1.00000000}.{2336D778-FB80-4787-9EC4-DBB7BFEACBEF}` | OK / True |
| **Mic/Line 3** | 1 (Mono) | Ch 2 | `SWD\MMDEVAPI\{0.0.1.00000000}.{61869519-F113-4C38-8DD8-1B811E906B49}` | OK / True |
| **Mic/Line 4** | 1 (Mono) | Ch 3 | `SWD\MMDEVAPI\{0.0.1.00000000}.{E14E022C-F94F-4A60-8E7F-7B7931755A56}` | OK / True |
| **Line 5/6** | 2 (Stereo) | Ch 4, 5 | `SWD\MMDEVAPI\{0.0.1.00000000}.{F919ACB1-0B1D-4F88-9625-FD85661A4E5D}` | OK / True |
| **Line 7/8** | 2 (Stereo) | Ch 6, 7 | `SWD\MMDEVAPI\{0.0.1.00000000}.{6363A233-45EE-477D-BF1F-9A08D062CCBA}` | OK / True |
| **Main L/R** | 2 (Stereo) | Ch 8, 9 | `SWD\MMDEVAPI\{0.0.1.00000000}.{E720520E-87D6-431A-858E-FD1811975931}` | OK / True |
| **Multi In 1-10** | 10 (Multi) | Ch 0-9 | `SWD\MMDEVAPI\{0.0.1.00000000}.{648AE5F5-1AF5-484B-A12C-CEFDB026EB9D}` | OK / True |

---

## 5. Driver Package Verification

- **Driver Title:** `BEHRINGER FLOW USB Audio Driver v5.72.0`
- **Vendor:** Thesycon Systemsoftware GmbH for Behringer / Music Tribe
- **Release Version:** `5.72.0` (December 2024 build)
- **Installer GUID:** `{0CCD546B-62EF-49B0-B51C-7F1D43E25C9C}`
- **Kernel Drivers:**
  - `flow-usb_audio.sys` (434,328 bytes) — Core USB Audio Class 2.0 driver
  - `flow-usb_audioks.sys` (55,448 bytes) — Kernel Streaming audio sub-layer
- **User-Mode APIs & ASIO:**
  - `flow-usb_audioasio_x64.dll` (277,896 bytes) — 64-bit ASIO driver implementation
  - `flow-usb_audioapi_x64.dll` (322,952 bytes) — Driver control & query API
  - `FlowAudioCplApp.exe` (663,432 bytes) — Native driver control panel
- **Confidence:** VERIFIED
