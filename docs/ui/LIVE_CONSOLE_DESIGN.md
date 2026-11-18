# FLOW 8 Live Console — LAN remote UI design

Status: implemented in `flow8/web_ui/` and `flow8/lan_hub.py`.
Scope: the browser remote served by the LAN hub (desktop, iPad, phone).

## 1. Requirements

### Functional

1. Show live state in real time, from real sources only. Never show a value or a lamp that the system cannot back with data.
2. Look and behave like a professional live console, so an engineer can read it at a glance during a show.
3. Protect the mix against stray touches during a show.
4. Keep every existing safety rule: no preamp gain and no +48 V over LAN, and no command while MIDI is closed.

### Non-functional

| Item | Target |
|---|---|
| Lamp latency (hub event to lamp) | < 1 frame after the SSE event arrives (~16 ms) |
| Lamp flash length | 220 ms, so a single event is visible |
| Meter frame rate | ≤ 30 frames/s per client (hub rate limit) |
| Re-render during a drag | none; reloads wait for pointer release |
| Works offline at a venue | yes; the font is bundled and served by the hub |
| Touch targets | ≥ 44 px on coarse pointers (36 px for the rename key) |

### Constraints

- The FLOW 8 sends **no meter data over USB MIDI** (see `FLOW8_AUDIO_ENGINE_SPEC.md` §2.3). Meters come from the USB audio capture stream (`flow8/audio_meter.py`, section 4a).
- MIDI IN reports some hardware moves (faders, mute, pan, bus faders). The mixer does not echo commands back.
- No build step. The page is plain HTML, CSS and JS served from the hub.

## 2. Reference: what top consoles do

These patterns are common to the three large live-console families (Yamaha CL/DM7 with StageMix, Allen & Heath dLive/SQ with MixPad, DiGiCo SD/Quantum):

| Pattern on large consoles | Adopted here | Notes |
|---|---|---|
| Colour LCD scribble strip per channel | Yes | Backlit LCD look: channel colour as backlight, dark ink |
| Signal / peak / clip LEDs and meter beside the fader | Yes, gated | Shown only while a measured meter feed is live |
| Per-channel processing overview (mini EQ) | Yes | Drawn from the known EQ band values |
| Sends on faders with a colour tint for the mix | Yes | Bank edge and caps take the MON/FX colour |
| Scene display with an "edited" marker | Yes | Hub tracks the current scene and changes after it |
| Panel / surface lock | Yes | Tap to lock, hold 0.8 s to unlock |
| Clock in the status bar | Yes | Local time on the device |
| Network / link status lamps | Yes | USB, MIDI IN, HUB, RX, METERS |
| Solo / PFL, DCA, mute groups | No | The FLOW 8 MIDI map does not expose them |
| Gain-reduction meter | No | Needs compressor telemetry the mixer does not send |

## 3. High-level design

```
 FLOW 8 ──USB MIDI──▶ Flow8Service ──listener──▶ Flow8LanHub ──SSE──▶ browser(s)
   ▲                      ▲                          │   ▲
   └──── commands ────────┘◀── POST /api/action ─────┘   │
                                                         │
 (future) USB audio ─▶ audio engine ─▶ hub.publish_meters()
```

### Event contract (`GET /api/events`, Server-Sent Events)

| `type` | Source | Payload | Browser action |
|---|---|---|---|
| `connected` | hub | `clientId` | none |
| `rx` | MIDI IN (hardware move) | `paramId`, `value` | RX lamp of that strip; reload |
| `tx` | accepted `/api/action` | `action`, `channel`, `bus`, `target` | TX lamp of that strip; reload |
| `state` | service state change (undo, preset) | — | reload |
| `link` | MIDI connect/disconnect reconcile | — | reload |
| `meters` | `hub.publish_meters()` only | `levels: {strip: {peak, rms}}` dBFS | meters; no reload |

Strip ids: `ch1`…`ch7`, `main`, `mon1`, `mon2`, `fx1`, `fx2`.

### Session fields added (`GET /api/session`)

`midiOutOpen`, `midiInOpen`, `meterFeed`, `currentScene`, `sceneEdited`.

## 4. Deep dive

### Lamps per strip

| Lamp | Colour | Lit when |
|---|---|---|
| RX | amber, flash | the mixer reported a change on this strip |
| TX | blue, flash | a command for this strip was accepted (from any client) |
| Source | steady | green: value reported by the mixer (OBSERVED); blue: value sent by this app (COMMANDED); red: last command failed; dark: unknown (UNSYNCED) |

Lamp timestamps live in a JS map, not in the DOM. One `requestAnimationFrame` loop applies them. A re-render therefore never drops a flash.

### Meters

- The hub never creates levels. `publish_meters()` accepts levels measured from audio only.
- Rate limit: one SSE frame per 33 ms. A full client queue drops meter frames but keeps the client. Any other event on a full queue disconnects the client, so it reloads its state.
- The feed counts as live while frames arrive within 2 s. Without a live feed, meters are hidden and the METERS lamp is dark.
- Scale: 0 dBFS at the top, −60 dBFS at the bottom. Peak hold 1.5 s. Clip lamp at ≥ −0.5 dBFS, held 1.5 s.

### Scene tracking

- `captureScene` or `recallScene` sets the current scene and clears "edited".
- Any accepted mix action, or a hardware move, sets "edited" while a scene is current.
- Renaming a channel does not change the mix, so it does not set "edited".

### Re-render policy

- SSE events schedule one reload, 120 ms after the last event.
- While a pointer holds a fader, knob, EQ canvas or send slider, reloads wait. The reload runs after release.
- Keyboard focus is restored after each re-render through `data-focus-key`.

## 4a. Meter source: USB audio capture (`flow8/audio_meter.py`)

### Capture map (Recording Mode, endpoint "Multi In 1-10", `FLOW8_USB_AUDIO_CAPABILITIES.md` §4)

| Capture channel (0-based) | FLOW 8 input | Strip | Meter |
|---|---|---|---|
| 0 | Mic 1 | ch1 | input, before the fader |
| 1 | Mic 2 | ch2 | input, before the fader |
| 2 | Mic/Line 3 | ch3 | input, before the fader |
| 3 | Mic/Line 4 | ch4 | input, before the fader |
| 4, 5 | Line 5/6 | ch5 | louder side of the pair |
| 6, 7 | Line 7/8 | ch6 | louder side of the pair |
| 8, 9 | Main L/R | main | main mix |
| — | USB/BT return | ch7 | none (not in the capture) |
| — | MON 1/2, FX 1/2 | buses | none (not in the capture) |

Streaming Mode exposes only a 2-channel main mix. The module then meters `main` only and says so in the status.

The input meters are **before the fader**: moving a fader does not move its meter. This matches a console's input meter.

### Pipeline

```
FLOW 8 USB ─▶ PortAudio (WASAPI) ─▶ audio callback ─▶ LevelMeter.process()   (audio thread: numbers only)
                                                         │
                         publisher thread, 25 Hz ◀───────┘  LevelMeter.read()
                                     │
                                     ▼
                           hub.publish_meters() ─▶ SSE "meters" ─▶ browsers
```

- Block size 512 frames (~10.7 ms at 48 kHz), float32.
- Peak: largest sample since the last read, so a transient between two reads is not lost.
- RMS: exponential smoothing, 300 ms time constant.
- Device choice: a FLOW 8 endpoint with 10 inputs, preferring WASAPI; else a 2-input FLOW 8 endpoint (Streaming Mode).
- Status (`/api/status` and `/api/session` → `meterStatus`): `running`, `no_device`, `unavailable` (no audio library), `error`, `stopped`, with a plain-language `detail`. The METERS lamp tooltip shows it.
- Recovery: the launchers call `ensure_running()` in their loop; it retries every 5 s, so meters start when the FLOW 8 is plugged in later. A stream the driver stops (cable pulled) is closed and reported as `error`, then retried.

### Setup on the host computer

```
pip install sounddevice numpy
```

`sounddevice` bundles PortAudio on Windows. Set the FLOW 8 to Recording Mode on the mixer. Start with `python launch_studio_ui.py` (or `python -m flow8.lan_hub`). Add `--no-meters` to run without the audio stream.

Only one program at a time may hold some WASAPI endpoints in exclusive mode. If a DAW holds "Multi In 1-10" exclusively, the meter status shows `error` with the driver message.

## 5. Visual system

| Token | Value | Use |
|---|---|---|
| Chassis | `#16181C` | page background (anodized graphite) |
| Panel | `#1C1F24` | rack cards, strips |
| Key | `#34383F → #2A2D33` | rubber keys |
| LED green / amber / red / blue | `#3BE36F` / `#FFB020` / `#FF3B30` / `#4FA8FF` | lamps, readouts |
| LCD ink | `#0D1014` | text on the backlit scribble strips |

Type: Barlow Condensed 500/600/700 (SIL OFL 1.1, bundled in `web_ui/fonts/`). Condensed silkscreen-style legends fit narrow strips. Readouts use tabular numerals.

Principle: the backlit scribble strips and the LED lenses carry the identity. The panel stays flat graphite. Only a lit LED glows.

## 6. Trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| Hide meters without a feed | Never shows a fake level | No meters until an audio engine exists |
| Full re-render on reload (no diffing) | Simple, one source of truth | Needs the drag guard and focus restore |
| Client-side panel lock | Instant, works offline | Each device locks on its own |
| SSE, not WebSocket | Standard library only, auto-reconnect | One direction; commands use POST |
| Bundled font | Works without internet at a venue | +~60 KB served by the hub |

## 7. Revisit as the system grows

1. **Hardware check of the meter module:** confirm the PortAudio device name and channel order on the real FLOW 8, and compare the meter readings with the mixer's own LEDs. The module has only been tested with a simulated audio backend.
2. **Incremental rendering:** update only the strips that changed, when more clients or more frequent RX events make full re-renders expensive.
3. **Hub-wide lock:** one lock for all clients, if the venue uses several tablets.
4. **Scene names:** user-defined scene names in the scene display.
