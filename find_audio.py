import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

terms = ['asio', 'wasapi', 'directsound', 'openal', 'audioinput', 'audiodevice', 'samplerate', 'buffersize', 'rta', 'microphone']

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class'):
            continue
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            strings = p.get_strings()
            found = [s for s in strings if any(t in s.lower() for t in terms)]
            if len(found) > 1:
                print(f"=== {p.this_class_name} ===")
                for s in set(found)[:8]:
                    print("  ", repr(s))
        except Exception:
            pass
