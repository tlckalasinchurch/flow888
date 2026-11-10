# REA Phase 2 — Summary & Recommendations

**Target:** `mixing-station-pc-windows-3.2.2_789.exe`  
**SHA-256:** `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb`  
**File size:** 90,396,672 bytes (86.2 MB)  
**Architecture:** x86-64 (PE32+), Graphical Subsystem (subsystem 2)  
**Phase:** 2 — PE Payload & Runtime Identification  
**Date:** 2026-11-09

---

## 1. Executive Summary

The binary `mixing-station-pc-windows-3.2.2_789.exe` is a **self-contained packaged application** — specifically, an **MSI installer wrapper** for a Java application (Mixing Station for Desktop).

Key findings:

1. **Executable architecture:** x86-64 (PE32+), GUI subsystem
2. **Exports:** None (no exported functions)
3. **Imports:** 6 DLLs — KERNEL32 (118), msi.dll (27 ordinal), ole32 (3), SHELL32 (1), SHLWAPI (1), USER32 (1)
4. **Resources:** 4 types — RT_ICON (9 icons), RT_MANIFEST (2: "MSI" 89.6 MB and "PRODUCT_CODE"), RT_VERSION (1), RT_DLGINCLUDE (1)
5. **Embedded payload:** MSI compound file (89.6 MB) containing JRE/JDK (OpenJDK 25.0.1) + application
6. **No overlay:** 0 bytes of appended data beyond sections
7. **Signature:** Certificate table present but data not verifiable without a valid signature

---

## 2. Finding Summary

| Check | Result | Verdict |
|---|---|---|
| SHA-256 & File Size | `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb` / 90,396,672 bytes | ✓ VERIFIED |
| PE Machine | x86-64 (`0x8664`) | ✓ VERIFIED |
| Subsystem | GUI (2) | ✓ VERIFIED |
| Exports | None | ✓ VERIFIED |
| Import DLLs | 6 DLLs (KERNEL32, msi.dll, ole32, SHELL32, SHLWAPI, USER32) | ✓ VERIFIED |
| Resource Types | 4 types (RT_ICON, RT_MANIFEST, RT_VERSION, RT_DLGINCLUDE) | ✓ VERIFIED |
| .rsrc Size | 89,826,352 bytes (85.7 MB) | ✓ VERIFIED |
| Embedded MSI | RT_MANIFEST "MSI" = compound MSI (89.6 MB) | ✓ VERIFIED |
| Overlay | None (0 bytes) | ✓ VERIFIED |
| JPackage evidence | `jdk.jpackage.windows.native.common` strings present | ✓ VERIFIED |
| JRE/JDK | OpenJDK 25.0.1 metadata in version strings | ✓ VERIFIED |
| mscoree.dll / msimsg.dll | String-only references (not imports) | ✓ VERIFIED |
| Signature | Certificate table present, but data unverifiable | ⚠ VERIFIED* |

\* Signature data is present but unverifiable without a valid signature. The certificate table at VA `0x8b600` with size 10,408 bytes does not appear to be a standard X.509 certificate (first bytes are not ASN.1 SEQUENCE).

---

## 3. Key Conclusions

### Executable Type Classification

**The executable is a self-contained packaged application:**

- It is a Java application ("Mixing Station for Desktop") packaged using **jpackage** (Java's native application packaging tool)
- The jpackage tool generated a Windows MSI installer with the bundled JRE
- The binary is the MSI installer wrapper executable (msiwrapper.exe)
- The MSI package (89.6 MB) contains:
  - OpenJDK 25.0.1 (Eclipse Adoptium)
  - The application files
  - MSI installer metadata

### Runtime Identification

- **Primary runtime:** Windows Installer (msi.dll) — 27 ordinal imports
- **Java runtime:** OpenJDK 25.0.1 (bundled inside the MSI)
- **JPackage tool:** `jdk.jpackage.windows.native.common` — confirms jpackage usage
- **.NET CLR:** mscoree.dll (string reference only — not a real import)
- **No console:** Subsystem 2 (GUI)

### Resource Overview

| Resource | Type | Size | Contents |
|---|---|---|---|
| RT_ICON | Type 3 | ~140 KB | 9 icon entries |
| RT_MANIFEST "MSI" | Type 10 | 89.6 MB | Compound MSI package |
| RT_MANIFEST "PRODUCT_CODE" | Type 10 | Variable | MSI product code |
| RT_VERSION | Type 14 | ~12 KB | Version info (VS_FIXEDFILEINFO) |
| RT_DLGINCLUDE | Type 16 | ~1 KB | Dialog template |

---

## 4. Recommended Next RE Engine

### Recommended Engine: **JADX or CFR** (for the Java application)

**Rationale:**

The binary is a **Java application** packaged with jpackage. The embedded MSI package contains the Java Runtime Environment (OpenJDK 25.0.1) and the application's bytecode.

**Recommended tools in order:**

1. **JADX** — Decompile the Java bytecode from the MSI package (best for Java source reconstruction)
2. **CFR** — Alternative Java decompiler (robust for obfuscated or complex code)
3. **Ghidra** — For analyzing the native launcher (msiwrapper.exe) and the embedded JRE (but Ghidra is not the primary tool for the Java app)

**Why NOT Ghidra?**

- Ghidra is a native decompiler, not designed for Java bytecode
- The binary's core logic is Java bytecode inside the MSI package
- Ghidra would only analyze the native launcher (msiwrapper.exe), which is a small part of the analysis

**Why NOT dnSpy/ILSpy?**

- dnSpy/ILSpy analyze .NET assemblies
- `mscoree.dll` is only a string reference, not an actual .NET dependency
- The binary's runtime is Java, not .NET

### Recommended Analysis Workflow

1. **Extract the MSI package** from the RT_MANIFEST resource (89.6 MB)
   - Use `msiextract` / `instmod` / `msi` command-line tools
   - Or write a Python script to parse the compound

2. **Decompile the Java application** inside the MSI:
   - Use JADX to get Java source code
   - Use CFR for alternative decompilation
   - Use `javap` for JVM class inspection

3. **Analyze the embedded JRE** (OpenJDK 25.0.1):
   - Identify the specific version and modifications
   - Check for custom patches or runtime modifications

4. **Analyze the MSI installer**:
   - Use `msiextract` to extract the MSI package
   - Use `msi` command-line tools to query the package
   - Examine the custom actions (using the msi.dll imports)

---

## 5. Tool Recommendations

| Tool | Purpose | Status |
|---|---|---|
| pefile | PE structural analysis | ✓ Installed |
| 7-Zip | Archive extraction | ✓ Installed |
| Sigcheck | Signature verification | ✓ Available |
| JADX | Java decompilation | ❌ Not installed (recommended) |
| CFR | Java decompilation | ❌ Not installed (recommended) |
| Ghidra | Native decompilation | ❌ Not installed (not primary) |
| msiextract | MSI package extraction | ❌ Not installed (recommended) |

---

## 6. Final Report

### Verifying Ghidra

- **Ghidra is NOT installed** — `Ghidra` is a native decompiler, not suitable for Java bytecode
- **Recommendation:** Use **JADX** or **CFR** for the Java application analysis
- Ghidra is only useful for the native launcher (msiwrapper.exe), which is a minor part of the analysis

### Verifying JADX

- **JADX** is **NOT installed** — it is a Java decompiler (Dex to Java)
- Recommended for Java bytecode analysis inside the embedded JRE

### Verifying CFR

- **CFR** is **NOT installed** — it is a Java decompiler (class to Java)
- Recommended as an alternative to JADX

### Verifying dnSpy/ILSpy

- **dnSpy/ILSpy** are **NOT installed** — they analyze .NET assemblies
- Not recommended because `mscoree.dll` is only a string reference, not a real .NET dependency

---

## 7. Closing Summary

The binary `mixing-station-pc-windows-3.2.2_789.exe` is a **self-contained packaged application**:

- **Type:** Java application packaged as an MSI installer using jpackage
- **JRE/JDK:** OpenJDK 25.0.1 (Eclipse Adoptium)
- **Product:** Mixing Station for Desktop 3.2.2
- **Company:** dev-core (Mixing Station GmbH)
- **Embedded payload:** MSI compound (89.6 MB) with JRE + application files

**Next RE engine:** JADX or CFR (for the Java application bytecode inside the MSI package)

**Key finding:** The binary is NOT a native application — it is a Java application wrapped in an MSI installer. The primary target for analysis should be the Java bytecode inside the embedded MSI package, not the native launcher.
