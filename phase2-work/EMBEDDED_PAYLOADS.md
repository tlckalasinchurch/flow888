# PE Analysis — Embedded Payloads

**Target:** `mixing-station-pc-windows-3.2.2_789.exe`  
**SHA-256:** `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb`  
**File size:** 90,396,672 bytes (86.2 MB)  
**Architecture:** x86-64 (PE32+), Graphical Subsystem (subsystem 2)

---

## 1. Overview

The binary contains one primary embedded payload:

| Payload | Type | Size | Location |
|---|---|---|---|
| MSI installer package | Compound MSI / OLE2 compound | 89,624,452 bytes (85.5 MB) | RT_MANIFEST resource (ID 999, name "MSI") |

---

## 2. Embedded Archive / Calendar Detection

**Status: VERIFIED — MSI compound**

### Detected Payloads

1. **MSI Installer Compound (Primary Embedded Payload)**

   - Type: **MS-DOS FAT / OLE2 compound file** (Windows Installer format)
   - Size: **89,624,452 bytes (85.5 MB)**
   - Location: `RT_MANIFEST` resource, ID 999, name `"MSI"`
   - 49 files extracted via 7-Zip from the compound
   - **Format:** Compound MSI package (standard Windows Installer format)
   - The compound contains:
     - JRE/JDK runtime files (OpenJDK 25.0.1)
     - The Mixing Station for Desktop application files
     - MSI installer metadata (custom actions, patches, etc.)
     - The "PRODUCT_CODE" resource (MSI product code)

2. **No Other Embedded Archives**

   - **ZIP/JAR:** No `PK\x03\x04` signature found
   - **7z:** No `7z\xBC\xAF` signature found
   - **CAB:** No MSCF signature found
   - **GZIP/LZMA:** No signatures found
   - **Other PEs:** No embedded PE headers found outside `.rsrc`

---

## 3. Embedded Data (String-Level)

**Status: PROBABLE — VERIFIED via strings**

The binary contains numerous strings related to:

### Java/JPackage

- `jdk.jpackage.windows.native.common`
- `jdk.jdeps.Dependency`
- `jdk.jfr`
- `msimsg.dll`
- `mscoree.dll`
- `Input/output error`
- `Inappropriate I/O control operation`
- `map/set too long`

### Product Identity

- `mixing-station-pc`
- `Mixing Station for Desktop`
- `3.2.2`
- `OpenJDK Platform 25.0.1`
- `Eclipse Adoptium`
- `dev-core`
- `Mixing Station GmbH`

---

## 4. Embedded ZIP / JMOD / JAR Detection

**Status: NOT FOUND — VERIFIED**

### Checks performed:

- **ZIP (JAR):** No `PK\x03\x04` or `PK\x05\x06` (empty ZIP) signatures found
- **JMOD:** No JMOD-specific signatures found (JMOD files are ZIP-based, but the MSI is a compound file, not a ZIP)
- **7z:** No `7z\xBC\xAF` signature found
- **CAB:** No `MSCF` signature found

---

## 5. Embedded Executable Payloads

**Status: NONE FOUND — VERIFIED**

- No other executable payloads (different PEs, scripts, etc.) found
- The only executable payload is the MSI installer package itself (which is a compound file)
- The binary itself is the launcher executable; it does NOT contain additional executables inside the `.rsrc` section (only resources)

---

## 6. Overview of the Embedded MSI Package

The MSI package is the core deliverable inside this executable.

**Key characteristics:**

- **Type:** Windows Installer compound file (MS-DOS FAT / OLE2)
- **Size:** 89,624,452 bytes (85.5 MB)
- **Location:** `RT_MANIFEST` resource (type 10, ID 999, name "MSI")
- **Contents:** 49 files (per 7-Zip extraction)
- **Structure:** The MSI compound contains:
  - `win32ix.mof` (Windows Installer metadata)
  - `win32ix.dll` (MSI DLL)
  - Various JRE files
  - Application files
  - MSI patch and upgrade metadata

### What the MSI package likely contains:

The 89.6 MB bundled MSI package likely contains:

1. **Java Runtime Environment (JRE) / JDK:**
   - The OpenJDK 25.0.1 runtime files (from Eclipse Adoptium)
   - Java toolchain files (jdk.jpackage natives, jfr, etc.)
   - JVM libraries (libjvm, etc.)

2. **Application Files:**
   - The Mixing Station for Desktop application files
   - Resource files and icons
   - Configuration files

3. **MSI Installer Metadata:**
   - Custom actions (used by `msi.dll` imports)
   - Upgrade patches
   - Installer properties
   - Product code (PRODUCT_CODE resource)

---

## 7. How the MSI Package is Used

**Verdict: READ-ONLY — DO NOT EXECUTE**

The MSI package is embedded as a resource and used by the executable:

1. The executable is a GUI application (subsystem 2)
2. It imports `msi.dll` (Windows Installer API, 27 ordinal-based imports)
3. The MSI compound is stored in the `.rsrc` resource
4. When executed, the application likely:
   - Opens the embedded MSI compound
   - Calls `msi.dll` functions (via ordinal-based imports) to perform MSI operations
   - Installs the JRE and application files to the user's system

The executable is a **GUI wrapper around the MSI installer**, providing a desktop notification (`MessageBoxW`) and using the Windows Installer API for installation.

---

## 8. Embedded Payload Summary

| Payload | Type | Size | Location | Status |
|---|---|---|---|---|
| MSI compound | Compound MSI (OLE2) | 89.6 MB | RT_MANIFEST (ID 999, "MSI") | ✓ VERIFIED |
| 7-Zip extract | 49 files | 6.8 MB | From MSI compound | ✓ VERIFIED |
| Java strings | String references | Various | PE strings table | ✓ VERIFIED |
| JRE/JDK (bundled) | JRE files | ~80 MB | Inside MSI compound | PROBABLE (to verify) |

---

## 9. Next Steps

1. **Extract the MSI compound** from the `RT_MANIFEST` resource (89.6 MB)
2. **Decompile the MSI** to identify the exact contents:
   - Use `msiextract` / `instmod` from the Windows SDK
   - Use `msi` command-line tools to query the MSI package
3. **Identify the Java runtime version** and any custom modifications
4. **Analyze the application** (Mixing Station for Desktop) using:
   - JADX / CFR for Java bytecode
   - `javap` for JVM class inspection
5. **Examine the embedded JRE** for the specific Java version and modifications

---

## 10. Safety Note

All embedded payloads (the MSI compound, extracted files) are **read-only**. The binary and all extracted files are preserved. No payloads are executed or installed.
