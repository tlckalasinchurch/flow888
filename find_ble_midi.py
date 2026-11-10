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
            
            # Check BLE
            ble_strs = [s for s in strings if 'bluetooth' in s.lower() or 'gatt' in s.lower() or 'ble' in s.lower()]
            if ble_strs and any('service' in s.lower() or 'characteristic' in s.lower() or 'uuid' in s.lower() or 'device' in s.lower() for s in ble_strs):
                print(f"[BLE] {p.this_class_name}: {ble_strs[:6]}")

            # Check MIDI
            midi_strs = [s for s in strings if 'javax/sound/midi' in s or 'midi' in s.lower()]
            if len(midi_strs) > 3:
                print(f"[MIDI] {p.this_class_name}: {midi_strs[:6]}")
        except Exception:
            pass
