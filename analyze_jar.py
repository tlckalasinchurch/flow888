import zipfile, os
from collections import Counter

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

with zipfile.ZipFile(jar_path, 'r') as z:
    names = z.namelist()
    
    # Check extensions
    exts = Counter(os.path.splitext(n)[1].lower() for n in names)
    print("=== EXTENSIONS IN JAR ===")
    for ext, count in exts.most_common():
        print(f"  {ext if ext else '(dir/none)'}: {count}")
        
    # Check for native libraries (.dll, .so, .dylib)
    native_files = [n for n in names if any(n.lower().endswith(ext) for ext in ['.dll', '.so', '.dylib', '.jnilib'])]
    print(f"\n=== NATIVE LIBRARIES IN JAR ({len(native_files)}) ===")
    for nf in native_files:
        print(f"  {nf} ({z.getinfo(nf).file_size} bytes)")

    # Check top-level packages
    top_packages = Counter()
    all_packages = set()
    class_count = 0
    for n in names:
        if n.endswith('.class'):
            class_count += 1
            parts = n.split('/')
            if len(parts) > 1:
                top_packages['/'.join(parts[:2])] += 1
                all_packages.add('/'.join(parts[:-1]))
    
    print(f"\n=== TOTAL CLASSES: {class_count} ===")
    print(f"=== TOP LEVEL PACKAGE PREFIXES ===")
    for pkg, count in top_packages.most_common(30):
        print(f"  {pkg.replace('/', '.')}: {count} classes")

    print(f"\n=== DISTINCT PACKAGES COUNT: {len(all_packages)} ===")
