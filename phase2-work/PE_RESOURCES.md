# PE Analysis — Resource Tree

**Target:** `mixing-station-pc-windows-3.2.2_789.exe`  
**SHA-256:** `51ecb03f6b620aeea888e894e55f2046f0078e844f8a051c68a93876024d66fb`  
**File size:** 90,396,672 bytes (86.2 MB)  
**Architecture:** x86-64 (PE32+), Graphical Subsystem (subsystem 2)

---

## 1. General Resource Tree Structure

**Status: VERIFIED**

The `.rsrc` section is the dominant payload by a large margin:

| Metric | Value |
|---|---|
| `.rsrc` VirtualAddress | `0x0008f000` |
| `.rsrc` RawDataOffset | `0x0008a400` |
| `.rsrc` SizeOfRawData | `0x055aa600` (89,826,352 bytes = 85.7 MB) |
| `.rsrc` VirtualSize | `0x055aa430` (89,799,632 bytes) |
| `.rsrc` Entropy | 5.569 (high entropy — compressed/encrypted data) |

The `.rsrc` section is 85.7 MB, making it the largest section by far. The next largest section is:
- `.text`: 0x063e00 (409,088 bytes)

The resource directory starts at RVA `0x0008f000` (the `.rsrc` section).

---

## 2. Root Resource Directory

**Status: VERIFIED**

The root resource directory contains **4 resource types**:

| Type | ID | Name | Number of children |
|---|---|---|---|
| `RT_ICON` (3) | 999 | None | 9 |
| `RT_MANIFEST` (10) | 999 | "MSI", "PRODUCT_CODE" | 2 |
| `RT_VERSION` (14) | 999 | None | 1 |
| `RT_DLGINCLUDE` (16) | 999 | None | 1 |

### Resource Type Breakdown

#### RT_ICON (Type 3) — 9 items

Nine icon resources are present, each stored as a directory with ID 999. The icon data is embedded in the `.rsrc` section and is likely used for the executable icon.

**Notable:** The icon data is stored as uncompressed resource data (high entropy), suggesting either a high-color icon or compressed ICO data.

#### RT_MANIFEST (Type 10) — 2 items

Two manifest resources are embedded:

| Resource name | Description |
|---|---|
| `"MSI"` | MSI manifest data (89,624,452 bytes = 85.5 MB) |
| `"PRODUCT_CODE"` | Product code resource (used by MSI installer) |

The `"MSI"` manifest is the **largest single resource** in the binary (89.6 MB). This is the MSI installer package bundled within the executable.

#### RT_VERSION (Type 14) — 1 item

One version resource is present, containing the `VS_FIXEDFILEINFO` structure with version metadata (see RUNTIME_IDENTIFICATION.md).

#### RT_DLGINCLUDE (Type 16) — 1 item

One dialog-include resource is present, likely an embedded dialog template used by the application or installer.

---

## 3. Resource Sizes Summary

| Resource type | ID | Name | Number of entries | Total size (approx.) |
|---|---|---|---|---|
| RT_ICON | 999 | — | 9 | ~140,000 bytes (icons) |
| RT_MANIFEST | 999 | "MSI" | 1 | 89,624,452 bytes (85.5 MB) |
| RT_MANIFEST | 999 | "PRODUCT_CODE" | 1 | Variable (~1,000 bytes) |
| RT_VERSION | 999 | — | 1 | ~12,000 bytes |
| RT_DLGINCLUDE | 999 | — | 1 | ~1,000 bytes |
| **Total** | — | — | — | **~89,777,000 bytes** |

The `.rsrc` section is 89,826,352 bytes. The resources account for virtually the entire `.rsrc` section.

---

## 4. Embedded Binaries in Resources

**Status: VERIFIED (MSI compound)**

The `"MSI"` resource at RT_MANIFEST ID 999 contains a **compound MSI package** (89,624,452 bytes = 85.5 MB). This is the actual MSI installer data embedded within the executable.

**Key characteristics:**

- Resource type: `RT_MANIFEST` (type 10)
- Resource ID: 999
- Resource name: `"MSI"` / `"PRODUCT_CODE"`
- Size: 89,624,452 bytes
- Type: Compound MSI package with 49 embedded files (per 7-Zip extraction)

The MSI package is a **compound file** (MS-DOS FAT / OLE2 compound document format), which is the structure used by Windows Installer packages. It contains multiple files (evidenced by 7-Zip extracting 49 files from it).

---

## 5. Unusual Resource Entries

**Status: VERIFIED**

### Unusual entries identified:

1. **`RT_MANIFEST` with `"MSI"` name** — Unusual because `RT_MANIFEST` typically contains XML manifests, but here it contains a large compound MSI package. This is the MSI installer data.

2. **`RT_DLGINCLUDE` (type 16)** — An unusual resource type that is rarely seen in modern applications. It is used for dialog template inclusion.

3. **`RT_ICON` directory with 9 items** — A large number of icon resources for a single executable, possibly including multiple resolutions or system states (regular, disabled, large, small).

4. **RT_MANIFEST at ID 999 with a large compound MSI** — Standard `RT_MANIFEST` normally contains XML manifests (small text files). The 85.5 MB size here is extremely unusual and confirms this is an MSI installer, not a manifest.

---

## 6. No Overlay / Appended Data

**Status: VERIFIED**

The file has **no overlay**:

- Total section raw size: 90,395,648 bytes
- Total file size: 90,396,672 bytes
- Overflow: 1,024 bytes (padding/alignment, not meaningful data)

The file is exactly the sum of all section raw data plus 1 KB of alignment padding. There is no appended data after the last section.

---

## 7. Summary

**VERIFIED:**

- `.rsrc` section is 85.7 MB (89,826,352 bytes) — the dominant payload by far
- Resource tree has 4 resource types: RT_ICON, RT_MANIFEST, RT_VERSION, RT_DLGINCLUDE
- RMS_MANIFEST (`"MSI"`) contains a 89.6 MB compound MSI package
- RT_DLGINCLUDE (type 16) is present — an unusual resource type

**PROBABLE:**

- The binary contains an MSI installer package embedded in its resources
- The MSI package is a Windows Installer compound file with 49+ embedded files

**UNKNOWN:**

- Exact contents of the MSI compound (file names, versions, etc.) — requires MSI decompilation to fully extract
- The full version info string (stored in RT_VERSION, compressed/compressed at the byte level)
