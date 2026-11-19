# FLOW 8 CueAir Pro — USB / BLE / Hybrid Transport Audit

Date: 2026-11-19 · Branch: `fix/ble-transport-routing-audit` · Baseline: `b871191`
Evidence basis: source read this session + `docs/product/REA_FLOW_MIX_SPEC.md`
(clean-room BLE spec verified against live GATT enumeration). No physical hardware
was attached; nothing below claims hardware verification.

## 1. Architecture as found

```
UI (web_ui/app.js) -> Flow8LanHub.dispatch_action -> Flow8Service.set_*
  -> Flow8ParameterEngine -> Flow8CommandBoundary.execute_command
     -> safety.authorize_command + ACTIVE_ALLOWLIST + value validation
     -> Flow8MidiOut.send_cc (WinMM midiOutShortMsg)          [USB MIDI]
  -> Flow8Service.set_fader additionally calls BleTransport.send_fader
     for ch1..6 faders when mode is ble/hybrid                 [BLE, ad-hoc]
```

`BleTransport` runs its own thread + asyncio loop (bleak), handshakes
`0x39 -> 0x37 -> 0x07 -> 0x4B`, and decodes `0x06` fader notifications.

## 2. Defects identified

| # | Severity | Defect | Evidence |
|---|----------|--------|----------|
| D1 | Critical | **Transport mode does not gate USB.** In `ble` mode every command still goes out over USB MIDI because `Flow8CommandBoundary` always dispatches to `midi_out` when the port is open; BLE is an *additional* sender, not a router. | `service.py` `set_fader` BLE block; `command_boundary.py` step 3 |
| D2 | Critical | **Hybrid double-writes.** In `hybrid` (and `ble`) mode a ch1-6 fader is sent over USB MIDI *and* BLE — the same command through both transports. | `service.py` `set_fader` lines ~579-581 |
| D3 | High | **BLE "authenticated" is asserted, not verified.** `_authenticated = True` is set immediately after the `0x39` write completes; the `0x36` ACK is not awaited (a second code path also sets it on ACK). A GATT write success is treated as auth success. | `ble_transport.py` `_ble_session` |
| D4 | High | **No checksum verification on most inbound packets.** Only `0x06` notifications are checksum-verified; `0x36`, `0x27`, `0x22`, `0x38` etc. are decoded/acted on without `verify_ble_packet`. | `ble_transport.py` `decode_ble_notification` |
| D5 | High | **No GATT topology validation.** After connect, the code never confirms `FLOW8_SERVICE_UUID` / the data characteristic exist in `client.services`; notify failure falls back to a WinRT path but service absence is not checked. | `ble_transport.py` `_ble_session` |
| 6 | Medium | **BLE writes are unserialized across callers.** `send_fader` and `request_dump_trigger` each do `run_coroutine_threadsafe` independently; handshake writes race user writes (no asyncio lock, no ordering guarantee). | `ble_transport.py` `_write_packet` |
| D7 | Medium | **Echo-suppression map grows unboundedly** and is only pruned on match. | `ble_transport.py` `_recent_echoes` |
| D8 | Medium | **3068-byte state dump is triggered but never received/decoded.** `0x38` packets fall through to a generic event; no reassembly, no count, no honest "unverified" state. Per task rules decoding stays unimplemented (chunked float format not verified in-repo). | `ble_transport.py`, spec §5 |
| D9 | Medium | **BLE channel mapping assumed, not proven.** BLE `CH 0x01..0x06` is documented as "Ch 1–6/USB-BT" — ambiguous whether `0x06` is logical strip 6 or the USB/BT return. Current code maps BLE channel = logical strip 1..6 and refuses 7. Kept, documented as residual risk. | `ble_transport.py` `encode_fader_command`, spec §4 |
| D10 | Medium | **`is_connected` conflates links.** `Flow8Service.is_connected` requires USB MIDI IN+OUT; in a BLE-only session (no USB) the LAN hub rejects every action with 503 even though BLE could carry faders. | `service.py`, `lan_hub.py:637` |
| D11 | Low | **BLE discovery accepts any device named *flow*.** Service-UUID advertisement is checked, but post-connect identity is not re-verified (covered by D5 fix). | `ble_transport.py` discovery loop |
| D12 | Low | **UI understates/misstates BLE.** INFO page claims "this console does not write to" the BLE characteristic — stale after `b871191`. Routing page shows only a one-line BLE status. | `web_ui/app.js` |
| D13 | Low | **No transport/auth/sync visibility** for the user: active writer, per-transport capability, last error, and state-sync level are not surfaced together. | `web_ui`, `lan_hub` status |
| D14 | Info | `stop()` can leave the worker thread alive up to ~17 s (discover 5 s + connect 12 s) because `join(4.0)` is shorter than a connect attempt; thread is daemon so it dies with the process. | `ble_transport.py` `stop` |

## 3. Transport architecture implemented

```
UI -> Flow8LanHub -> Flow8Service -> Flow8ParameterEngine
   -> Flow8CommandBoundary (allowlist + safety.authorize_command — UNCHANGED choke point)
   -> TransportRouter.dispatch(param_id, spec, raw_midi)
        usb_midi : USB MIDI only (Flow8MidiOut.send_cc)
        ble      : BLE only; params outside the verified 0x06/0x0F fader set are
                   rejected explicitly (Flow8CommandRejectedError)
        hybrid   : single-writer per command — BLE-capable params (ch1-6 faders)
                   go BLE when BLE is connected+authenticated, else USB;
                   every other param goes USB. A command is NEVER sent on both.
   -> FLOW 8
```

USB audio meters (`publish_meters`) are independent of the control transport
and are untouched by routing.

## 4. State vocabulary

Existing `ParameterProvenance` (UNSYNCED/COMMANDED/OBSERVED/DISPATCH_FAILED/
UNSUPPORTED) and `SyncStatus` (SYNCED/PENDING_DISPATCH/DIVERGENT/UNKNOWN) are
kept. Added `Flow8Service.state_sync_snapshot()` (counts per provenance and
sync status) and `transport_status()` exposing per-transport
connected/authenticated state, active writer, supported features, and last
error. `hardware_applied` remains `None` everywhere — a successful GATT write
or WinMM dispatch is never reported as applied.

## 5. Remaining hardware-verification requirements

- BLE `CH` byte → logical strip mapping (D9) needs a physical fader move test.
- The 3068-byte dump chunk framing on BLE (does each chunk carry the §2
  checksum? is `0x38` the chunk type?) is unverified → no decoder written.
- Whether the mixer echoes non-fader params (`0x06` with other `PARAM` ids) is
  unknown → only `0x0F` faders are routed/decoded.
- BLE auth ACK timing on real hardware (timeout budget 4 s) needs a live check.
