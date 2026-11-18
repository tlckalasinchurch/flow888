# Phase 3: Behringer FLOW 8 Connection & Synchronization Workflow

**Document ID:** `FLOW8_CONNECTION_WORKFLOW`  
**Interface:** Windows Multimedia API (`winmm.dll`)  
**Status:** SPECIFIED & VERIFIED

---

## 1. Connection Life Cycle

```mermaid
sequenceDiagram
    participant User as Sound Engineer
    participant UI as Flow8App UI
    participant Service as Flow8Service
    participant MidiOut as Flow8MidiOut
    participant MidiIn as Flow8MidiIn
    participant HW as Behringer FLOW 8

    User->>UI: Launch Application
    UI->>Service: start()
    Service->>MidiOut: Enumerate Ports (midiOutGetDevCapsW)
    Service->>MidiIn: Enumerate Ports (midiInGetDevCapsW)
    
    alt FLOW 8 Detected
        MidiOut-->>Service: Port ID (e.g. 1, "FLOW 8 MIDI OUT [0]")
        MidiIn-->>Service: Port ID (e.g. 1, "FLOW 8 MIDI IN [0]")
        Service->>MidiOut: open(deviceId)
        Service->>MidiIn: open(deviceId) + start()
        Service-->>UI: ConnectionState.CONNECTED
        UI-->>User: Green "FLOW 8 CONNECTED" badge
    else FLOW 8 Not Detected
        Service-->>UI: ConnectionState.DISCONNECTED
        UI-->>User: Amber "FLOW 8 OFFLINE (Simulated / Standby)"
        Service->>Service: Start 2.5s Polling Watchdog
    end

    Note over User,HW: Real-Time Operational Loop
    User->>UI: Adjusts Fader to -6 dB
    UI->>Service: set_fader(channel=1, db=-6.0)
    Service->>MidiOut: send_cc(ch=1, cc=7, val=102)
    MidiOut->>HW: 0xB0 0x07 0x66
    HW-->>HW: Motor/DSP Updates

    Note over HW,UI: Hardware Knob Turned on Console
    HW->>MidiIn: 0xB0 0x01 0x48 (EQ Low tweaked)
    MidiIn->>Service: on_midi_in(ch=1, cc=1, val=72)
    Service->>UI: update_channel_state(ch=1, eq_low=+2.0 dB)
    UI-->>User: Dial rotates smoothly on screen

    Note over HW,Service: Disconnection / Cable Pull Handling
    HW--xMidiOut: USB unplugged (MMSYSERR_NODRIVER)
    MidiOut-->>Service: Flow8MidiError("Endpoint lost")
    Service->>MidiIn: close()
    Service->>MidiOut: close()
    Service-->>UI: ConnectionState.DISCONNECTED
    UI-->>User: Red "DISCONNECTED — Check USB Cable"
    Service->>Service: Engage auto-reconnect retry loop
```

---

## 2. Reconnection & Recovery Resilience

1. **Watchdog Thread:** `Flow8Service` runs a lightweight non-blocking background thread checking connection status every 2.5 seconds.
2. **Graceful Fail-Safe:** When a USB connection drops or a cable is disconnected during a live performance:
   - All outgoing commands fail safely with an exception intercepted by `Flow8CommandBoundary`.
   - The UI does not crash or hang.
   - The UI displays an amber/red disconnection indicator.
   - The application preserves in-memory mixer state so that upon reconnection, the engineer's work is not lost.
3. **Auto-Rebind:** When the mixer is re-plugged or powered on, the watchdog detects the endpoint and reopens both MIDI OUT and MIDI IN without requiring an application restart.
