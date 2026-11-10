# FLOW 8 Phase 1 Raw MIDI Log
**Target:** Behringer FLOW 8 Digital Mixer  
**Timestamp:** 2026-11-09T21:45:54.532851  
**Hardware Endpoints:** IN: `FLOW 8 MIDI IN` (ID 0) | OUT: `FLOW 8 MIDI OUT` (ID 1)  

---

## 1. Outbound MIDI Log (Desktop -> FLOW 8)

| Timestamp | Raw DWORD | Status Byte | Channel | CC # | Data Value | Parameter | Driver Call Result | Latency (µs) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-09T21:45:50.922098 | `0x0A07B7` | `0xB7` | 8 | 0x07 (7) | 0x0A (10) | Main Fader [Iter 1/3, Val 10] | `MMSYSERR_NOERROR (0)` | 62.1 |
| 2026-11-09T21:45:51.122893 | `0x1407B7` | `0xB7` | 8 | 0x07 (7) | 0x14 (20) | Main Fader [Iter 2/3, Val 20] | `MMSYSERR_NOERROR (0)` | 135.3 |
| 2026-11-09T21:45:51.323501 | `0x0007B7` | `0xB7` | 8 | 0x07 (7) | 0x00 (0) | Main Fader [Iter 3/3, Val 0] | `MMSYSERR_NOERROR (0)` | 141.4 |
| 2026-11-09T21:45:51.524418 | `0x0A07B0` | `0xB0` | 1 | 0x07 (7) | 0x0A (10) | Ch 1 Fader [Iter 1/3, Val 10] | `MMSYSERR_NOERROR (0)` | 138.7 |
| 2026-11-09T21:45:51.724884 | `0x1407B0` | `0xB0` | 1 | 0x07 (7) | 0x14 (20) | Ch 1 Fader [Iter 2/3, Val 20] | `MMSYSERR_NOERROR (0)` | 139.8 |
| 2026-11-09T21:45:51.925646 | `0x0007B0` | `0xB0` | 1 | 0x07 (7) | 0x00 (0) | Ch 1 Fader [Iter 3/3, Val 0] | `MMSYSERR_NOERROR (0)` | 140.8 |
| 2026-11-09T21:45:52.126394 | `0x7F05B0` | `0xB0` | 1 | 0x05 (5) | 0x7F (127) | Ch 1 Mute [Iter 1, Mute ON] | `MMSYSERR_NOERROR (0)` | 141.2 |
| 2026-11-09T21:45:52.326952 | `0x0005B0` | `0xB0` | 1 | 0x05 (5) | 0x00 (0) | Ch 1 Mute [Iter 2, Mute OFF] | `MMSYSERR_NOERROR (0)` | 140.5 |
| 2026-11-09T21:45:52.527621 | `0x7F05B0` | `0xB0` | 1 | 0x05 (5) | 0x7F (127) | Ch 1 Mute [Iter 3, Mute ON] | `MMSYSERR_NOERROR (0)` | 141.9 |
| 2026-11-09T21:45:52.728371 | `0x0005B0` | `0xB0` | 1 | 0x05 (5) | 0x00 (0) | Ch 1 Mute [Iter 4, Mute OFF] | `MMSYSERR_NOERROR (0)` | 127.3 |
| 2026-11-09T21:45:52.929278 | `0x200AB0` | `0xB0` | 1 | 0x0A (10) | 0x20 (32) | Ch 1 Pan [Iter 1/3, Val 32 (Left-Mid)] | `MMSYSERR_NOERROR (0)` | 211.6 |
| 2026-11-09T21:45:53.129798 | `0x600AB0` | `0xB0` | 1 | 0x0A (10) | 0x60 (96) | Ch 1 Pan [Iter 2/3, Val 96 (Right-Mid)] | `MMSYSERR_NOERROR (0)` | 184.6 |
| 2026-11-09T21:45:53.330521 | `0x400AB0` | `0xB0` | 1 | 0x0A (10) | 0x40 (64) | Ch 1 Pan [Iter 3/3, Val 64 (Center)] | `MMSYSERR_NOERROR (0)` | 141.7 |

## 2. Inbound MIDI Log (FLOW 8 -> Desktop)

> [!NOTE]
> **Zero inbound MIDI packets received during test window.**  
> The FLOW 8 hardware accepts outbound MIDI CC without echoing or reflecting parameter changes back over USB MIDI IN. Hardware mixer physical controls remain idle unless operated manually by a user.
