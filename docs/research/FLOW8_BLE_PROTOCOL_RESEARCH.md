# FLOW 8 BLE Protocol Research

Date: 2026-11-19. Updated 2026-11-20 (LightBlue evidence, section 1.3a). Repo state: `main` @ `2d3ec73`.
Scope: repository audit, read-only BLE observation, analysis. **No implementation. No product source changed.**
Labels: **VERIFIED** (observed or computed this session, with the source), **USER-PROVIDED** (from the owner's nRF Connect session, not reproduced here), **ASSUMPTION**, **UNKNOWN**.

## 0. Disclosure: writes sent before the read-only rule

The read-only rule arrived after these steps. They are listed so the evidence below is not misread as read-only throughout.

| When (2026-11-19, evening) | What was sent to the mixer | Result |
|---|---|---|
| Console switched to `hybrid` | Existing `BleTransport` handshake: `AUTH_PACKET` (`0x39`) via `write_gatt_char` | GATT link up, `packetsTx = 1`, `packetsRx = 0`, `BLE auth ACK (0x36) not received within 4.0s`. An earlier try ended `[WinError -2147467260] Operation aborted`. Console switched back to `usb_midi`. |
| Scratch script, no pair | Same `AUTH_PACKET`, `response=True` | Write raised `Operation aborted`. 0 packets received. |
| Scratch script, `pair()` first | Same `AUTH_PACKET`, `response=True` | `pair()` returned without error; the write raised `Operation aborted`. Bond removed afterwards with `unpair()`. |

No fader, mute, bus, EQ or other parameter packet was sent. No hex payload was invented: the only bytes written are the constant already in `flow8/ble_transport.py`. Whether those bytes reached the mixer when the write aborted is UNKNOWN. After the rule, only reads and scans were done.

## 1. Hardware discovery evidence

### 1.1 PC scan (bleak 3.1.0, Windows, Intel Wireless Bluetooth adapter) - VERIFIED
Passive scan, 10 s, no connection:

| Field | Value |
|---|---|
| Address | `E2:CE:15:BA:E1:4D` (same address as in `docs/product/REA_FLOW_MIX_SPEC.md`) |
| Local name | `FLOW 8 LE` |
| Advertised service UUID | `14839ad4-8d7e-415c-9a42-167340cf2339` |
| Service data, key `14839ad4-0000-1000-8000-00805f9b34fb` | `00523f4576e95a` (7 bytes; matches the owner's iPad reading `0052 3F45 76E9 5A`) |
| Manufacturer data | none |
| TX power | not advertised |
| RSSI | -53 to -87 dBm across scans (iPad: -53) |

### 1.2 GATT enumeration from the PC (read-only connect) - VERIFIED
Connected in 5.6 s; the service is present.

| Characteristic | Properties | Descriptors | Value read |
|---|---|---|---|
| `0034594a-a8e7-4b1a-a6b1-cd5243059a57` | `notify`, `write` | 0 (no CCCD) | not readable by property |
| `0035594a-a8e7-4b1a-a6b1-cd5243059a57` | `read` | 0 | `0900` |
| `0036594a-a8e7-4b1a-a6b1-cd5243059a57` | `read` | 0 | `e52d` |

- `start_notify` on `0034…` fails: `BleakGATTProtocolError(3, 'GATT Protocol Error: Write Not Permitted')`. Same error as the older `tools/output/ble_watch_stdout.log`.
- 12 s of listening with no write: 0 notifications.

### 1.3 Owner's iPad session (nRF Connect 2.8.3) - USER-PROVIDED
- Same service, same three characteristics, "no Descriptors" on each. Also standard services 1800 and 1801.
- `0035594a` last read `0900`: matches the PC read.
- `0034594a` last value `35 02 00 01 27 00 00 09 2D E5 7A` (11 bytes). **VERIFIED by arithmetic:** `sum(first 10 bytes) & 0xFF = 0x7A`, equal to the last byte. So it follows the repo's frame rule `[type, version, payload…, checksum]`. Its type byte `0x35` is named `PKT_IDENTITY` in `ble_transport.py`; the spec calls version `0x02` "multi-part device identity".
- Connection log: connect, discovery, then **disconnect about 30 s later** in both cases that did nothing else (23:37:32 to 23:38:02; 23:39:10 to 23:39:40). ASSUMPTION: an unauthenticated session timeout.

### 1.3a Owner's second iPad session (LightBlue) - USER-PROVIDED, added 2026-11-20
Screenshots and notes from LightBlue on the iPad. Nothing here was reproduced by the agent.

| Item | Reported |
|---|---|
| Device name | `FLOW 8 LE` |
| Peripheral identifier | `FF6B459E-3DFF-31ED-9EF2-3B374D08DCE6` |
| Connectable | yes |
| Advertising service data | `00523F4576E95A` (same 7 bytes as 1.1 and 1.3) |
| Primary service | `14839AD4-8D7E-415C-9A42-167340CF2339` |
| `0034594A-…` | Notify, Write |
| `0035594A-…` | Read |
| `0036594A-…` | Read |

Not obtained in this session: **no read value was successfully inspected in LightBlue**, and the connection was lost during later inspection. Notifications were not enabled and nothing was written (owner's instruction).

What this adds and what it does not:
- It repeats the GATT layout and properties from 1.2 and 1.3 with a second, independent iOS tool. The layout is now seen by 3 sources: the PC (bleak), nRF Connect, LightBlue.
- The identifier `FF6B459E-…` is not a Bluetooth address. It cannot be compared with `E2:CE:15:BA:E1:4D` (PC) or used on Windows. ASSUMPTION: iOS exposes a per-device identifier instead of the address (platform behaviour, not verified here). So the iPad and the PC have not been proven to see the same physical mixer by address. The matching service data `00523F4576E95A` on both is the only link, and it is not proof of identity.
- The lost connection is one more case of a session ending without any write from the host. It does not change the 30 s observation in 1.3 and is not evidence for a cause (see U4).
- No new protocol conclusion is drawn. Per the owner, further protocol analysis waits for read values obtained with a real read. The PC reads of `0035` and `0036` in 1.2 remain the only read values from these two characteristics in this document.

### 1.4 Observation, no interpretation
The identity value contains `00 09` and `2D E5`. The reads of `0035` and `0036` are `09 00` and `E5 2D`: the same two byte pairs, each reversed. Meaning UNKNOWN. Do not map them to firmware, version or serial without evidence.

### 1.5 The "Clone 2" device
`FLOW 8 LE - Clone 2` (rotating random address, manufacturer data company id 76) is an advertiser made in nRF Connect on the owner's iPad (VERIFIED from the Peripheral tab screenshot). Its advertisement has no service UUID. It has the substring "flow" in its name. See 6.4.

## 2. GATT mapping

| UUID | Role | Basis |
|---|---|---|
| `14839ad4-8d7e-415c-9a42-167340cf2339` | Vendor primary service | VERIFIED (PC, iPad) |
| `0034594a-…` | Bidirectional data channel: host writes packets, mixer notifies | Properties VERIFIED. Packet semantics from the spec, partly verified (section 3). |
| `0035594a-…` | Read-only metadata, 2 bytes, `0900` | Value VERIFIED. Purpose UNKNOWN. |
| `0036594a-…` | Read-only metadata, 2 bytes, `e52d` | Value VERIFIED. Purpose UNKNOWN. |
| Service data `00523f4576e95a` | Advertisement payload | Value VERIFIED. Purpose UNKNOWN. |

## 3. Protocol analysis

Source of packet semantics: `docs/product/REA_FLOW_MIX_SPEC.md`, derived from the public project `abelroes/flow-8-midi` plus hardware GATT enumeration. It is a secondary source. Packet meanings are not independently verified on this hardware.

Frame: `[type, version, payload…, checksum]`, `checksum = sum(body) & 0xFF`. Checksum rule VERIFIED on one mixer-originated packet (1.3) and on the repo's constants by `tests/test_ble_transport.py::test_known_handshake_packets_pass_checksum`.

| Type | Direction | Meaning per spec | Status here |
|---|---|---|---|
| `0x39` | host to mixer | Static auth key, 19 bytes | Written, no ACK observed (section 0) |
| `0x36` | mixer to host | Auth ACK | Never observed |
| `0x37`, `0x07`, `0x4B` | host to mixer | Session start, config request, dump trigger | Not sent by us (they follow the ACK) |
| `0x35` | mixer to host | Identity | One value observed (USER-PROVIDED) |
| `0x06` + `0x0F` | both | Fader on channels `0x01..0x06`, value `0x00..0xFF` | Not exercised on hardware |
| `0x22` | mixer to host | 20-byte metering, about 300 ms | Not observed |
| `0x27` | mixer to host | Snapshot names | Not observed |
| `0x38` | mixer to host | 4-chunk state dump (3068 bytes) | Not observed; repo counts, never decodes |

Open point on notifications: the mixer exposes `notify` with no CCCD. Windows cannot enable it the normal way (ATT error 3). `BleTransport` falls back to WinRT `add_value_changed`. Whether the mixer then pushes data without a CCCD write is UNKNOWN: the single attempt received 0 packets.

## 4. Capability matrix

"Documented" is not "verified on this mixer".

| Capability | Documented (spec) | Observed on this hardware |
|---|---|---|
| Advertise and connect without pairing | - | YES (PC and iPad) |
| Read metadata `0035`, `0036` | yes | YES |
| Notify on `0034` | yes | NO (0 packets; CCCD missing) |
| Receive identity packet | yes | YES, on iPad (USER-PROVIDED) |
| Authenticate (`0x39` to `0x36`) | yes | NO |
| Write fader `0x06/0x0F`, strips 1-6 | yes | NOT TESTED |
| Mute, pan, EQ, comp, sends, buses, +48V, gain over BLE | no (unconfirmed) | NOT TESTED, and refused by the router |
| Read mixer state in real time | via `0x06` echoes, `0x38` dump | NO |
| Metering | `0x22` | NO |

Answers to the owner's questions:
1. Is BLE a control channel or only advertising? There is a writable GATT characteristic, so it is more than advertising. Control working on this hardware is NOT verified.
2. Characteristic roles: section 2.
3. Read state over BLE? Only metadata reads work. State reading depends on notifications (UNKNOWN) or the dump (not observed).
4. Real-time notify? Documented, not observed.
5. Fader, Mute, Volume, channel state? Documented: faders 1-6 only. Everything else unconfirmed.
6. BLE vs USB MIDI: section 5.
7. No payload meaning is claimed beyond the cited spec and the checksum arithmetic.

## 5. BLE vs USB MIDI (current system)

| Aspect | USB MIDI | BLE |
|---|---|---|
| Status on this hardware | Working, in daily use | Link works; control path unverified |
| Writable parameters | All allowlisted (`flow8/safety.py`, `command_boundary`) | Faders 1-6 only, by router rule (`flow8/transport_router.py`) |
| Read-back | MIDI IN telemetry for some moves (faders, mute, pan, bus faders) | Unknown |
| Meters | Not over MIDI; USB audio capture | `0x22` documented, not observed |
| Safety validation | `authorize_command()` then `validate_outbound()` at the USB edge | `authorize_command()` in the boundary, then the router. **Not** `validate_outbound()` (stated in `docs/architecture/TRANSPORT_ROUTING.md`) |
| Cable | USB required | None |
| Concurrency | One host | One central at a time is likely (ASSUMPTION): the mixer stopped advertising to the PC while the iPad was connected |

## 6. Safety and security assessment

Repo audit of what exists today: BLE is already implemented (`flow8/ble_transport.py`, `flow8/transport_router.py`, mode switch in `flow8/service.py`, `setTransportMode` and `bleDumpTrigger` in `flow8/lan_hub.py`), tested offline by `tests/test_ble_transport.py` (14 tests) and `tests/test_transport_router.py`. No hardware test passed an auth ACK.

Findings (no code changed):

- 6.1 **BLE writes sit outside `validate_outbound()`.** The router narrows them to `ch1..6.fader`, but the rule lives in one regex, not in the safety module. `docs/product/FLOW8_SAFETY_POLICY.md` has no rule for BLE (SR-01 to SR-12 concern MIDI).
- 6.2 **Handshake packets bypass the router.** `_handshake()` writes four constants (`0x39`, `0x37`, `0x07`, `0x4B`) straight through `_write_packet`. They are fixed, but nothing in the safety layer names them.
- 6.3 **`bleDumpTrigger` is exposed as a hub action** (`lan_hub.py`, allowlist near line 88) and writes `0x4B`.
- 6.4 **Device selection is weak.** `_ble_session` picks the first advertiser whose service UUID matches **or whose name contains "flow"**; the later GATT check only needs the UUIDs. A device that copies the GATT layout and has "flow" in its name can be chosen. The "Clone 2" advertiser demonstrates the name path (its advertisement has no UUID but has "flow" in the name). The auth key is a static constant sent to whichever device is chosen. Pinning the address or checking `0035`/`0036`/service data would narrow this; neither is done.
- 6.5 **Provenance conflict in the docs.** `REA_FLOW_MIX_SPEC.md` says the GATT layout was verified on live hardware; `docs/archive/FLOW8_BLE_GATT_DISCOVERY.md` (2026-11-09) says enumeration was BLOCKED. This session's evidence (1.1, 1.2) supports enumeration, so the spec claim now holds, but the archive file should not be read as current.
- 6.6 The static auth key is a shared secret copied from a public repo. It gives no per-device or per-session security. Anyone in range can try to connect. ASSUMPTION: the mixer has no BLE-level encryption; the pair attempt did not change the outcome.
- 6.7 Provenance rules (SR-08, SR-11): a BLE write that is merely "accepted" must never be shown as applied. `TRANSPORT_ROUTING.md` already says `hardware_applied` stays `None`. Keep that.

## 7. Unknowns and required experiments

| # | Unknown | Experiment | Needs a write? |
|---|---|---|---|
| U1 | Why the `0x39` write aborts or gets no ACK | Retry with `response=False`; compare with the owner's other BLE client | Yes: re-sends `AUTH_PACKET` |
| U2 | Whether notifications are delivered without a CCCD | Passive listen on a link where the mixer is already pushing (e.g. identity on connect) with the WinRT handler attached | No |
| U3 | Meaning of `0035`, `0036`, service data | Read several mixers or states; compare before and after a mixer-side change made by hand | No |
| U4 | Reason for the 30 s disconnect | Time an idle connection from the PC | No |
| U5 | Which central the mixer accepts | Connect from the PC while a second client is idle, then reverse | No |
| U6 | Whether `0x06/0x0F` fader writes change the mixer | After U1 succeeds, one fader on a muted, unused channel with the owner watching | Yes |
| U7 | Whether the mixer needs its physical pairing button | Check the manual; compare advertising with and without it | No |

Every row marked Yes needs separate owner approval. This document does not authorise it.

## 8. Recommended architecture (proposal, not implemented)

Keep USB MIDI as the primary control transport. Treat BLE as an optional, additive transport behind the existing single-writer router. Reuse what exists; change only the gaps from section 6.

1. **Connection manager:** one worker (already `BleTransport`) with an explicit state machine: `idle`, `scanning`, `connected_unauthenticated`, `ready`, `failed`. Publish each state; no state implies "applied".
2. **Device identity:** connect only to an address the owner has confirmed (stored setting), and require the service UUID plus the `0035` read to be stable across sessions. Never select by name.
3. **GATT client:** keep the GATT identity check. Add reads of `0035`/`0036` as read-only diagnostics.
4. **Notification handler:** keep the WinRT fallback; log raw notifications for research behind a debug switch that never writes.
5. **Write boundary:** move the "BLE-writable set" into `flow8/safety.py` as an explicit allowlist (faders 1-6 only) and have `BleTransport` refuse anything outside it, so the safety module, not a regex in the router, is the authority. Put the four handshake constants in the same allowlist by name. Remove `bleDumpTrigger` from the hub until it has a use.
6. **Transport abstraction:** unchanged: `TransportRouter.dispatch` stays the single writer. USB behaviour must not change; existing tests are the guard.
7. **Truthful UI:** show BLE state from the state machine and the real error text, as the status pill already does.

## 9. Implementation roadmap (each step needs approval)

| Step | Content | Gate |
|---|---|---|
| R0 | Approve this document; correct the contradiction in 6.5 | owner |
| R1 | Read-only experiments U2, U3, U4, U5, U7 | no hardware writes |
| R2 | Safety changes from 6.1 to 6.4: BLE allowlist in `safety.py`, address pinning, drop name matching, drop `bleDumpTrigger`; offline tests only | owner approves the diff |
| R3 | Write experiment U1 (`AUTH_PACKET` only) | explicit owner approval |
| R4 | If R3 yields an ACK: one fader on one unused channel (U6) | explicit owner approval, owner present |
| R5 | State machine and UI wording | after R4 |
| R6 | Decide whether hybrid is worth shipping: USB already carries every command | owner |

## 10. Evidence index

- PC scan and GATT read: bleak 3.1.0 scripts run 2026-11-19; output quoted in sections 1.1 and 1.2 (scripts were in the session scratchpad, not in the repo).
- iPad session and screenshots (nRF Connect): owner, 2026-11-19 23:37-23:41.
- iPad session (LightBlue): owner, reported 2026-11-20; section 1.3a. No read values.
- Repo: `flow8/ble_transport.py`, `flow8/transport_router.py`, `flow8/service.py:166-195`, `flow8/lan_hub.py`, `docs/product/REA_FLOW_MIX_SPEC.md`, `docs/architecture/TRANSPORT_ROUTING.md`, `docs/product/FLOW8_SAFETY_POLICY.md`, `docs/archive/FLOW8_BLE_GATT_DISCOVERY.md`, `tools/ble_probe.py`, `tools/output/ble_watch_stdout.log`, `tests/test_ble_transport.py`.
- Not done: no change to `safety.py`, `command_boundary`, `midi_out`, the allowlist or any business logic; no mock data.
