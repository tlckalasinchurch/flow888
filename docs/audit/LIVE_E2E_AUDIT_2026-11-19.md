# Live E2E audit + FlowAi verification (2026-11-19)

**Build:** `1217b60` + dispatch-status change. **Target:** the real server on
`http://127.0.0.1:8844` (`python main.py --no-browser`). **Browser:** Chromium headless,
1366x768 and 1024x768. No fake endpoints: the MIDI IN/OUT handles are the real WinMM ones.

## Result

- **124 checks, 124 passed, 0 failed** across both viewports.
- Uncaught JS exceptions: **0**. Unexpected HTTP failures: **0** (403/409/503 guards excluded).
- Screenshots: `tools/output/audit-live-*.png`.

## What was exercised

Top bar (SELECT cycle, Undo/Redo/Copy/Paste/Clear Solo, ONLINE pill), all five Sends-on-Fader
buses, MIXER/STAGE, every tab (Mixer/Channel/Input/EQ/Comp/Sends/FX/Presets/Setup), EQ node
drag + RESET plan, FX 4x4 grids, Thai preset browser + plan preview, Setup pages (15 snapshots,
WHAT TO LOAD, library, inputs +48V lock, Info), and the overlay Inspector.

## FlowAi (how it works, verified live)

**No LLM.** `renderFlowAiDrawer()` is a rule engine over live state:
- `GAIN ADVICE` when the measured USB meter peak is >= -2 dBFS (advice only; gain is never automated);
- `HPF` when the selected CH 1-4 `lowCut < 10` raw -> proposes `low_cut = hzToHpfRaw(100)`;
- `SMART EQ` when all four band gains are within 0.3 dB of flat -> proposes `eq_low_mid -2.0 dB`, `eq_hi_mid +1.5 dB`;
- `SPACE` when `send_fx1 == 0` -> proposes `send_fx1 = 76` (-18 dB);
- `OK` otherwise. `REVIEW ALL` merges the changes (`mergePlanChanges`) into one ChangePlan.

Live commit evidence (CH 1, channel reset to low cut OFF / flat EQ / FX1 0 first):

```text
FlowAi actionable cards : 3 (HPF, SMART EQ, SPACE)
Plan rows               : 4  (Low Cut OFF -> 102 Hz, EQ Low-Mid 0.0 -> -2.1 dB,
                              EQ Hi-Mid 0.0 -> +1.4 dB, Send FX1 -inf -> -17.3 dB)
After COMMIT            : lowCut > 10, low_mid/hi_mid changed, send_fx1 = 76
Dispatch                : commands 0 -> 4+ ; drivers accepted every message
UI                      : EQ tab legend = COMMANDED (draws the committed curve)
After UNDO              : lowCut 0, low_mid 64, hi_mid 64, send_fx1 0  (one step)
```

So FlowAi genuinely reads live `Flow8Service` state, produces a reviewed plan, commits through
the command boundary, and undoes as one transaction. It is not stubbed and it does not call an
external model.

## MIDI OUT evidence

`/api/status` now exposes a dispatch summary and the Setup > Info page shows it:

```json
{"commands": 54, "accepted": 54, "driverDispatched": 54, "rejected": 0,
 "last": {"paramId": "ch1.send_fx1", "status": "DRIVER_DISPATCHED", "driverDispatched": true}}
```

`driverDispatched` means WinMM accepted the short message; it is not proof the mixer applied
it (evidence register E-rules).

## Two-way hardware sync

`python -m tools.hw_probe --safe --seconds 15` on the real host:

```text
MIDI IN devices : FLOW 8 MIDI IN, Nanocore
MIDI OUT devices: Microsoft GS Wavetable Synth, FLOW 8 MIDI OUT, Nanocore
messages 0 | mapped CC 0 | unmapped CC 0 | PC 0
USB meters: NOT RECEIVING (sounddevice missing)
```

The server's own telemetry counters also stay at `ccReceived=0` until the mixer transmits.
**Conclusion:** the outbound path is exercised at the driver level (54/54 accepted), but no
inbound CC has been observed, so `OBSERVED` provenance remains unverified on real hardware.
Enable USB MIDI TX on the FLOW 8 (and keep the mixer awake), then move a fader; the live
watcher log `tools/output/live_telemetry_watch.log` and `/api/status` telemetry will show
`mapped > 0` and the strip provenance becomes OBSERVED.

## Changes shipped

- `/api/status` and `/api/session` expose `dispatch` (commands/accepted/driverDispatched/rejected/last).
- Setup > Info shows the MIDI OUT dispatch row.
- `tests/test_status_dispatch.py`: 3 tests.
- `python -m tools.run_tests_no_hw` -> 575 tests, 570 passed, 0 failed, 0 errors, 5 skipped, 0 port opens.