# Decision record: Rust porting investigation (closed)

- Date: 2026-11-27
- Status: **Decided: no Rust porting. The Python architecture stays.**
- Decided by: the project owner, based on the profiling evidence below
- Scope: the whole `flow8/` package, including `flow8.safety.validate_outbound`

## Decision

1. No Python function is ported to Rust.
2. The Python architecture stays as it is. The command path in `CLAUDE.md` is unchanged.
3. `flow8.safety.validate_outbound` stays Python code.
4. The safety layer, the SR rules (`docs/product/FLOW8_SAFETY_POLICY.md`), MIDI routing and business logic are not modified.
5. No Rust extension is built, enabled or switched on. `fast-anything enable` was never run.

## Profiling evidence

Tool: `fast-anything` v0.6.1 (`scan` only). Python: `C:\Python314\python.exe`.
Code profiled: the working tree at commit `6a9b8c6`, plus the uncommitted changes present on 2026-11-27 (including `flow8/service.py`).

### Workload

A synthetic script that exits when done (see the appendix). It drives `Flow8Service(auto_connect=False)` through a MIDI driver faked with `tests/_safety_helpers.py::fake_open_port`. Before any `flow8` import, it replaces winmm `midiOutOpen` and `midiInOpen` with functions that raise. It refuses to run if `FLOW8_HW_TESTS` or `FLOW8_HW_TESTS_MUTATE` is set.

Each of the 60 rounds covers all 7 channel strips: fader sweeps, pan, mute, 4 EQ bands in dB, and 4 sends. It also sets 3 bus faders and runs 5 undos and 5 redos. Every 10th round captures a scene, and the round 5 after each capture recalls it.

The script does not cover +48 V, preamp gain, Program Change, BLE, the LAN hub, inbound MIDI or the audio meters.

### Results

| Measure | Value |
|---|---|
| Workload rounds | 60 |
| Fake MIDI sends (`midiOutShortMsg` on the mock) | 12,114 |
| Wall time, plain run (`time python …`) | 3.7 s |
| Wall time under `fast-anything scan` | 2.31 s (script outside the repo), 2.86 s (script in the repo root) |
| Real MIDI hardware communication | None. Real port opens were denied, and all sends went to a `MagicMock` |

Top entries from the second scan (`.fast/state.json`; share = cumulative time / wall time):

| Function | Calls | Share | fast-anything verdict |
|---|---|---|---|
| `flow8.safety.validate_outbound` | 12,114 | 2.9% | portable (with `_permit_active`, `_tables`) |
| `flow8.safety.authorize_command` | 12,114 | 1.7% | too small to matter |
| `flow8.service.Flow8Service._param_id` | 12,696 | 0.8% | too small to matter |
| `flow8.parameter_mapping.eq_db_to_midi` | 1,680 | 0.4% | too small to matter |
| `Flow8Service._dispatch_and_notify` | 12,114 | 71.9% | not portable (method) |
| `Flow8Service.set_fader` | 6,772 | 46.7% | not portable (method) |
| `Flow8CommandBoundary.execute_command` | 12,114 | 45.3% | not portable (method) |
| `TransportRouter.dispatch` | 12,114 | 32.0% | not portable (method) |
| `TransportRouter._dispatch_usb` | 12,114 | 30.7% | not portable (method) |
| `Flow8MidiOut.send_cc` | 12,114 | 28.4% | not portable (method) |

Shares are cumulative, so nested calls are counted more than once and the column does not sum to 100%.

## Rationale for rejecting the port

1. **The gain is too small.** The only portable candidate takes 2.9% of a synthetic run. Even an infinitely fast port cuts less than 3% from the end-to-end time. The fast-anything threshold for a visible difference is 2%, so this is barely above it.
2. **The real app does not run at this speed.** On the real mixer, each command waits on the USB MIDI driver and the hardware. The workload removed those waits. With them back, the Python share is smaller still.
3. **The candidate is the safety gate.** `validate_outbound` is the final outbound check (SR rules). It reads the +48 V permit state through `_permit_active` (`flow8/safety.py:337`). Enabling a port appends a swap block to `flow8/safety.py`, so a second implementation would run the safety check. Every SR rule would then depend on that Rust code matching the Python code exactly. A 3% gain does not justify that risk.
4. **The heavy paths cannot be ported.** About 70% of the time is in class methods that do I/O (dispatch, the router, `send_cc`). fast-anything ports only module-level functions and static methods, and these would not be pure functions anyway.
5. **Cost.** A Rust port adds a toolchain, a build step and a native binary to a project that has no build step and uses only the standard library.

## Remaining validation (not verified)

Real hardware performance has **not** been measured. These items stay open:

- [ ] `flow8/audio_meter.py`: CPU cost of the level math on real buffers.
- [ ] Real USB audio capture from the FLOW 8 (the device's own stream, not synthetic audio).
- [ ] Live meter CPU usage, and meter latency from capture to the SSE event to the UI.
- [ ] Buffer drops and audio glitches during capture over a long session.
- [ ] End-to-end command latency on the real mixer (UI action to `midiOutShortMsg` return).

Any of these needs the mixer connected and the owner's go-ahead in that session (`CLAUDE.md`, hardware tests).

## Artifacts

- `.fast/` (repo root, untracked) holds the scan output: `state.json` (the results above), `profile.json`, `job-profile.json`, `runner.py` and the tool's own `.gitignore`. That `.gitignore` already excludes `profile.*`, `job-*.json` and `runner.*`. Only `.fast/.gitignore` and `.fast/state.json` appear in `git status`. No `.fast/ports/` directory exists.
- The workload script was a temporary file outside the repo. Its full text is in the appendix, so the run can be reproduced.

## Appendix: workload script

Place it in the repo root before running it. fast-anything rates every function as not importable when the entry script sits outside the project folder.

```python
"""No-hardware workload for profiling Flow8Service. Real port opens are denied; MIDI goes to a MagicMock."""
import ctypes
import os
import sys

REPO = r"C:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888"
sys.path.insert(0, REPO)
os.chdir(REPO)
for name in ("FLOW8_HW_TESTS", "FLOW8_HW_TESTS_MUTATE"):
    if os.environ.get(name):
        sys.exit(f"REFUSED: {name} is set")

winmm = ctypes.windll.winmm


def _deny(*_a, **_k):
    raise AssertionError("physical port open attempted")


winmm.midiOutOpen = _deny
winmm.midiInOpen = _deny

from flow8.service import Flow8Service  # noqa: E402
from tests._safety_helpers import fake_open_port  # noqa: E402

svc = Flow8Service(auto_connect=False)
_, driver = fake_open_port(svc.midi_out)

ROUNDS = int(os.environ.get("FLOW8_WORKLOAD_ROUNDS", "60"))
for r in range(ROUNDS):
    for ch in range(1, 8):
        for v in range(0, 128, 8):  # fader drag
            svc.set_fader(ch, (v + r) % 128)
        svc.set_pan(ch, (r * 7) % 128)
        svc.set_mute(ch, r % 2 == 0)
        for band in ("low", "low_mid", "hi_mid", "hi"):
            svc.set_eq_band(ch, band, (r * 5 + ch) % 31 - 15, unit="dB")
        for target in ("mon1", "mon2", "fx1", "fx2"):
            svc.set_send(ch, target, (r * 3 + ch) % 128)
    for bus in ("main", "mon1", "mon2"):
        svc.set_bus_fader(bus, (r * 11) % 128)
    if r % 10 == 0:
        svc.capture_scene(f"s{r}")
    for _ in range(5):
        svc.undo()
    for _ in range(5):
        svc.redo()
    if r % 10 == 5:
        svc.recall_scene(f"s{r - 5}")

print("messages sent to fake driver:", driver.midiOutShortMsg.call_count)
```

**DECISION: NO RUST PORTING — PYTHON ARCHITECTURE RETAINED**
