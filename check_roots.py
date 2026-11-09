import zipfile
from collections import Counter

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

with zipfile.ZipFile(jar_path, 'r') as z:
    classes = [n for n in z.namelist() if n.endswith('.class')]
    roots = Counter()
    for c in classes:
        parts = c.split('/')
        if len(parts) > 1:
            roots[parts[0]] += 1
        else:
            roots['(root)'] += 1
            
    print("=== CLASS COUNT BY ROOT DIRECTORY ===")
    for r, count in roots.most_common():
        print(f"  {r}: {count}")
