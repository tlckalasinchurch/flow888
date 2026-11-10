import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

terms = ['xr18', 'xair', 'x18', 'x12', 'x16', 'x32', 'm32', 'wing', 'qu-16', 'qu-24', 'qu-32', 'sq-5', 'sq-6', 'sq-7', 'dlive', 'avantis', 'ui12', 'ui16', 'ui24']

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
                for b in terms:
                    if b in sl:
                        found.append(s)
            if found:
                print(f"=== {p.this_class_name} ===")
                for s in set(found)[:10]:
                    print("  ", repr(s))
        except Exception:
            pass
