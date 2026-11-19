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

`midiOutOpen`, `midiInOpen`, `meterFeed`, `meterStatus`, `currentScene`, `sceneEdited`. Inspector fields: section 4b.

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

## 4b. Layout: fader bank + Inspector

The FLOW 8 app opens a full-screen page for each channel and returns with `< BACK`. This UI keeps the fader bank on screen and opens the settings in an Inspector beside it.

### Fader bank

| Item | Behaviour |
|---|---|
| Strips | `MIC 1`, `MIC 2`, `COMBO 3`, `COMBO 4`, `LINE 5/6`, `LINE 7/8`, `USB/BT` (blue LCD and blue top edge), then one master strip |
| Master strip | Follows the bus selector: `MAIN`, `MON 1`, `MON 2`, `FX 1` or `FX 2`. Its fader sends `main.fader` or `<bus>.fader` |
| Sends on faders | On a MON or FX mix the input faders set the sends to that bus |
| Mix colour | The mix bar on top of each strip, the fader cap line, the fader fill and the readout use the mix colour: MAIN silver `#E6E8EB`, MON emerald `#34D399`, FX violet `#A78BFA` |
| Meters | Unchanged (section 4a): pre-fader, only where a capture channel exists |

### Opening the Inspector

| Action | Result |
|---|---|
| Tap a strip header (LCD) | Inspector for that channel |
| Tap the master strip header | Inspector for the selected bus |
| Tap a bus tab | That mix goes on the faders. A bus Inspector that is open follows it |
| Tap the active bus tab | Opens or closes that bus Inspector |
| `‹` / `›` in the Inspector | Step CH 1 … CH 7, MAIN, MON 1, MON 2, FX 1, FX 2 |
| Escape or `✕` | Close; focus goes back to the strip header |

| Width | Inspector |
|---|---|
| ≥ 1000 px | Split pane (400 px, 360 px at ≤ 1180 px). All 8 strips stay visible at 1024 px |
| 761–999 px | Slides over the right side of the bank |
| ≤ 760 px | Bottom sheet, 54 % of the height. Strips keep name, mute and fader above it |

### Inspector contents and what each control can send

LIVE: the control sends a verified command. LOCKED: shown with a reason from `session.locked`, sends nothing.

| Target | Control | State |
|---|---|---|
| CH 1–7 | MUTE, RENAME, PRESETS | LIVE |
| CH 1–7 | SOLO | LOCKED: CC 6 is not on the allowlist |
| CH 1–4 | GAIN | LOCKED: host-only (SR-05). Shows the value the mixer reports |
| CH 1–2 | +48V | LOCKED: host-only. Shows the reported state. The key has hold-to-toggle (1 s); it works only when `lanPolicy.phantom` is true, and the hub keeps it false |
| CH 1–4 | LOW CUT (20–600 Hz), COMP (0–100 %) | LIVE |
| CH 1–7 | PAN (CH 1–4) / BALANCE (CH 5–7) | LIVE |
| CH 1–7 | 4-band EQ: knobs + draggable curve, FLAT | LIVE. Labels 100 Hz / 500 Hz / 2 kHz / 12 kHz come from the FLOW 8 app; the curve is approximate (conflict C-04) |
| CH 1–7 | Sends MON 1, MON 2, FX 1, FX 2 | LIVE |
| MAIN | LEVEL, BALANCE | LIVE |
| MAIN, MON 1, MON 2 | LEVEL | LIVE |
| MAIN, MON 1, MON 2 | LIMITER, 9-band GEQ (63 Hz … 16 kHz) | LOCKED: CC 8 and CC 11–19 are documented but not hardware-verified |
| FX 1, FX 2 | RETURN LEVEL | LIVE |
| FX 1, FX 2 | DECAY / FEEDBACK, INSTRUMENT·VOCAL / DULL·BRIGHT, TAP TEMPO, presets No. 1–16 | LOCKED: conflict C-09. Tap tempo uses MIDI channel 16, which also carries the forbidden reset (Program Change 16) |

To unlock a feature: verify its address on the hardware, add it to `command_boundary.ACTIVE_ALLOWLIST`, add a hub action, and remove it from `LAN_LOCKED_FEATURES`. The Inspector then needs only a change from `locked:` to `onCommit:` for that control.

### Session fields added for the Inspector

Per channel: `lowCutProvenance`, `compressorProvenance`, `gain` (raw or `null`), `gainProvenance`, `phantom` (`true`/`false`/`null`), `phantomProvenance`. Top level: `lanPolicy` (`{"gain": false, "phantom": false}`) and `locked` (feature → reason).

## 4c. Views, setup pages and snapshots

### Views

| Control | Result |
|---|---|
| `MIXER` | Fader bank + Inspector (section 4b) |
| `STAGE` | 7 large level knobs (`MIC 1` … `USB/BT`) for the mix on the faders, a MUTE key under each, and an FX 2 `TAP TEMPO` pad. An outer ring around each knob shows the live pre-fader level (green, amber above −6 dBFS, red on clip). `USB/BT` has no ring (no capture channel) |
| `SNAPSHOTS` | Setup view, MIXER SNAPSHOTS page |
| `SETUP` | Setup view: CONFIGURE INPUTS, MIXER SNAPSHOTS, SNAPSHOT LIBRARY, PREFERENCES, ROUTING, INFO. `✕` or Escape returns to the last view |

### Setup pages and what each control can send

| Page | Live | Locked (reason key in `session.locked`) |
|---|---|---|
| CONFIGURE INPUTS | Per-jack meters and signal lamps (`ch1`–`ch4`, `in5`–`in8` from the USB capture) | +48V (`phantom`, hold-to-toggle ready), STEREO/MONO (`stereoLink`). Hi-Z on Line 6 and 8 is a label |
| MIXER SNAPSHOTS | 15 hub snapshot slots: tap recall, hold save. WHAT TO LOAD: CH, FX, MAIN, MON | ROUT (`routing`), RESET (`hwSnapshots`) |
| SNAPSHOT LIBRARY | NEW, LOAD (asks first), UPDATE, RENAME, DELETE (asks first), search, sort by date or A–Z, IMPORT and EXPORT JSON | — |
| PREFERENCES | DISPLAY DECIBEL, FINER SLIDERS (this device only, `localStorage`) | FULL PARAMETRIC (`eqParametric`), −10 dBV pads (`outputPad`), foot switch mode (`footswitch`) |
| ROUTING | USB audio mode, read from the USB device | All routing options (`routing`) |
| INFO | MIDI, meter and library state; LAN addresses | — |

FINER SLIDERS (or Shift on a desktop): a fader moves from its cap at one quarter of the finger travel instead of jumping to the finger; knobs turn at one quarter speed.

### Snapshot model

| Tier | Where it lives | Slots | Content |
|---|---|---|---|
| Mixer snapshots | Hub memory (`Flow8Service.scenes`, `SCENE_CAPACITY = 15`) | `SCENE 1` … `SCENE 15`, shown 01–15 | Known values only: inputs 1–7 (fader, pan, mute, EQ, low cut, comp, sends), Main fader and balance, MON/FX bus faders |
| Snapshot library | `~/.flow8/snapshot_library.json` on the host (`--library PATH` to change) | Up to 500 named entries | Same values, plus name and dates |

These are not the FLOW 8's own snapshot memories. Those recall by Program Change on MIDI channel 16, where Program Change 16 resets the mixer; the hub sends nothing on channel 16.

Recall scope (`recall_scope_of`): `CH` = input values except sends; `MON` = sends to MON 1/2 and the MON bus faders; `FX` = sends to FX 1/2 and the FX bus faders; `MAIN` = Main fader and balance. A recall or library load is one undo step. A partial recall shows the scene as EDITED. Gain and +48V are never stored, and the library import refuses them.

Library file format `flow8-snapshot-library-v1`:

```json
{"format": "flow8-snapshot-library-v1",
 "snapshots": [{"id": "…", "name": "Pastor", "createdAt": "…", "updatedAt": "…",
                "parameters": {"1": {"fader": 90, "mute": false}, "8": {"fader": 101}, "mon1": {"fader": 80}}}]}
```

Import checks every value (channel 1–8 or bus id, allowed parameter, integer 0–127, mute true/false). Invalid entries are skipped and counted. The hub refuses request bodies over 1 MB. The file is written atomically.

### Hub API added

| Call | Purpose |
|---|---|
| `recallScene {name, scope?}` | Scope: list of `CH`, `FX`, `MAIN`, `MON`; omitted = all |
| `librarySave {name, id?}` | New entry from the known mix, or overwrite `id` |
| `libraryLoad {id, scope?}` | Send an entry (needs the mixer) |
| `libraryRename`, `libraryDelete`, `libraryImport {data}` | Library edits; allowed while the mixer is disconnected |
| `GET /api/library/export` | Download the library as JSON |
| Session: `sceneSlots`, `sceneInfo`, `recallScopes`, `library`, `libraryError` | Data for the pages |

### FX preset names

FX 1 and FX 2 tiles show the preset names of the FLOW 8 app v1.14 (screens supplied by the owner): FX 1 = AMBIENCE … STADIUM (12 reverbs) + FLANGER, SOFT/WARM/DEEP CHOR; FX 2 = DELAY, ECHO, WIDE ECHO, PING PONG (12 delays) + the same 4 modulation presets. This settles the names part of conflict C-09. The CC meanings stay unconfirmed, so the engine controls stay locked. Tap tempo shows on FX 2 only, as in the app.

## 5. Visual system

Matte dark slate. Colour carries meaning only: mix colour, LEDs, channel tags.

| Token | Value | Use |
|---|---|---|
| Chassis | `#0E1013` | page background |
| Panel / card | `#14171C` / `#191C22` | control row, Inspector, sections |
| Strip | `#1C1F25 → #17191E` | channel strips |
| Key | `#30343B → #272A30` | rubber keys |
| Mix colours | `#E6E8EB` / `#34D399` / `#A78BFA` | MAIN / MON / FX |
| LED green / amber / red / blue | `#3BE36F` / `#FFB020` / `#FF3B30` / `#4FA8FF` | lamps, readouts; blue also marks USB/BT |
| LCD ink | `#0D1014` | text on the backlit scribble strips |
| LOCKED chip | amber outline | sections the remote cannot send |

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
| Show locked FLOW 8 functions in the Inspector | Same layout as the FLOW 8 app; the user sees what exists and why it is locked | Sections that do nothing until verified |
| One master strip that follows the bus selector | Same muscle memory as the FLOW 8 app; more width per strip | MON 2 level is not visible while MON 1 is selected |

## 7. Revisit as the system grows

1. **Hardware check of the meter module:** confirm the PortAudio device name and channel order on the real FLOW 8, and compare the meter readings with the mixer's own LEDs. The module has only been tested with a simulated audio backend.
2. **Hardware verification of GEQ, limiter, solo and FX:** each needs a controlled test before it leaves `LAN_LOCKED_FEATURES` (see section 4b).
3. **FLOW 8 snapshot memories (Program Change 1–15 on channel 16):** a controlled hardware test with the owner present, before any recall of mixer memories from the remote.
4. **EQ band frequencies:** confirm 100 Hz / 500 Hz / 2 kHz / 12 kHz against an official source (conflict C-04 lists other values).
5. **Incremental rendering:** update only the strips that changed, when more clients or more frequent RX events make full re-renders expensive.
6. **Hub-wide lock:** one lock for all clients, if the venue uses several tablets.
7. **Scene names:** user-defined scene names in the scene display.
