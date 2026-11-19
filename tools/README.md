# tools/

Diagnostic scripts. They are not part of the application: `flow8/` and `main.py` never import this package, and the PyInstaller spec bundles `main.py` only.

Rules (S1.2, decisions D4 and G-07):

- **No arbitrary MIDI.** `flow8_midi_harness.py` sends nothing unless `--allow-write` is given, and every message passes `flow8.safety.validate_outbound` (control change only, allowlisted pairs only). Program Change (including the mixer reset), Note, SysEx, gain and unauthorised +48V are refused.
- **Never overwrite evidence.** Every script writes a new file named `<stem>_<UTC timestamp>_p<pid>_<n>.<ext>` created in exclusive mode. Default directory: `tools/output/`. The historical logs (`FLOW8_PHASE1_RAW_MIDI_LOG.md`, `FLOW8_PHASE2B_RAW_MIDI_LOG.md`, `docs/audit/hw_stage1/*`) are never opened for writing.
- **No hardware in tests.** `run_tests_no_hw.py` runs the suite with the real `midiOutOpen`/`midiInOpen` replaced by counters that raise.
- **The probe is read-only.** `hw_probe.py` enumerates devices, opens MIDI IN only, and starts the USB capture meter. It has no outbound path at all: no service setter, no command boundary, no `midiOutShortMsg`. `--safe` is accepted so a shell history shows the intent, and the JSON report always carries `"sentMidi": false`.

Commands (from the repository root):

```text
python -m tools.flow8_midi_harness                 # prints help, sends nothing
python -m tools.flow8_midi_harness --allow-write   # fixed safe fader/mute/pan list; needs the mixer
python -m tools.flow8_midi_in_logger --duration 22.5
python -m tools.hw_probe --safe                    # read-only readiness probe; never sends MIDI
python -m tools.run_tests_no_hw
python -m tools.test_inventory
python -m tools.hw_verify_stage1 d01 90            # Stage 1 capture script (unique outputs)
python -m tools.capture_stage1                     # Stage 1 screenshots (unique outputs)
```

The original root-level `flow8_midi_harness.py` and `flow8_midi_in_logger.py` and the Stage 1 scripts under `docs/audit/stage1_screenshots/` are kept unchanged until the owner approves their removal.
