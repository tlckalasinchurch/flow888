import zipfile
import pefile
import os
import hashlib
from collections import defaultdict

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"
out_dir = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls"
os.makedirs(out_dir, exist_ok=True)

dll_data = {}

# Extract DLLs from JAR
with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if name.endswith('.dll') and ('x64' in name or 'win32-x86-64' in name or '/' not in name):
            dest_name = os.path.basename(name)
            data = z.read(name)
            target_path = os.path.join(out_dir, dest_name)
            with open(target_path, 'wb') as f:
                f.write(data)
            dll_data[dest_name] = (target_path, name)

print(f"Extracted {len(dll_data)} DLLs from JAR:")

def analyze_pe(file_path, orig_name):
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    sha256 = h.hexdigest()
    size = os.path.getsize(file_path)

    pe = pefile.PE(file_path, fast_load=False)
    machine = pe.FILE_HEADER.Machine
    arch = "x86-64" if machine == 0x8664 else ("x86" if machine == 0x14c else ("ARM64" if machine == 0xaa64 else hex(machine)))

    imports = defaultdict(list)
    if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            dll_name = entry.dll.decode('latin-1', errors='replace')
            for imp in entry.imports:
                func_name = imp.name.decode('latin-1', errors='replace') if imp.name else f"ordinal_{imp.ordinal}"
                imports[dll_name].append(func_name)

    exports = []
    if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT') and pe.DIRECTORY_ENTRY_EXPORT:
        for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if exp.name:
                exports.append(exp.name.decode('latin-1', errors='replace'))

    jni_exports = [e for e in exports if e.startswith('Java_')]

    return {
        'orig_name': orig_name,
        'size': size,
        'sha256': sha256,
        'arch': arch,
        'imports': {k: len(v) for k, v in imports.items()},
        'import_dlls': list(imports.keys()),
        'exports_count': len(exports),
        'exports_sample': exports[:15],
        'jni_exports': jni_exports
    }

results = {}
for dest_name, (target_path, orig_name) in dll_data.items():
    try:
        results[dest_name] = analyze_pe(target_path, orig_name)
        r = results[dest_name]
        print(f"\n--- {dest_name} ({orig_name}) ---")
        print(f"  Size: {r['size']} bytes | SHA256: {r['sha256'][:16]}... | Arch: {r['arch']}")
        print(f"  Import DLLs ({len(r['import_dlls'])}): {', '.join(r['import_dlls'])}")
        print(f"  Exports ({r['exports_count']}): {', '.join(r['exports_sample'][:8])}")
        if r['jni_exports']:
            print(f"  JNI Exports ({len(r['jni_exports'])}): {', '.join(r['jni_exports'])}")
    except Exception as e:
        print(f"Error analyzing {dest_name}: {e}")

# Save detailed results to JSON
import json
with open(os.path.join(out_dir, "native_analysis.json"), "w") as f:
    json.dump(results, f, indent=2)
