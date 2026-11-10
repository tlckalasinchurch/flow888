import zipfile

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

with zipfile.ZipFile(jar_path, 'r') as z:
    devcore_classes = [n for n in z.namelist() if n.startswith('org/devcore') and n.endswith('.class')]
    print(f"Total org.devcore classes: {len(devcore_classes)}")
    for c in sorted(devcore_classes):
        print(" ", c)
