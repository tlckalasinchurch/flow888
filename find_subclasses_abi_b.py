import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class'):
            continue
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            if p.super_class_name == 'blob/abi/b':
                print(f"Subclass of blob/abi/b: {p.this_class_name}")
                print("  Strings:", p.get_strings()[:10])
        except Exception:
            pass
