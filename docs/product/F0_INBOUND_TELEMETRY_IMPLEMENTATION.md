# F0 / P0: inbound telemetry, unplug detection and plan staleness

**Status:** Implemented, offline-verified, browser-verified with fake endpoints.
**Date:** 2026-11-19.
**Branch:** `stage2-mixer-workstation`.
**Companions:** `F7_CHANGE_PLAN_IMPLEMENTATION.md`, `P7_P8_F1_IMPLEMENTATION.md`,
`FLOW8_SAFETY_POLICY.md`, `docs/product/FLOW8_EVIDENCE_REGISTER.md`,
`docs/hardware/FLOW8_PROTOCOL_SPECIFICATION.md`.

This stage implements the hardware boundary the earlier tiers were waiting on:

1. **Inbound telemetry** — allowlisted CC feedback from the mixer becomes `OBSERVED`
   (the project's HARDWARE_CONFIRMED tier), on both the LAN console and the desktop app.
2. **Unplug detection and auto-reconnect** — a watchdog notices a vanished MIDI endpoint
   and a silent USB capture stream, flips the console to OFFLINE with a banner, and
   reconnects without restarting the server.
3. **Change-plan staleness guard** — a commit is refused when any targeted value moved
   after the preview, and the console shows the fresh diff marked `STALE`.
4. **`python -m tools.hw_probe --safe`** — a read-only readiness probe for the mixer,
   USB meters and Program Change reception. It has no send path at all.

---

## 1. Inbound telemetry

`flow8/telemetry.py` is the single decoder:

- The map is **derived from the verified command allowlist**, not hand-written:
  `(MIDI channel, CC) -> parameter`. If a pair cannot be sent, it is not accepted as
  telemetry either (97 allowlisted parameters today, including EQ CC 1-4, Low Cut CC 9,
  Compressor CC 11, Sends CC 14-17, Main/Bus faders).
- `decode()` classifies each driver message as `cc`, `program_change` or `other`, and
  `observed_value()` keeps booleans for mute/+48V. A malformed message never raises.
- `TelemetryStats` counts received/mapped/ignored CCs, Program Changes, forbidden resets
  (PC 16 on channel 16), and remembers the last parameter/time. It is exposed as
  `session.telemetry` (and `/api/status`) and shown on the Setup > Info page.

`Flow8Service._on_midi_in_event` now:

1. decodes and counts the event;
2. writes `set_observed_value(...)` **only** for mapped CCs (thread-safe state store);
3. notifies listeners once.

There is no outbound call on this path, so an echo of our own command cannot create a
loop. A test asserts the command log length is unchanged while telemetry arrives. Inbound
events run on the driver callback thread; the state store is locked and listeners are
snapshotted before dispatch.

**Current-value rule.** When provenance is `OBSERVED`, the observed raw value is the
current truth (used by preview, scenes and undo targets); otherwise the last commanded
value is used. This matters when the engineer moves a control after the app sent one.

## 2. Unplug detection and auto-reconnect

`Flow8Service` starts a daemon link watchdog (`start_watchdog`) when created with
`auto_connect=True` (the LAN hub path). Every `WATCHDOG_INTERVAL_S = 1.0` s:

- connected: `check_connection_health()` re-enumerates both endpoints. If either is gone,
  ports are closed, the ledger is cleared, every parameter becomes `UNSYNCED`, and a
  `__reconcile__` event is broadcast (the hub turns it into an SSE `link` event, so the
  console re-fetches the session and shows OFFLINE + the banner immediately).
- disconnected with `auto_reconnect`: `connect(quiet=True)` is retried every
  `RECONNECT_INTERVAL_S = 2.0` s. A manual `disconnect()` turns auto-reconnect off.

USB audio is separate from MIDI on purpose. `Flow8AudioMeter` now closes the stream and
reports `state="error"` when an "active" stream delivers **no frames** for
`FRAME_TIMEOUT_S = 2.0` s (some unplugs leave the endpoint active). The console shows an
amber `USB AUDIO LOST` banner while MIDI control keeps working, and the meter retries every
5 s. The METERS lamp already turned amber on `error`/`no_device`; that behaviour is kept.

## 3. Change-plan staleness guard

`previewChangePlan` now calls `Flow8Service.stage_change_plan(plan)`, which returns
`(rows, guard)` and remembers the preview snapshot:

```
guard -> { changes: ((channel, parameter, value), ...),
           snapshot: ((parameterId, from_value, from_provenance), ...),
           at: monotonic }
```

`commitChangePlan` requires a guard. The service re-reads every targeted parameter and
compares it with the snapshot. If anything moved (value **or** provenance, including a
disconnect that reset it to `UNSYNCED`), it returns `stale=True`, sends nothing, and the
hub answers:

```json
{"ok": false, "code": "stale_plan",
 "staleParameters": [{"parameterId": "ch1.eq_low", "previewFrom": 64,
                      "currentFrom": 40, "previewProvenance": "COMMANDED",
                      "currentProvenance": "COMMANDED"}],
 "rows": [ ... fresh preview rows ... ]}
```

Guards expire after `PREVIEW_TTL_S = 300` s, are single-use, are pruned to 32 pending,
and commit without one answers `409 preview_required`. The console keeps the panel open,
re-previews, marks the moved rows `STALE` with "was X · now Y", and requires a second
COMMIT on the fresh guard. Service-level callers can still pass `require_guard=False`
(internal tests), but the LAN API always requires it.

## 4. Safe hardware probe

```text
python -m tools.hw_probe --safe [--seconds 5] [--json] [--no-midi] [--no-audio]
```

1. Lists MIDI IN and MIDI OUT devices (read-only enumeration, nothing opened).
2. Opens **MIDI IN only** for the window and summarises mapped CCs per parameter,
   unmapped CCs, Program Changes and forbidden resets.
3. Starts the USB capture meter and reports frames received, levels and the exact reason
   when it cannot start.

Safety properties: no service object, no command boundary, no `midiOutShortMsg`; the JSON
report always contains `"safe": true, "sentMidi": false`. Exit codes: 0 when a FLOW 8 MIDI
IN is present, 2 when it is not, 3 on an unexpected error. A test patches
`Flow8MidiOut.open`/`send_cc` to raise and proves neither is called.

## 5. Tests

New/updated suites (555 total, 5 skipped):

| File | Tests | Covers |
|---|---|---|
| `test_telemetry.py` | 10 | allowlist map, decode, booleans, provenance, no echo, unmapped/PC counting, 200 concurrent events |
| `test_watchdog.py` | 8 | connect/listen, unplug→UNSYNCED, auto-reconnect, no MIDI sent, manual disconnect stays off, idempotent start, silent USB stream→error |
| `test_hw_probe.py` | 10 | summary math, injected port, no-device opens nothing, audio frames/reason, CLI exit codes, no MIDI OUT open/send |
| `test_change_plan.py` | +6 | guard required, fresh commit, moved value, expired guard, different plan, hub 409 + stale rows |

## 6. Verification evidence

```
python -m tools.run_tests_no_hw
ran 555 | passed 550 | failed 0 | errors 0 | skipped 5 | ...
hardware tests: NOT RUN (skipped 5) | attempted physical port opens: 0
```

Real probe on this workstation (read-only):

```
MIDI IN  devices: FLOW 8 MIDI IN, Nanocore
MIDI OUT devices: Microsoft GS Wavetable Synth, FLOW 8 MIDI OUT, Nanocore
MIDI IN listen: 5.0s on FLOW 8 MIDI IN
  messages 0 | mapped CC 0 | unmapped CC 0 | PC 0
  no allowlisted telemetry arrived; move a fader on the mixer and retry
USB meters: NOT RECEIVING | status unavailable
  (Meters need the 'sounddevice' package and PortAudio ...)
```

So the driver still enumerates stale FLOW 8 endpoints, but **zero bytes arrived in 5 s**
and no capture package is installed. This stage therefore does not claim hardware
telemetry; it claims the code path, with the evidence reported honestly by the probe.

Browser end-to-end (Chromium 1366×768, hub with fake endpoints; watchdog 0.2 s):

```
METER_BANNER USB AUDIO LOST — ... Mixer control continues if MIDI is online ...
STILL_ONLINE MIXER ONLINE
PLAN_ROWS 6
STALE_ROWS 1   STALE_SUB STALE — the mix moved after this preview
STALE_DIFF was 0.0 dB · now -5.6 dB
AFTER_COMMIT eq_low 51 lowCut 20 comp 25
TOAST Plan committed · 6 changes sent · UNDO restores the mix in one step
UNPLUG_PILL DISCONNECTED   UNPLUG_CLASS status-pill offline
UNPLUG_BANNER MIXER NOT CONNECTED — controls are locked...
REPLUG_PILL MIXER ONLINE
ERRORS []
```

Screenshots (local, `tools/output/` is git-ignored): `f0-meter-lost-1366.png`,
`f0-plan-stale-1366.png`, `f0-mixer-unplugged-1366.png`.

## 7. Known limitations

- **No hardware telemetry observed yet.** The probe reports the truth; USB TX must be ON
  and the mixer awake before an OBSERVED claim can be made on real hardware.
- **Stale driver entries.** Windows keeps a FLOW 8 MIDI IN/OUT entry after unplug; the
  watchdog therefore trusts an actual open/health check, not the enumeration alone.
- **One drag at a time** across clients (the ledger batch is hub-wide), unchanged from F7.
- **Meter package.** USB meters need `sounddevice` + PortAudio; the probe says so instead
  of pretending the stream is silent.
- **Guard is per preview.** Editing a plan in the console requires a new preview, which is
  the intended safety property, not a defect.
