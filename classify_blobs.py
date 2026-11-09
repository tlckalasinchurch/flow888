import zipfile
from collections import defaultdict
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

keywords = [
    # Mixers
    'x32', 'm32', 'xair', 'xr18', 'wing', 'qu', 'sq', 'dlive', 'avantis', 'soundcraft', 'ui24', 'si impact',
    'yamaha', 'tf', 'ql', 'cl', 'mackie', 'dl32', 'presonus', 'studiolive', 'allen', 'heath',
    # Protocols
    'osc', 'midi', 'bluetooth', 'ble', 'usb', 'serial', 'hid', 'tcp', 'udp', 'http', 'websocket',
    # Audio / DSP
    'dsp', 'eq', 'compressor', 'gate', 'limiter', 'reverb', 'delay', 'fx', 'meter', 'fader', 'pan',
    'routing', 'channel', 'dca', 'bus', 'matrix', 'aux', 'scene', 'snapshot', 'cue', 'rta'
]

subpkg_matches = defaultdict(lambda: defaultdict(int))
subpkg_classes = defaultdict(list)

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class') or not name.startswith('blob/'):
            continue
        subpkg = '/'.join(name.split('/')[:2])
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            strings = p.get_strings()
            subpkg_classes[subpkg].append(p.this_class_name)
            for s in strings:
                sl = s.lower()
                for kw in keywords:
                    if kw in sl:
                        subpkg_matches[subpkg][kw] += 1
        except Exception as e:
            pass

print("=== SUBPACKAGE KEYWORD HITS ===")
for subpkg, kw_counts in sorted(subpkg_matches.items()):
    hits_str = ', '.join(f"{kw}:{count}" for kw, count in sorted(kw_counts.items(), key=lambda x: -x[1])[:8])
    print(f"{subpkg:20} ({len(subpkg_classes[subpkg]):3} classes) -> {hits_str}")
