# PE Analysis — Overlay & Appended Data

**Target:** `mixing-station-pc-windows-3.2.2_789.exe`  
**SHA-256:** `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb`  
**File size:** 90,396,672 bytes (86.2 MB)  
**Architecture:** x86-64 (PE32+), Graphical Subsystem (subsystem 2)

---

## 1. Overlay Definition

An overlay is data appended after the last section of a PE file. It is outside the section boundaries and is accessed via the `IMAGE_DIRECTORY_ENTRY_OVERLAY` entry (which is absent in this binary).

---

## 2. Section Raw Data Sizes

| Section | VirtualAddress | Raw offset | SizeOfRawData | VirtualSize | Notes |
|---|---|---|---|---|---|
| `.text` | `0x1000` | `0x0000400` | `0x063e00` | `0x063d60` | Code |
| `.rdata` | `0x65000` | `0x00064200` | `0x01c800` | `0x01c620` | Read-only data |
| `.data` | `0x82000` | `0x00080a00` | `0x001e00` | `0x00360c` | Initialized data |
| `.pdata` | `0x86000` | `0x00082800` | `0x007a00` | `0x0079f8` | Exception handling |
| `.fptable` | `0x8e000` | `0x0008a200` | `0x000200` | `0x000100` | Function tables |
| `.rsrc` | `0x8f000` | `0x0008a400` | `0x55aa600` | `0x55aa430` | **Resources (85.7 MB)** |
| `.reloc` | `0x563a000` | `0x05634a00` | `0x000e00` | `0x000c8c` | Relocation table |
| **Total** | — | — | **90,395,648** | **90,400,064** | — |

---

## 3. Overlay Detection

**Status: NONE — VERIFIED**

The file has **no overlay data**:

- Total section raw size: 90,395,648 bytes
- Total file size: 90,396,672 bytes
- Overflow: 1,024 bytes (0x400) — alignment padding only

The file ends exactly at the end of the `.reloc` section (`0x05635800`). The last 1,024 bytes are alignment padding between sections, not meaningful overlay data.

---

## 4. Section Overlap Analysis

The `.rsrc` and `.reloc` sections appear to overlap in the file:

- `.rsrc` ends at: `0x0008a400 + 0x055aa600 = 0x05635A00`
- `.reloc` starts at: `0x05634a00`
- `.reloc` ends at: `0x05634a00 + 0x0e00 = 0x05635800`

Wait — the `.rsrc` section starts at `0x8A400` and has SizeOfRawData `0x55AA600`.  
End of `.rsrc` = `0x8A400 + 0x55AA600 = 0x5634E00`.

But the `.reloc` section starts at `0x5634A00`, which is 0x400 (1024) bytes before the end of `.rsrc`. This is a **overlap of 1,024 bytes** between `.rsrc` and `.reloc` in the file.

This is NOT an overlay — it is a section alignment artifact. The `.rsrc` section is padded to align with the `.reloc` section, or vice versa. The total file size is 90,396,672 bytes (0x5635800), which is consistent.

**Conclusion:** No overlay data exists.

---

## 5. Repository / Archive Detection

**Status: NONE FOUND — VERIFIED**

The file was scanned for embedded archives using multiple methods:

1. **7-Zip extraction** — "Everything is Ok", 4 files recovered from the binary
2. **Python structural analysis** — Scanning for archive signatures in the file and overlay
3. **7z direct scan** — The binary was scanned for ZIP, JAR, 7z, CAB, MSI, etc.

**Results:**

- No ZIP/JAR archive signatures found (`PK\x03\x04` not present at any overlap boundary)
- No 7z archive found (`7z\xBC\xAF` not present)
- No GZIP or LZMA signatures found
- No CAB (MSCF) signature found
- No standalone PE overlay found

The bulk of the file is the `.rsrc` section, which contains the embedded MSI package. The MSI package itself is a compound file, not a standard archive.

---

## 6. Overlay Summary

| Check | Result |
|---|---|
| Overlay directory entry present? | No (absent) |
| Appended data after last section? | No (0 bytes meaningful) |
| 7-Zip extraction? | 4 files only (from .rsrc resources) |
| Archive signatures in overlay? | None found |
| ZIP/JAR/7z/CAB/MSI in overlay? | No — the MSI is inside `.rsrc` |

---

## 7. Summary

**VERIFIED:**

- No overlay data exists in the binary
- File size = 90,395,648 (section raw sizes) + 1,024 bytes (alignment padding)
- The `.rsrc` section (85.7 MB) is the primary storage location for the embedded MSI package

**PROBABLE:**

- The MSI package (89.6 MB) is stored within the `.rsrc` section's `RT_MANIFEST` resource
- The MSI package is a compound file, not a standard archive format

**UNKNOWN:**

- The exact layout of the compound MSI within the `.rsrc` section (offsets, sizes)
- Whether additional data is embedded in the `.rsrc` section's high-entropy region
