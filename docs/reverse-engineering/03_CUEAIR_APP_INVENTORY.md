# Phase 1: CueAir Application Inventory

**Target:** `CueAir.dmg` (Extracted `CueAir.app`)  
**Package Identifier:** `cc.cuetone.cueair`  
**Version:** `1.48` (Build `303`)  
**Date:** 2026-11-18  
**Integrity Digest:** SHA-256 `1D0F9E0DD87A38877204592FC08DC72E6AA76A62C76E85E98021B6A6CDEA41EC`  
**Extracted Size:** 108,165,596 bytes (1,006 files, 27 directories)

---

## 1. Filesystem & Container Layout

CueAir is distributed as an Apple Disk Image (`.dmg`) formatted with Apple File System (`APFS`).

```
CueAir.app/
├── Contents/
│   ├── Info.plist                     (Application metadata, permissions, URL schemes)
│   ├── embedded.provisionprofile      (Apple Developer provision profile)
│   ├── _CodeSignature/                (CodeResources, code signatures)
│   ├── MacOS/
│   │   ├── CueAir                     (Main executable, Universal Mach-O 64-bit, 40,058,640 bytes)
│   │   └── cueair-mcp                 (Embedded MCP server CLI, Universal Mach-O 64-bit, 11,883,456 bytes)
│   └── Resources/
│       ├── AppIcon.icns               (Application vector icons)
│       ├── CueAir_CueAir.bundle/      (UI icons, channel assets, fader caps, tab icons)
│       └── CueAir_XAirCore.bundle/    (Core mixer models, presets, FX definitions)
│           └── Contents/Resources/
│               ├── fx.json            (Global FX definitions)
│               └── presets/
│                   ├── cuetone-basic.cueairpreset  (50 curated channel strip presets + 8 trims)
│                   ├── cuetone-fx-xair.json        (Behringer X Air / XR18 FX starting points)
│                   ├── cuetone-fx-wing.json        (Behringer WING FX profiles)
│                   ├── cuetone-fx-ui.json          (Soundcraft Ui series FX profiles)
│                   ├── cuetone-fx-cq.json          (Allen & Heath CQ FX profiles)
│                   ├── cuetone-fx-tf.json          (Yamaha TF FX profiles)
│                   ├── cuetone-fx.json             (Generic DSP FX catalog)
│                   └── supporter-packs.json        (Tier/supporter features)
```

---

## 2. Binary Inventory

### 2.1 Main Executable: `CueAir`
- **Location:** `CueAir.app/Contents/MacOS/CueAir`
- **File Size:** 40,058,640 bytes (~38.2 MB)
- **Format:** Mach-O Universal Binary (FAT binary, magic `0xCAFEBABE`)
- **Slices:**
  - Slice 0: `x86_64` (Type: `0x1000007`), Offset: 16,384, Size: 20,607,296 bytes
  - Slice 1: `ARM64` (Type: `0x100000C`), Offset: 20,627,456, Size: 19,431,184 bytes
- **Minimum OS:** macOS 15.0 (Sequoia)
- **SDK:** macOS 15.x SDK, Swift 6.0 Toolchain

### 2.2 Embedded Agent Interface: `cueair-mcp`
- **Location:** `CueAir.app/Contents/MacOS/cueair-mcp`
- **File Size:** 11,883,456 bytes (~11.3 MB)
- **Format:** Mach-O Universal Binary (FAT binary, magic `0xCAFEBABE`)
- **Slices:**
  - Slice 0: `x86_64`, Offset: 16,384, Size: 6,190,464 bytes
  - Slice 1: `ARM64`, Offset: 6,209,536, Size: 5,673,920 bytes
- **Role:** Model Context Protocol (MCP) server providing LLM/agent-driven mixer introspection, parameter inspection, and remote automation over stdio/JSON-RPC.

---

## 3. Presets & DSP Data Assets

The bundled `CueAir_XAirCore.bundle` contains a rich library of digital audio engineering presets:
- **`cuetone-basic.cueairpreset`:** 3,153 lines of JSON with 50 specialized channel presets spanning vocalists, acoustic guitars, bass, drums, podcasts, and speeches. Each preset includes:
  - Exact 4-band Parametric EQ filter frequencies ($f$), gains ($g$), and Q factors ($q$).
  - Dynamic compressor thresholds, ratios, attack times, release times, and auto-makeup gain ($M_{\text{gain}}$).
  - Low cut / High-pass filter frequencies (HPF).
  - Engineering annotations explaining acoustic rationale (e.g. proximity effect filtering, vocal sibilance avoidance).
- **`cuetone-fx-xair.json`:** 779 lines defining Behringer XR/XAir FX algorithms (Room, Plate, Chamber, Hall, Vintage Reverb, Chorus, Flanger, Stereo Delay) with exact parameter starting points.
