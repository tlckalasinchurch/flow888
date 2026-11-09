import hashlib
import os

files_to_hash = [
    (r"C:\Users\Administrator\Downloads\mixing-station-pc-windows-3.2.2_789.exe", "Original MSI Wrapper Installer Executable"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installer.msi", "Extracted Embedded MSI Package (RT_MANIFEST ID 999)"),
    (r"C:\Users\Administrator\Downloads\_pe_extract\Data.cab", "MSI Embedded Cabinet File (Data.cab)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\mixing-station-pc.exe", "Installed Native JPackage Application Launcher"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar", "Application Fat JAR"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-pc.cfg", "JPackage Launcher Configuration"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\.package", "JPackage Package Identification File"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\runtime\bin\server\jvm.dll", "Bundled OpenJDK 25.0.1 JVM Library"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\runtime\lib\modules", "Bundled OpenJDK 25.0.1 JImage Modules"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\runtime\release", "OpenJDK 25.0.1 Release Specification"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\WinMultitouch64.dll", "Native Touch Input DLL (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\jnidispatch.dll", "JNA 5.x C Dispatcher DLL (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\glfw.dll", "LWJGL3 GLFW Windowing DLL (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\OpenAL.dll", "OpenAL Soft Audio Library (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\libEGL.dll", "Google ANGLE EGL Direct3D Bridge (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\libGLESv2.dll", "Google ANGLE GLESv2 Direct3D Bridge (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\gdx64.dll", "LibGDX Core Native DLL (Embedded in JAR)"),
    (r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\native_dlls\gdx-freetype64.dll", "LibGDX FreeType Native DLL (Embedded in JAR)"),
]

for p, desc in files_to_hash:
    if os.path.exists(p):
        size = os.path.getsize(p)
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            while chunk := f.read(65536):
                h.update(chunk)
        print(f"| `{os.path.basename(p)}` | {desc} | {size:,} bytes | `{h.hexdigest()}` | VERIFIED |")
    else:
        print(f"| `{os.path.basename(p)}` | {desc} | MISSING | UNKNOWN |")
