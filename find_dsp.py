import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

eq_classes = []
comp_classes = []
fx_classes = []

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class') or not name.startswith('blob/'):
            continue
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            strings = p.get_strings()
            s_lower = [s.lower() for s in strings]

            # EQ
            if any('peq' in s or 'geq' in s or 'parametric' in s or 'high pass' in s or 'low pass' in s or 'bell' in s or 'notch' in s for s in s_lower):
                hits = [s for s in strings if any(x in s.lower() for x in ['peq', 'geq', 'parametric', 'high pass', 'low pass', 'bell', 'notch'])]
                eq_classes.append((p.this_class_name, p.super_class_name, hits[:5]))

            # Compressor / Gate / Dynamics
            if any('compressor' in s or 'gate' in s or 'threshold' in s or 'ratio' in s or 'attack' in s or 'release' in s or 'knee' in s for s in s_lower):
                hits = [s for s in strings if any(x in s.lower() for x in ['compressor', 'gate', 'threshold', 'ratio', 'attack', 'release', 'knee'])]
                if len(hits) >= 3:
                    comp_classes.append((p.this_class_name, p.super_class_name, hits[:5]))

            # FX
            if any('reverb' in s or 'chorus' in s or 'flanger' in s or 'pitch' in s or 'de-esser' in s or 'rotary' in s or 'hall' in s for s in s_lower):
                hits = [s for s in strings if any(x in s.lower() for x in ['reverb', 'chorus', 'flanger', 'pitch', 'de-esser', 'rotary', 'hall'])]
                fx_classes.append((p.this_class_name, p.super_class_name, hits[:5]))

        except Exception:
            pass

print(f"=== EQ CLASSES ({len(eq_classes)}) ===")
for c, sup, hits in eq_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")

print(f"\n=== COMPRESSOR / DYNAMICS CLASSES ({len(comp_classes)}) ===")
for c, sup, hits in comp_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")

print(f"\n=== FX CLASSES ({len(fx_classes)}) ===")
for c, sup, hits in fx_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")
