# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A LAN web console and safety-gated control library for the Behringer FLOW 8 mixer. Windows only: MIDI goes through WinMM via `ctypes` (`flow8/midi_out.py`, `flow8/midi_in.py`). Python 3.14, standard library plus `unittest`. No package manifest, no build step for the UI. Product intent and principles: `PRODUCT.md`. Visual system and tokens: `DESIGN.md`.

## Commands

Run from the repository root.

```text
python main.py                                   # web console on the LAN + USB meters + app-mode browser window
python main.py --no-browser --no-meters --port 0 # headless; 0 picks a free port
python -m tools.run_tests_no_hw                  # full suite; real midiOutOpen/midiInOpen replaced by raising counters
python -m unittest tests.test_transport_router   # one module
python -m unittest tests.test_transport_router.TransportRouterModeTests.test_usb_mode_never_touches_ble   # one test
python -m tools.test_inventory                   # test count vs baseline (no tests may silently disappear)
python -m tools.hw_probe --safe                  # read-only hardware readiness probe; never sends MIDI
```

- Prefer `tools.run_tests_no_hw` for whole-suite runs: it reports "attempted physical port opens", which must be 0. It refuses to start if `FLOW8_HW_TESTS` or `FLOW8_HW_TESTS_MUTATE` is set.
- Hardware tests (`tests/test_hardware_midi_out.py`) run only with `FLOW8_HW_TESTS=1`; mutating ones also need `FLOW8_HW_TESTS_MUTATE=1` and a connected mixer. Do not set these unless the user asks in this session.
- Safety tests mix in `tests/_no_hardware.py::NoHardwareMixin` and use `tests/_safety_helpers.py::fake_open_port`. Enable +48 V in tests only through `authorize_phantom_on` (the real gate), never by patching around it.
- No linter or formatter is configured.

## Architecture

Command path (one direction, no shortcuts):

```
web UI (flow8/web_ui) → LAN hub HTTP/SSE (flow8/lan_hub.py) → Flow8Service (flow8/service.py)
  → Flow8ParameterEngine (parameter_engine.py, parameter_mapping.py, domain_model.py)
  → Flow8CommandBoundary.execute_command (command_boundary.py: allowlist + safety.authorize_command)
  → TransportRouter.dispatch (transport_router.py: picks exactly one writer)
  → Flow8MidiOut.send_cc (re-runs safety.validate_outbound)  |  BleTransport.send_fader (ble_transport.py)
```

- `flow8/web_console.py` is the launcher (`main.py` and `launch_studio_ui.py` both call its `main`). It starts the LAN hub, the USB audio meters (`audio_meter.py`) and the browser window.
- `flow8/lan_hub.py` serves `flow8/web_ui/` (plain HTML/CSS/JS, bundled font, must work offline) and the API: `GET /api/status|presets|presets/thai|library/export|session|events` (SSE) and `POST /api/action` (one message type per action). `LAN_LOCKED_FEATURES` lists features locked over LAN, with the reason (often an unresolved conflict in `docs/product/FLOW8_UNRESOLVED_CONFLICTS.md`).
- Transport modes (`TransportRouter.MODES`): `usb_midi` (default), `ble` (strips 1–6 faders only; fails closed with `REJECTED` when no authenticated BLE session, never falls back to USB), `hybrid` (BLE for strips 1–6 faders when ready, USB otherwise). One command, one transport, never duplicated. BLE writes do not pass `validate_outbound`; the router restricts them to the verified write set. Details: `docs/architecture/TRANSPORT_ROUTING.md`.
- Inbound: `midi_in.py` → `telemetry.py` → `state_model.py`. The mixer does not echo commands and sends no meter data over MIDI; meters come from the USB audio capture stream.
- State provenance: every value is `UNSYNCED`, `COMMANDED` or `OBSERVED`. After a disconnect everything returns to `UNSYNCED`. A driver return code is not hardware confirmation.
- Session layer in `Flow8Service`: `ledger.py` (undo/redo), `scenes.py` + `snapshot_library.py` + `library_io.py` (snapshots), `presets.py` / `presets_th.py` (presets never touch levels, gain or +48 V), `change_plan.py`, `show_mode.py` + `show_mode_store.py` (MC/BAND changeover macros).
- `tools/` holds diagnostic scripts. `flow8/` and `main.py` never import it. Scripts write only new uniquely named files under `tools/output/`.

## Safety rules (binding)

Full text and current enforcement state: `docs/product/FLOW8_SAFETY_POLICY.md` (SR-01 to SR-12). The short version:

- No Note or SysEx sender may exist in `flow8/`. The only Program Change allowed is FX preset select, data bytes 1–16 on MIDI channels 13/14 (owner decision 2026-11-20, `FLOW8_SAFETY_POLICY.md` §7), sent only by `Flow8MidiOut.send_program_change`. Channel 16 stays closed: Program Change 16 on channel 16 (mixer reset) is forbidden everywhere, including tests and scripts, and FX mute / tap tempo (also channel 16) stay locked.
- Preamp gain and +48 V are gated and never automated. +48 V needs a single-use `PhantomPowerSafetyGate` token; it is excluded from undo, scenes, presets and macros. Both are blocked over LAN.
- Enforce safety in the boundary/service, not only in the UI.
- No UI control for a parameter not documented in the manufacturer chart. Capability truth: `docs/product/FLOW8_CAPABILITY_MATRIX.md` and `docs/product/FLOW8_PARAMETER_MAPPING.md`.
- CueAir material may inform workflow but is never evidence of a FLOW 8 capability and is not named in user-facing UI.

## Evidence files

- Files listed in `docs/product/evidence_baseline.sha256` (historical MIDI logs, `docs/audit/hw_stage1/`, `docs/audit/stage1_screenshots/`, source PDFs, the root-level `flow8_midi_harness.py` and `flow8_midi_in_logger.py`) are hashed byte-for-byte by a test. Do not edit them; `.gitattributes` marks the audit folders `-text`.
- The root-level harness/logger scripts are originals kept for evidence; the maintained versions live in `tools/`.
- `docs/product/sources/` (manufacturer manuals), `app/` and `cueair_extracted/` are third-party material: never commit them.

## Docs that are partly stale

- `docs/architecture/APPLICATION_ARCHITECTURE.md` still describes the removed Tkinter UI (`flow8/ui/`) and a 315-test count.
- The enforcement column of `FLOW8_SAFETY_POLICY.md` cites `flow8/ui/` files from before S1.2; check the code before relying on it.
- The `web_console.py` docstring mentions `--legacy-tk`; the parser has no such flag.
