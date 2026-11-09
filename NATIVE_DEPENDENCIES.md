# REA Phase 3 — Native Dependencies & DLL Analysis
**Target:** Mixing Station PC Windows 3.2.2 Build 789  
**Analysis Date:** 2026-11-09  
**Status:** VERIFIED  

---

## 1. Executive Summary

Mixing Station employs native libraries for three distinct operational tiers:
1. **Application Packaging & Runtime Engine:** JPackage native launcher and a stripped OpenJDK 25.0.1 64-bit Server VM (`jvm.dll`).
2. **Graphics & Audio Acceleration (Embedded in JAR):** Google ANGLE (Direct3D 11 / OpenGL ES bridge), LWJGL 3 native bindings (GLFW, jemalloc, OpenAL Soft, STB, TinyFD), and LibGDX native engines (`gdx64.dll`, `gdx-freetype64.dll`).
3. **Hardware Touch Digitizer Integration:** `WinMultitouch64.dll`, a proprietary JNI library linking Windows multi-touch messages directly into the Java UI thread.

---

## 2. Embedded Native Libraries (Inside `mixing-station-desktop.jar`)

All embedded binaries were extracted and statically verified via PE header and export analysis:

| DLL Name | Internal Jar Path | CPU Arch | File Size | SHA-256 (Truncated) | Primary Imports | JNI / Native Role |
|---|---|---|---|---|---|---|
| **WinMultitouch64.dll** | `WinMultitouch64.dll` | x86-64 | 262,144 | `83381f840e084c6e...` | KERNEL32, USER32 | **JNI:** `Java_org_devcore_touch_win_WinMultitouch_initTouch`, `dispose` |
| **jnidispatch.dll** | `com/sun/jna/win32-x86-64/` | x86-64 | 235,008 | `cf8e552ee05cb0e8...` | KERNEL32, PSAPI | **JNA:** Core C dispatcher for Java Native Access FFI |
| **libGLESv2.dll** | `windows/x64/angle/` | x86-64 | 7,519,232 | `f25545f26c4ec5ad...` | KERNEL32, USER32, GDI32, D3DCOMPILER_47, dxgi, d3d11 | **ANGLE:** Translates OpenGL ES 2.0/3.0 to Direct3D 11 |
| **libEGL.dll** | `windows/x64/angle/` | x86-64 | 509,440 | `1a1f0aacfae9bdd8...` | KERNEL32, USER32, GDI32, libGLESv2.dll | **EGL:** Window surface context management for ANGLE |
| **OpenAL.dll** | `windows/x64/org/lwjgl/openal/` | x86-64 | 1,338,368 | `0630aa42492f7812...` | KERNEL32, USER32, OLE32, WINMM | **Audio:** OpenAL Soft audio playback & microphone capture |
| **glfw.dll** | `windows/x64/org/lwjgl/glfw/` | x86-64 | 496,128 | `affa7e54eb0dedce...` | KERNEL32, USER32, GDI32, SHELL32 | **Windowing:** Desktop window creation, event loop, mouse/keyboard |
| **jemalloc.dll** | `windows/x64/org/lwjgl/jemalloc/` | x86-64 | 398,336 | `e97a3a608031e846...` | KERNEL32 | **Memory:** High-performance off-heap native memory allocator |
| **lwjgl.dll** | `windows/x64/org/lwjgl/` | x86-64 | 479,232 | `d1fa2f0a1c13bc30...` | KERNEL32 | **LWJGL:** Core LWJGL JNI dispatcher and pointer management |
| **lwjgl_opengl.dll** | `windows/x64/org/lwjgl/opengl/` | x86-64 | 364,032 | `6ce6bbaf9278971f...` | KERNEL32 | **LWJGL:** OpenGL function pointer binding table |
| **lwjgl_opengles.dll** | `windows/x64/org/lwjgl/opengles/` | x86-64 | 212,992 | `70868ee4a93883a9...` | KERNEL32 | **LWJGL:** OpenGLES function pointer binding table |
| **lwjgl_stb.dll** | `windows/x64/org/lwjgl/stb/` | x86-64 | 510,464 | `36c4bfe81d86e92b...` | KERNEL32 | **Graphics/Audio:** stb_image, stb_truetype, stb_vorbis |
| **lwjgl_tinyfd.dll** | `windows/x64/org/lwjgl/tinyfd/` | x86-64 | 251,904 | `ec7d76e6ef7a9962...` | KERNEL32, USER32, COMDLG32, SHELL32, OLE32 | **UI:** Native file picker, color chooser, message box dialogs |
| **gdx64.dll** | `gdx64.dll` | x86-64 | 130,280 | `ff664855fa81e7a1...` | KERNEL32, msvcrt | **LibGDX:** Core JNI utilities, matrix multiplication, fast math |
| **gdx-freetype64.dll** | `gdx-freetype64.dll` | x86-64 | 741,926 | `385cee2b55ec2046...` | KERNEL32, msvcrt | **LibGDX:** FreeType 2 vector font rasterizer JNI wrapper |

*Note: The JAR also packages complete `windows/arm64/...` binaries for Windows on ARM, as well as `com/sun/jna/darwin-aarch64/` and `darwin-x86-64/` `.jnilib` binaries for macOS.*

---

## 3. Deep-Dive: WinMultitouch64.dll (Touch Digitizer Integration)

- **Class Binding:** `org.devcore.touch.win.WinMultitouch`
- **CPU Architecture:** x86-64
- **Exports:**
  - `Java_org_devcore_touch_win_WinMultitouch_initTouch`
  - `Java_org_devcore_touch_win_WinMultitouch_dispose`
- **Imports:** `USER32.dll`, `KERNEL32.dll`
- **Mechanism:**
  - `initTouch(long windowHandle)` registers the GLFW native HWND with Windows Touch API (`RegisterTouchWindow` or `RegisterPointerDeviceNotifications`).
  - Hooks the Win32 window message procedure (`WndProc`) to intercept `WM_TOUCH` / `WM_POINTERUPDATE` events before standard Windows mouse emulation can compress or serialize them.
  - Passes raw pointer coordinates ($X, Y$), contact ID, and pressure back to the Java layer via JNI callback `nativeOnTouchCallback(JIIIII)V`.
  - Enables true 10-finger multi-touch fader adjustment on multi-touch touchscreen consoles.

---

## 4. JNA (Java Native Access) Usage Analysis

The application bundles JNA 5.13.x (`com.sun.jna`, `jnidispatch.dll`).

### JNA Call Targets:
1. **Auto-Updater Windows Execution:**
   - Class: `org.devcore.mixingstation.gdx.desktop.update.f$a`
   - Invocation: `ShellExecuteA(HWND, "open", installerPath, params, workDir, SW_SHOWNORMAL)`
   - Purpose: Spawns the MSI installer or elevated updater process outside the JVM sandbox.
2. **Hardware Diagnostic Information:**
   - Package: `oshi.hardware.platform.windows.*`, `com.sun.jna.platform.win32.*`
   - Purpose: Queries Windows WMI, kernel performance counters, and network adapters (`NicsDto`).
3. **UPDD Touch Daemon Interface:**
   - Class: `org.devcore.touchbase.TouchBaseApi`
   - Purpose: Dynamic binding to `/Library/Application Support/UPDD` or Windows touch services.

---

## 5. Bundled OpenJDK Runtime Libraries (`runtime\bin\*`)

The application bundles an optimized OpenJDK 25.0.1 runtime:

### 5.1 JVM Engine
- **File:** `runtime\bin\server\jvm.dll` (15,423,656 bytes, SHA-256 `94fa72cd9d66ddce...`)
- **Version:** OpenJDK 25.0.1+8-LTS (Eclipse Adoptium)
- **Exports:** `JNI_CreateJavaVM`, `JNI_GetCreatedJavaVMs`, `JNI_GetDefaultJavaVMInitArgs`, JVM diagnostic entry points.

### 5.2 Java Platform Native Libraries
- `awt.dll` (1,419,432 bytes): Native desktop GUI plumbing, clipboard, drag-and-drop.
- `fontmanager.dll` (963,752 bytes): GDI / DirectWrite font enumeration.
- `freetype.dll` (546,984 bytes): Java desktop FreeType implementation.
- `jsound.dll` (61,096 bytes): Windows Multimedia (`winmm.dll`) MIDI and audio routing for `javax.sound.midi`.
- `net.dll` (61,096 bytes) & `nio.dll` (81,576 bytes): Winsock (`ws2_32.dll`) asynchronous socket I/O.
- `syslookup.dll` (28,840 bytes): Java 25 Foreign Function & Memory (FFM) system lookup.

### 5.3 Microsoft Visual C++ Redistributable (Bundled)
- `ucrtbase.dll` (1,361,448 bytes)
- `msvcp140.dll` (575,056 bytes)
- `vcruntime140.dll` (119,888 bytes)
- `vcruntime140_1.dll` (49,640 bytes)
- 32 Windows CRT API forwarding stubs (`api-ms-win-core-*.dll`, `api-ms-win-crt-*.dll`).
- **Significance:** Eliminates external MSVC redistributable installation prerequisites; the application runs out-of-the-box on clean Windows installations.
