import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

scene_classes = []
routing_classes = []
meter_classes = []
persist_classes = []

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class') or not name.startswith('blob/'):
            continue
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            strings = p.get_strings()
            s_lower = [s.lower() for s in strings]
            
            # Scene
            if any('scene' in s or 'snapshot' in s or 'cue' in s or 'snippet' in s for s in s_lower):
                scene_hits = [s for s in strings if any(x in s.lower() for x in ['scene', 'snapshot', 'cue', 'snippet'])]
                if len(scene_hits) >= 2:
                    scene_classes.append((p.this_class_name, p.super_class_name, scene_hits[:5]))

            # Routing
            if any('routing' in s or 'patch' in s or 'inputsource' in s for s in s_lower):
                rout_hits = [s for s in strings if any(x in s.lower() for x in ['routing', 'patch', 'inputsource'])]
                if len(rout_hits) >= 2:
                    routing_classes.append((p.this_class_name, p.super_class_name, rout_hits[:5]))

            # Metering
            if any('meter' in s or 'vumeter' in s or 'peakmeter' in s for s in s_lower):
                meter_hits = [s for s in strings if any(x in s.lower() for x in ['meter', 'vumeter', 'peakmeter'])]
                if len(meter_hits) >= 2:
                    meter_classes.append((p.this_class_name, p.super_class_name, meter_hits[:5]))

            # Persistence / storage
            if any('.json' in s or '.ms' in s or 'settings' in s.lower() or 'preference' in s.lower() for s in strings):
                persist_hits = [s for s in strings if any(x in s.lower() for x in ['.json', '.ms', 'settings', 'preference'])]
                if len(persist_hits) >= 2:
                    persist_classes.append((p.this_class_name, p.super_class_name, persist_hits[:5]))

        except Exception:
            pass

print(f"=== SCENE CLASSES ({len(scene_classes)}) ===")
for c, sup, hits in scene_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")

print(f"\n=== ROUTING CLASSES ({len(routing_classes)}) ===")
for c, sup, hits in routing_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")

print(f"\n=== METERING CLASSES ({len(meter_classes)}) ===")
for c, sup, hits in meter_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")

print(f"\n=== PERSISTENCE CLASSES ({len(persist_classes)}) ===")
for c, sup, hits in persist_classes[:10]:
    print(f"  {c} (super {sup}) -> {hits}")
