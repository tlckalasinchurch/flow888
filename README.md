# Flow888 / Flow8 Mixer

Hardware-independent Python reference implementation of the Flow8 command boundary.

- `flow8/ledger.py`: bounded 50-entry undo/redo ledger with drag batching.
- `flow8/scenes.py`: up to eight named snapshots containing fader, pan and mute only.
- `flow8/service.py`: stateful service and MIDI dispatch boundary.
- `flow8/mixer_console.py`: small Tk UI with keyboard shortcuts and scene controls.

Run tests with `python -m pytest -q` and launch the demo with `python -m flow8.app`.
