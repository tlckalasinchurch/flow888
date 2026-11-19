# Behringer FLOW 8 — Clean-Room BLE & SysEx Protocol Specification

- **Status:** Verified against public clean-room reverse-engineering documentation and live hardware GATT enumeration (`FLOW 8 LE` `[E2:CE:15:BA:E1:4D]`).
- **Primary Open-Source Reference:** [`abelroes/flow-8-midi`](https://github.com/abelroes/flow-8-midi/blob/main/docs/flow8-midi-implementation.md) (`src/service/ble.rs`, `src/service/sysex_parser.rs`).
- **Scope:** Behringer FLOW 8 ONLY. All outbound writes remain subject to `flow8/safety.py` (`+48V` confirmation lock, preamp gain lock, PC 16 reset block).

---

## 1. BLE GATT Endpoint (Observed on Live Hardware)

| Property | Value |
|---|---|
| Device Name | `FLOW 8 LE` |
| Service UUID | `14839ad4-8d7e-415c-9a42-167340cf2339` |
| Bidirectional Characteristic UUID | `0034594a-a8e7-4b1a-a6b1-cd5243059a57` (`write`, `notify`, no `0x2902` CCCD on Windows) |
| Metadata Characteristics | `0035594a-...` (`read`), `0036594a-...` (`read`) |

> **Windows WinRT Note:** Because `0034594a-...` exposes `notify` without a `0x2902` CCCD descriptor (`descs: []`), `bleak`'s `start_notify()` fails with ATT Error 3 (`Write Not Permitted`). On Windows, attach `GattCharacteristic.add_value_changed` directly via WinRT rather than writing a CCCD.

---

## 2. Packet Framing & Checksum

All vendor BLE packets on `0034594a-...` follow:

```text
[type:1] [ver:1] [payload:N] [checksum:1]
```

- **Host → Mixer:** `ver` (`byte[1]`) is `0x01`.
- **Mixer → Host:** `ver` is `0x01` (ack/data) or `0x02` (multi-part device identity).
- **Checksum:** `sum(packet[:-1]) & 0xFF` (verified across all 13 documented packet types).
- **Echo Pattern:** Outbound `0x06` write commands are echoed back by the mixer as notifications. `BleTransport` suppresses matching echoes within a short dedupe window to prevent feedback loops.

---

## 3. Handshake & Sync Sequence

| Step | Direction | Type | Hex Bytes | Purpose |
|---|---|---|---|---|
| 1 | Host → Mixer | `0x39` | `39 01 fd 06 2b 06 39 f1 7f e7 b7 27 8b 8f 35 5a 49 5c 2a` | Static auth key (19 bytes) |
| 2 | Mixer → Host | `0x36` | `36 01 37` | Auth acknowledgment |
| 3 | Host → Mixer | `0x37` | `37 01 38` | Session start (triggers `0x38` 4-chunk BLE state dump) |
| 4 | Host → Mixer | `0x07` | `07 01 08` | Config/snapshot request (triggers `0x27` snapshot names) |
| 5 | Host → Mixer | `0x4B` | `4b 01 4c` | Dump trigger (emits 3068-byte SysEx state dump on USB MIDI IN & BLE) |

---

## 4. Parameter Write & Notification Framing (`Type 0x06`)

```text
06 01 <CH> <PARAM> <VALUE> <CHK>
```

- **Verified:** `PARAM = 0x0F` (Channel Fader/Level), `VALUE = 0x00..0xFF` (`0` = `-inf`, `255` = `+10 dB`, mapped to/from `0..127` raw MIDI).
- **Channel Addressing (`CH`):** `0x01..0x06` (Ch 1–6/USB-BT). Bus addresses (`MAIN`, `MON1`, `MON2`) and non-fader `PARAM` IDs remain **UNCONFIRMED** in public docs and are NOT sent over BLE `0x06` without verification.
- **Type `0x22` (20-byte Metering Stream):** ~300 ms interval metering packets; does **not** carry fader positions.
- **Type `0x27` (Snapshot Names):** Length-prefixed UTF-8 strings for slots 1–15.

---

## 5. 3068-Byte SysEx State Dump (Triggered by `0x4B 0x01 0x4C`)

- **Header:** `F0 00 20 32 21 00 46 4C 4F 57 ... F7` (Behringer `00 20 32`, Model `0x21` FLOW 8).
- **Encoding:** 5-byte packed IEEE 754 little-endian 32-bit floats with rotating MSB byte position (3 modes).
- **Confidence Note:** Channel faders, gains, pans, compressors, low cuts, 4-band EQs, sends, mutes, solos, phantom power, bus levels/GEQ/limiter, and channel names are documented and calibrated in `abelroes/flow-8-midi/src/service/sysex_parser.rs`.
