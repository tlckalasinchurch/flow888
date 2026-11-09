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
            strings = p.get_strings()
            osc_strs = [s for s in strings if '/xremote' in s or '/xinfo' in s or '/status' in s or '/ch/' in s or 'osc' in s.lower() or '#bundle' in s]
            if len(osc_strs) > 2:
                print(f"[OSC] {p.this_class_name}: {osc_strs[:8]}")
        except Exception:
            pass
