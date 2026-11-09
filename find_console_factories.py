import zipfile
from jvm_class_parser import JavaClassParser

jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"

target_cls = "org/devcore/mixingstation/api/dto/network/ConsoleListDto$ConsoleFactoryDto"

with zipfile.ZipFile(jar_path, 'r') as z:
    for name in z.namelist():
        if not name.endswith('.class'):
            continue
        try:
            data = z.read(name)
            p = JavaClassParser(data)
            # Check constant pool for target_cls
            for item in p.constant_pool:
                if item and item[0] == 'Class':
                    cname = p.get_utf8(item[1])
                    if target_cls in cname or 'ConsoleListDto' in cname:
                        print(f"Found reference in {p.this_class_name}")
                        print("  Strings:", p.get_strings()[:10])
                        break
        except Exception:
            pass
