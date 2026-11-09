# REA Phase 3 — Java Package Map
**Target:** Mixing Station PC Windows 3.2.2 Build 789  
**Application JAR:** `mixing-station-desktop.jar`  
**JAR SHA-256:** `83094b1e41cb51af7a94b076f4b71cf45a7fb35de45a32565797c52cc277caad`  
**Total Classes:** 13,549  
**Distinct Packages:** 1,398  
**Analysis Date:** 2026-11-09  

---

## 1. Top-Level Package Distribution

| Root Namespace | Class Count | Primary Purpose | Classification |
|---|---|---|---|
| `blob.*` | 8,776 | Obfuscated Core Application Logic (Mixer drivers, DSP models, UI widgets, Routing, Scenes) | Core Proprietary (Obfuscated) |
| `com.*` | 2,125 | Runtime Frameworks (JNA `com.sun.jna`, LibGDX `com.badlogic.gdx`, Jackson `com.fasterxml`, Google Protobuf `com.google.protobuf`) | Third-Party Runtime |
| `org.*` | 1,917 | Embedded Web Server (`org.eclipse.jetty`), Native Windowing (`org.lwjgl`), Logging (`org.slf4j`), and App Entry (`org.devcore`) | Mixed (Vendor + Third-Party) |
| `oshi.*` | 569 | Operating System and Hardware Information library (`oshi.hardware`, `oshi.driver`, `oshi.software`) | Third-Party Diagnostics |
| `serialisation.*` | 96 | Compiled Google Protocol Buffers IPC/Network Schemas | Vendor Schema (Unobfuscated) |
| `io.*` | 66 | OpenAPI / Swagger Metadata (`io.swagger`) | Third-Party API Specs |

---

## 2. Vendor Unobfuscated Packages (`org.devcore.*`)

The `org.devcore` root contains 48 unobfuscated classes maintaining public interfaces, native bindings, DTOs, and application bootstrapping.

| Package | Classes | Key Classes | Architectural Function | Confidence |
|---|---|---|---|---|
| `org.devcore.mixingstation.gdx.desktop` | 11 | `MsDesktopLauncher`, `Selftest`, `a`, `b`, `c`, `d`, `e`, `f`, `g` | Desktop entry point, CLI parser, LibGDX backend bootstrap, scheme handler (`mixingstation://`) | VERIFIED |
| `org.devcore.mixingstation.gdx.desktop.update` | 9 | `Updater`, `a`, `b`, `c`, `d`, `e`, `f` | Application auto-update engine, temporary directory installer spawner, Windows ShellExecute | VERIFIED |
| `org.devcore.mixingstation.api.dto.network` | 12 | `ConsoleListDto`, `ConnectToMixerDto`, `ConsoleConnectDto`, `StartMixerSearchDto`, `StartOfflineModeDto`, `NicsDto` | REST/WebSocket JSON DTOs for mixer discovery, connection, NIC selection, offline simulation | VERIFIED |
| `org.devcore.touch.win` | 1 | `WinMultitouch` | Win32 native multi-touch event capture (`WM_TOUCH`/`WM_POINTER`) via `WinMultitouch64.dll` | VERIFIED |
| `org.devcore.touch.linux` | 1 | `X11Multitouch` | Linux X11 multi-touch XI2 event capture | VERIFIED |
| `org.devcore.touchbase` | 2 | `TouchBaseApi`, `a` | UPDD (Universal Pointer Device Driver) macOS daemon connector | VERIFIED |
| `org.devcore.coremidi.macos` | 9 | `MacOsCoreMidiClient`, `CoreMidiApi`, `MidiEndpoint`, `MidiEntity`, `MidiObject`, `MidiPort` | Apple CoreMIDI client integration via native JNA dispatcher | VERIFIED |
| `org.devcore.macos` | 3 | `MacosUtils`, `a`, `b` | macOS native integration and URL scheme listener | VERIFIED |

---

## 3. Serialization Layer (`serialisation.*`)

Compiled Google Protocol Buffers (proto3) message descriptors used for high-frequency state updates, metering streams, automation, and UI parameter synchronization:

| Class Name | Enclosing Outer Class | Functional Role |
|---|---|---|
| `ActionEventOuterClass` | `ActionEvent` | User interaction and UI control events |
| `AutomationEventOuterClass` | `AutomationEvent` | Automation cues, fader moves, and timed triggers |
| `ConsoleValueOuterClass` | `ConsoleValue`, `ConsoleValueList`, `ConsoleValueMap` | Universal mixer parameter value container (scalar, list, dictionary) |
| `DebugEventOuterClass` | `DebugEvent` | Diagnostic and protocol debug tracing |
| `EventOuterClass` | `Event` | Top-level multiplexed IPC/network event envelope |
| `KeyOuterClass` | `Key`, `SubKey` | Hierarchical mixer parameter addressing keys |
| `MeterIndexEventOuterClass` | `MeterIndexEvent`, `MeterIndex` | Meter subscription index mappings (channel, bus, aux, matrix) |
| `MeterIndexRequestOuterClass` | `MeterIndexRequest` | Client meter stream registration request |
| `ParameterEventOuterClass` | `ParameterEvent` | State push notification for modified console parameter |
| `ParameterOuterClass` | `Parameter` | Single parameter definition with min/max/default/step |
| `ParameterRequestOuterClass` | `ParameterRequest`, `Identifier`, `Subscribe`, `Unsubscribe` | Parameter subscription/unsubscription lifecycle requests |
| `VersionEventOuterClass` | `VersionEvent` | Protocol and firmware version handshake event |
| `VersionRequestOuterClass` | `VersionRequest` | Protocol version query request |

---

## 4. De-Obfuscated Core Package Map (`blob.*`)

Through constant pool string extraction, inheritance graphs, and method call topology, the flattened `blob.*` packages have been classified into their actual architectural subsystems:

### 4.1 Mixer Platform Implementations

| Subpackage | Class Count | Target Mixer Hardware | Protocol / Transport Evidence | Confidence |
|---|---|---|---|---|
| `blob.ab.*` | 132 | **Behringer WING** | OSC over UDP, `/Meters`, `/Meters/values`, WLive, routing, 60+ FX modules | VERIFIED |
| `blob.pb.*` | 111 | **Behringer X32 / Midas M32** | OSC over UDP, `/xremote`, `/meters`, 100+ FX, channels, routing | VERIFIED |
| `blob.rb.*`, `blob.qb.*` | 71 | **Behringer X-Air** (XR12, XR16, XR18, X18) | OSC over UDP, `/xremotenfb`, parameter batching | VERIFIED |
| `blob.jm.*` | 24 | **Allen & Heath Qu** (Qu-16, Qu-24, Qu-32, Qu-Pac) | A&H binary protocol, dSnake, preamp control, quConType | VERIFIED |
| `blob.lp.*` | 27 | **Allen & Heath SQ** (SQ-5, SQ-6, SQ-7) | A&H MIDI/TCP protocol, `#chName/`, `#chCol/` | VERIFIED |
| `blob.hy.*` | 31 | **Allen & Heath dLive / Avantis** | A&H dLive TCP/IP protocol, channel/mixer config change | VERIFIED |
| `blob.ud.*`, `blob.ue.*`, `blob.vq.*` | 45 | **Soundcraft Ui** (Ui12, Ui16, Ui24R) | HTTP REST + WebSocket protocol, RTA, VU2 stream | VERIFIED |
| `blob.sv.*`, `blob.ut.*` | 19 | **Soundcraft Vi** (Vi1 - Vi7000) | Soundcraft HiQnet / Harman proprietary TCP protocol | VERIFIED |
| `blob.wd.*` | 7 | **Yamaha CL / QL** (CL1/3/5, QL1/5) | Yamaha SCP protocol, `presets/yamaha/cl-map.bin`, SCENE | VERIFIED |
| `blob.ws.*`, `blob.ye.*`, `blob.yf.*` | 15 | **Yamaha TF** (TF1, TF3, TF5, TF-RACK) | Yamaha SCP multicast discovery `239.192.0.164`, `_ypax-tf` | VERIFIED |
| `blob.wx.*`, `blob.xd.*`, `blob.xr.*` | 21 | **Yamaha DM3 / DM7** (DM3, DM3S, DM7, DM7C) | Yamaha SCP multicast `_ypax-dm`, `RequestMeter` unicast 50ms | VERIFIED |
| `blob.se.*`, `blob.sc.*` | 35 | **PreSonus StudioLive** (Series III) | StudioLive UCNET / TCP protocol, Fat Channel plugins | VERIFIED |
| `blob.mq.*` | 18 | **Mackie DL** (DL1608, DL32R) | Mackie DL Master Fader TCP protocol, `/monitor-aux/` | VERIFIED |
| `blob.oi.*`, `blob.oh.*` | 16 | **Midas Pro / Heritage D** | Midas HD96 protocol, `PopGrp`, `POP` VCA navigation | VERIFIED |

### 4.2 Application Core Subsystems

| Subpackage Group | Classes | Architectural Subsystem | Evidence & Signatures |
|---|---|---|---|
| `blob.abi.*` | 12 | **Mixer Connection Base** | Abstract base `blob.abi.b`, connection heartbeat watchdog, reconnect loop |
| `blob.aoe.*`, `blob.apq.*` | 25 | **Remote Mix ("Anywhere")** | Tunnel agent client, OAuth2 token handling, remote WebSocket proxy |
| `blob.apw.*` | 30 | **REST & WebSocket API** | Embedded HTTP API server, `/console/metering/`, `/console/metering2/` |
| `blob.abc.*`, `blob.ang.*`, `blob.ani.*` | 42 | **Hardware MIDI / Controllers** | Mackie Control (MCU), Behringer X-Touch, PreSonus Faderport, HUI, Java Sound MIDI |
| `blob.ade.*`, `blob.adl.*`, `blob.ajs.*`, `blob.akm.*` | 48 | **Scene / Cue / Snippet Engine** | Offline scene storage, scene recall, snippet scopes, cue list automation |
| `blob.ael.*`, `blob.ajf.*`, `blob.akj.*` | 43 | **Routing Matrix** | Patch bay routing, batch routing confirmation, physical I/O mapping |
| `blob.afe.*`, `blob.afw.*`, `blob.aua.*` | 45 | **RTA / FFT & Audio Capture** | Real-Time Analyzer rendering, OpenAL microphone capture, peak detection |
| `blob.abv.*`, `blob.acq.*`, `blob.aga.*` | 55 | **Configuration & Persistence** | `globalSettings.dson`, `layouts.json`, `midiMap.json`, channel strip configs |
| `blob.c.*`, `blob.atb.*`, `blob.acp.*` | 120 | **UI Presentation Framework** | LibGDX custom Scene2D actors, faders, knobs, meters, responsive layouts |
| `blob.da.*`, `blob.ec.*`, `blob.fo.*`, `blob.fe.*` | 71 | **DSP Modeling & Dynamics Curves** | Parametric EQ curves, compressor transfer curves, gate threshold diagrams |

---

## 5. Third-Party Library Inventory

| Library | Package Root | Version | Role in Application |
|---|---|---|---|
| **LibGDX** | `com.badlogic.gdx` | 1.12.x | 2D OpenGL ES rendering, Scene2D graph, Pixmap manipulation, FreeType |
| **LWJGL 3** | `org.lwjgl` | 3.3.x | Low-level C bindings for GLFW, jemalloc, OpenAL, OpenGL, STB, TinyFD |
| **Google ANGLE** | Native DLLs | Embedded | Direct3D 11 translation for OpenGL ES 2.0/3.0 on Windows |
| **Eclipse Jetty** | `org.eclipse.jetty` | 10.0.x / 11.0.x | Embedded HTTP/1.1 servlet engine, WebSocket server, REST API endpoints |
| **JNA** | `com.sun.jna` | 5.13.x | Java Native Access FFI binding to Win32, Cocoa, X11, CoreMIDI |
| **OSHI** | `oshi` | 6.4.x | Hardware CPU/RAM monitoring, network adapter detection (`NicsDto`) |
| **Google Protobuf** | `com.google.protobuf` | 3.21.x | Binary serialization of internal state and network communications |
| **Jackson** | `com.fasterxml.jackson` | 2.15.x | High-performance JSON parser for presets, settings, and REST DTOs |
| **SLF4J** | `org.slf4j` | 2.0.x | Structured logging abstraction |
