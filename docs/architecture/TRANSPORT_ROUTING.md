# FLOW 8 Transport Routing (USB MIDI / BLE / Hybrid)

Status: implemented in `flow8/transport_router.py`, wired through
`Flow8CommandBoundary` and `Flow8Service`. See
`docs/audit/TRANSPORT_AUDIT_2026-11-19.md` for the defect list that motivated
this layer.

## Command path

```
UI / LAN hub / service API
  → Flow8Service (parameter engine, clamping, units)
  → Flow8CommandBoundary.execute_command   (allowlist + safety + value checks)
  → TransportRouter.dispatch               (single-writer transport choice)
  → Flow8MidiOut.send_cc  |  BleTransport.send_fader
  → FLOW 8
```

Safety is never bypassed: `authorize_command()` (gain block, +48V token grant)
runs in the boundary *before* routing, and `Flow8MidiOut.send_cc()` re-runs
`validate_outbound()` at the USB edge. BLE writes are a separate, narrower
protocol and do not pass through `validate_outbound()` — they are restricted by
the router to the verified write set instead.

## Modes

| Mode        | Control writes                                              | Observations                          |
|-------------|-------------------------------------------------------------|---------------------------------------|
| `usb_midi`  | USB MIDI only (all allowlisted parameters)                  | MIDI IN telemetry + USB audio meters  |
| `ble`       | BLE only; strips 1–6 faders (packet `0x06`, param `0x0F`)   | BLE notifications; dump chunks counted, not decoded |
| `hybrid`    | BLE for strips 1–6 faders when connected+authenticated, USB for everything else — one writer per command | USB meters + BLE notifications |

Single-writer rules:

- A command is sent on exactly one transport. It is never duplicated.
- In `hybrid`, if the BLE write fails the command fails; it is **not** retried
  over USB (that could double-apply).
- In `ble` mode, any parameter outside the verified BLE set is rejected
  explicitly (`Flow8CommandRejectedError`) — no silent USB fallback.
- USB audio meters (WASAPI) are independent of the control transport in all
  modes.

## BLE protocol evidence boundary

Verified in-repo (`docs/product/REA_FLOW_MIX_SPEC.md`):

- GATT service `14839ad4-8d7e-415c-9a42-167340cf2339`, data characteristic
  `0034594a-a8e7-4b1a-a6b1-cd5243059a57`.
- Framing `[type, version, payload…, checksum]`, checksum `sum(body) & 0xFF`.
- Host→mixer writes: **only** fader commands `0x06`/`0x0F` for channels
  `0x01..0x06`. Bus/master BLE addresses are unconfirmed and refused.
- Handshake: `0x39` auth → mixer `0x36` ACK → `0x37` session → `0x07` config →
  `0x4B` dump trigger.

NOT verified (fail closed):

- The 3068-byte state dump (`0x38` chunks) is counted (`dumpChunks`,
  `dumpBytes`, `lastDumpAt`) but **never decoded** — the chunked float layout
  is documented but not verified against this firmware.
- No other BLE write types are implemented. Do not add them without protocol
  evidence.

## Connection / authentication semantics

`BleTransport.is_connected` means **GATT link up AND auth ACK (0x36) received**.
A completed GATT write never marks a command as applied:

- `DRIVER_DISPATCHED` — WinMM accepted the short message.
- `BLE_WRITE_ACCEPTED` — GATT write accepted.
- `hardware_applied` stays `None` in both cases until an observed confirmation
  exists.

`Flow8Service.control_connected` reports whether the *active* control
transport can accept commands; `transport_status()` exposes per-transport
state (connected / authenticated / packets / last error / supported features)
to the LAN hub and the ROUTING page of the web UI.

## Remaining hardware verification

- Physical FLOW 8 BLE session: auth ACK timing, reconnect behavior, echo
  suppression against real notifications.
- Whether `0x38` dump chunks can be reassembled into a verified state image.
- Whether BLE fader writes on strips 1–6 produce mixer-side changes identical
  to USB CC (echo path currently suppresses self-notifications for 0.5 s).
