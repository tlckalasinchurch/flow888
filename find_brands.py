import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

brands = ['behringer', 'midas', 'allen', 'heath', 'soundcraft', 'yamaha', 'presonus', 'mackie']

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class'):
            continue
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            strings = p.get_strings()
            found = []
            for s in strings:
                sl = s.lower()
                for b in brands:
                    if b in sl:
                        found.append(s)
            if found:
                print(f"=== {p.this_class_name} ===")
                for s in set(found)[:10]:
                    print("  ", repr(s))
        except Exception:
            pass
