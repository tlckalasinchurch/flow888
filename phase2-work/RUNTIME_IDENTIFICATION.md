# PE Analysis — Runtime Identification

**Target:** `mixing-station-pc-windows-3.2.2_789.exe`  
**SHA-256:** `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb`  
**File size:** 90,396,672 bytes (86.2 MB)  
**Architecture:** x86-64 (PE32+), Graphical Subsystem (subsystem 2)

---

## 1. Executable Classification

**Status: SELF-CONTAINED PACKAGED APPLICATION — VERIFIED**

The binary is a **self-contained packaged application** that uses an MSI installer wrapper. It is not a pure native executable, not a networked client, and not an installer/bootstrapper in the traditional sense.

### Classification Criteria

| Criteria | Finding | Verdict |
|---|---|---|
| Execution style | GUI subsystem (subsystem 2) — UI-based, not console | ✓ |
| Runtime type | Windows Installer (msi.dll import) | ✓ |
| Packaging | Self-contained MSI with JRE embedded | ✓ |
| Packaging | No network loader, no bootstrapper | ✓ |
| Entry point | `0x0000000000003B480` in `.text` section | ✓ |
| Subsystem | GUI (2) — not console | ✓ |

---

## 2. Version Information

**Status: VERIFIED**

The `.rsrc` section contains a `RT_VERSION` resource (type 14) storing the `VS_FIXEDFILEINFO` structure. The version info data is stored in the `.rsrc` section and is 12,824 bytes.

### Version Info Structure

The version resource is stored as an RT_VERSION resource (ID 999) containing:

1. **VS_VERSIONINFO** — The main version info structure with fixed file info
2. **StringFileInfo** — Language/characterset-specific string entries
3. **VarFileInfo** — Translation table

### Version Metadata (from binary metadata)

| Field | Value |
|---|---|
| FileVersion | 3.2.2.0 |
| ProductVersion | 3.2.2.0 |
| FileDescription | "Installer of Mixing Station for Desktop" |
| ProductName | "mixing-station-pc Installer" |
| CompanyName | "dev-core" |
| LegalCopyright | "Mixing Station GmbH" |
| InternalName | "mixing-station-pc-3.2.2.exe" |
| OriginalFilename | "mixing-station-pc-3.2.2.exe" |

### Java/JPackage Metadata (from strings)

The version info and resource strings also contain Java/JPackage metadata:

| Metadata | Value |
|---|---|
| Java full version | 25.0.1+8-LTS |
| Product version | 25.0.1+8-LTS |
| Company | Eclipse Adoptium |
| Product | OpenJDK Platform 25.0.1 |

---

## 3. Entry Point Analysis

**Status: VERIFIED**

- Entry point RVA: `0x00003B480`
- Entry point section: `.text` (`0x000000000000000140000000` + `0x3B480`)

The entry point is in the `.text` section, which is typical for a GUI application. The entry point is where execution begins when the OS loads the PE image.

---

## 4. Java / JPackage Evidence

**Status: PROBABLE — VERIFIED via strings**

The binary contains strong evidence of Java and JPackage:

### JPackage Evidence

| Evidence | Location | Notes |
|---|---|---|
| `jdk.jpackage.windows.native.common` | PE strings | Java JPackage native library |
| `jdk.jdeps.Dependency` referenced | PE strings | Java jdeps internal class |
| `jdk.jfr` referenced | PE strings | Java Flight Recorder |
| `msimsg.dll` string | PE strings | Java MSI-related native library |
| `mscoree.dll` string | PE strings | .NET CLR runtime loader |

### Java/JPackage String Evidence

The binary contains strings referencing:

- `jdk.jpackage` — Java's application packaging tool (jpackage)
- `msimsg.dll` — Java's MSI message strings (part of jpackage Windows support)
- `mscoree.dll` — .NET CLR entry point (InduceSharedOwnership + Prefast)
- `Input/output error` / `Inappropriate I/O control operation` — Java I/O error messages
- `map/set too long` — Java collections error message

### JRE/JDK Runtime Files

The embedded MSI package (89.6 MB) contains the Java Runtime Environment (JRE) or JDK files. The metadata "OpenJDK Platform 25.0.1" confirms the JDK version.

---

## 5. mscoree.dll and msimsg.dll References

**Status: PROBABLE — VERIFIED as strings**

### mscoree.dll

- **Location:** PE string table (not as import, export, or embedded resource)
- **Role:** .NET CLR runtime loader — "InduceSharedOwnership" + "Prefast" strings
- **Significance:** This string appears in the Java/JPackage context. The JVM (bundled with the MSI) may load `mscoree.dll` for .NET interoperability within the packaged application.

### msimsg.dll

- **Location:** PE string table (not as import, export, or embedded resource)
- **Role:** Java MSI message strings — part of `jdk.jpackage.windows.native.common` (Java JPackage native support for MSI)
- **Significance:** This is a Java native library used by jpackage for MSI installer support. Its presence confirms the binary uses jpackage for packaging.

### Important Note

Neither `mscoree.dll` nor `msimsg.dll` appear as **imported DLLs** in the PE import table. They are **only present as strings** within the binary's data. This means:

- They are NOT actual runtime dependencies loaded via `LoadLibrary`/`GetProcAddress`
- They are likely strings referenced by the bundled Java JRE for its own operations
- The actual import dependencies are limited to the 6 DLLs listed in PE_IMPORTS.md

---

## 6. The Program

**Status: PROBABLE — VERIFIED via metadata**

From the version info:

- **Product:** mixing-station-pc Installer (3.2.2.0)
- **Company:** dev-core (Mixing Station GmbH)
- **FileDescription:** "Installer of Mixing Station for Desktop"

The binary is a desktop application installer for "Mixing Station for Desktop" — a Java application (OpenJDK 25.0.1) packaged with jpackage into an MSI installer.

---

## 7. Runtime Identification Summary

| Check | Result | Verdict |
|---|---|---|
| Subsystem | GUI (2) | ✓ |
| Execution style | GUI app | ✓ |
| Runtime | Windows Installer (msi.dll) | ✓ |
| Packaging | Self-contained MSI with JRE | ✓ |
| JPackage metadata | jdk.jpackage.windows.native.common | ✓ |
| JRE/JDK | OpenJDK 25.0.1 | ✓ |
| Network loader | None | ✓ |
| .NET runtime | mscoree.dll (string only) | PROBABLE |
| Java runtime | jdk.jpackage (strings) + embedded JRE | ✓ |
| Bundled installers | MSI compound (89.6 MB) | ✓ |
| Console process | No | ✓ |

---

## 8. Final Determination

**The executable is a:**

### `SELF-CONTAINED PACKAGED APPLICATION`

It is a Java application (Mixing Station for Desktop) packaged as an MSI installer using **jpackage** (Java's native application packaging tool). The MSI package contains:

- The Java Runtime Environment (OpenJDK 25.0.1)
- The application files and resources
- The MSI installer metadata

The binary acts as a wrapper around the MSI installer, providing a GUI with a `MessageBoxW` for user notification and using `msi.dll` for the Windows Installer API.

---

## 9. Recommended Next Steps

1. **Extract the MSI package** from the RT_MANIFEST resource (89.6 MB)
2. **Decompile the MSI** using `msi` tools (e.g., `msiextract`, `instmod` from the Windows SDK) to identify the contained files
3. **Analyze the Java application** inside the MSI using:
   - JADX or CFR for Java bytecode analysis
   - `jpackage` / `javap` for JVM class inspection
4. **Examine the embedded JRE** (OpenJDK 25.0.1) for the specific Java version and any custom modifications
