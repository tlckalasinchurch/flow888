# PE Analysis — Imports, Exports & DLL Dependencies

**Target:** `mixing-station-pc-windows-3.2.2_789.exe`  
**SHA-256:** `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb`  
**File size:** 90,396,672 bytes (86.2 MB)  
**Architecture:** x86-64 (PE32+), Graphical Subsystem (subsystem 2)

---

## 1. Exports

**Status: NONE — VERIFIED**

The Export directory is absent:

- Export VirtualAddress = `0x0`
- Export Size = `0x0`

The binary does not export any functions. It is a freestanding executable, not a DLL or a library.

---

## 2. Import Table (DLL Dependencies)

**Status: VERIFIED**

Six DLLs are imported:

| DLL | Import count | Import mode | Notable imports |
|---|---|---|---|
| `KERNEL32.dll` | 118 | Name-based | `CreateProcessW`, `LoadLibraryExW`, `GetProcAddress`, `VirtualProtect`, `RtlUnwindEx`, `SetUnhandledExceptionFilter`, `IsDebuggerPresent`, etc. |
| `msi.dll` | 27 | **Ordinal-only** | Windows Installer API (all imports are ordinal, no function names visible) |
| `ole32.dll` | 3 | Name-based | `CoCreateGuid`, `StringFromGUID2`, `IIDFromString` |
| `SHELL32.dll` | 1 | Name-based | `CommandLineToArgvW` |
| `SHLWAPI.dll` | 1 | Name-based | `PathIsDirectoryEmptyW` |
| `USER32.dll` | 1 | Name-based | `MessageBoxW` |

### Import Analysis

- **KERNEL32** — standard Windows API for process/thread management, file I/O, memory protection, console, and critical-section operations. The presence of `CreateProcessW`, `VirtualProtect`, `RtlUnwindEx`, and exception-filter functions indicates the binary performs process creation and exception handling.
- **msi.dll** — the Windows Installer library. All 27 imports are ordinal-based, making detailed analysis difficult without further context. This is a strong indicator that the binary is an **MSI installer or MSI-bundling wrapper**.
- **ole32** — COM interface string creation (CoCreateGuid, StringFromGUID2, IIDFromString) suggests the binary uses COM for some operations.
- **SHELL32 / SHLWAPI** — standard shell API for command-line parsing and path validation.
- **USER32** — a single MessageBox import for likely user notification or error reporting.

---

## 3. DLL Dependency Summary

**VERIFIED:**

- 6 unique DLLs imported
- 118 + 27 + 3 + 1 + 1 + 1 = **151 total imports**
- **0 Objective-C / macOS frameworks** (this is a Windows PE binary)
- No Java or JVM library names appear in the import table (Java references are only string-level, see RUNTIME_IDENTIFICATION.md)

---

## 4. Key Conclusions

- **VERIFIED:** No function exports exist.
- **VERIFIED:** Exactly 6 DLLs are imported (KERNEL32, msi.dll, ole32, SHELL32, SHLWAPI, USER32).
- **VERIFIED:** The binary imports `msi.dll` — a Windows Installer runtime dependency.
- **PROBABLE:** The binary is an MSI installer or MSI-bundling wrapper (based on msi.dll import + product metadata).
- **UNKNOWN:** Whether the `msi.dll` imports are used to execute a bundled MSI or to query/installer metadata.
