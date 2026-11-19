"""Non-destructive FLOW 8 hardware readiness probe.

```
python -m tools.hw_probe --safe
```

What it does, in order:

1. Lists the MIDI IN and MIDI OUT devices (read-only enumeration, no port opened).
2. Opens the FLOW 8 MIDI IN port only, listens for the requested number of seconds,
   and reports the telemetry the mixer actually sent (mapped CCs, unmapped CCs,
   Program Changes). It never opens MIDI OUT and never sends a message.
3. Starts the FLOW 8 USB capture meter for the same window and reports how many
   meter frames arrived, so `Multi In 1-10` reception can be checked without
   touching any mixer setting.

Safety: there is no code path here that calls a service setter, a command
boundary, or `midiOutShortMsg`. `--safe` is accepted explicitly (and is the only
mode) so a shell history shows the intent. Preamp gain and +48V are never read
or written.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Optional

from flow8.audio_meter import Flow8AudioMeter
from flow8.midi_in import Flow8MidiIn
from flow8.midi_out import Flow8MidiOut
from flow8.telemetry import decode, is_forbidden_program_reset

EXIT_OK = 0
EXIT_NO_DEVICE = 2
EXIT_ERROR = 3

SAFE_MODE = True  # no outbound path exists; --safe only makes that explicit


def is_flow8(name: str) -> bool:
    lowered = str(name).lower()
    return "flow 8" in lowered or "flow8" in lowered


def flow_devices(devices: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(d) for d in devices if is_flow8(str(d.get("name", "")))]


def summarize_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Count what the mixer sent. Pure function, shared by the CLI and its tests."""
    mapped: dict[str, dict[str, Any]] = {}
    unmapped_cc = 0
    program_changes = 0
    forbidden_resets = 0
    other = 0
    total = 0
    for raw in events:
        total += 1
        event = decode(raw)
        if event.kind == "cc":
            if event.mapped:
                entry = mapped.setdefault(event.param_id, {
                    "paramId": event.param_id,
                    "channel": event.channel,
                    "controller": event.controller,
                    "count": 0,
                    "lastValue": event.value,
                })
                entry["count"] += 1
                entry["lastValue"] = event.value
            else:
                unmapped_cc += 1
        elif event.kind == "program_change":
            program_changes += 1
            if is_forbidden_program_reset(event):
                forbidden_resets += 1
        else:
            other += 1
    return {
        "totalMessages": total,
        "mappedParameters": sorted(mapped.values(), key=lambda item: item["paramId"]),
        "mappedCount": sum(entry["count"] for entry in mapped.values()),
        "unmappedCc": unmapped_cc,
        "programChanges": program_changes,
        "forbiddenProgramResets": forbidden_resets,
        "otherMessages": other,
        "telemetryObserved": bool(mapped),
    }


def probe_midi(seconds: float, *, devices: Optional[list] = None,
               port_factory: Callable[[], Flow8MidiIn] = Flow8MidiIn) -> dict[str, Any]:
    """Listen on the FLOW 8 MIDI IN for `seconds`. Sends nothing, ever."""
    in_devices = list(devices) if devices is not None else Flow8MidiIn.list_devices()
    found = flow_devices(in_devices)
    report: dict[str, Any] = {
        "devices": in_devices,
        "flow8Devices": found,
        "available": bool(found),
        "listenedSeconds": max(0.0, float(seconds)),
        "events": [],
    }
    if not found:
        return report

    port = port_factory()
    events: list[dict[str, Any]] = []
    port.register_callback(events.append)
    try:
        port.open(int(found[0]["index"]))
        port.start()
        if seconds > 0:
            time.sleep(seconds)
    finally:
        try:
            port.close()
        except Exception:
            pass
    report["events"] = events
    report["summary"] = summarize_events(events)
    return report


def probe_audio(seconds: float, *,
                meter_factory: Callable[..., Flow8AudioMeter] = Flow8AudioMeter) -> dict[str, Any]:
    """Run the USB capture meter for `seconds` and report frames received."""
    frames = {"count": 0, "levels": {}}
    statuses: list[dict[str, Any]] = []

    def publish(levels: Mapping[str, Mapping[str, float]]) -> None:
        frames["count"] += 1
        frames["levels"] = dict(levels)

    def on_status(status: Mapping[str, Any]) -> None:
        statuses.append(dict(status))

    meter = meter_factory(publish, on_status)
    started = bool(meter.start())
    # Capture the reason before stop() replaces it with "Meters are off".
    start_status = dict(getattr(meter, "status", {}))
    try:
        if started:
            deadline = time.monotonic() + max(0.0, float(seconds))
            while time.monotonic() < deadline:
                time.sleep(0.1)
    finally:
        try:
            meter.stop()
        except Exception:
            pass
    return {
        "started": started,
        "framesReceived": frames["count"],
        "metering": started and frames["count"] > 0,
        "levels": frames["levels"],
        "status": start_status,
        "statusHistory": statuses[-5:],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "safe": SAFE_MODE,
        "sentMidi": False,
        "midiOutDevices": Flow8MidiOut.list_devices(),
        "midiInDevices": Flow8MidiIn.list_devices(),
    }
    midi = {"available": bool(flow_devices(report["midiInDevices"])),
            "skipped": True, "flow8Devices": flow_devices(report["midiInDevices"])}
    if not args.no_midi:
        midi = probe_midi(args.seconds)
        midi["skipped"] = False
    report["midi"] = midi

    audio = {"skipped": True, "metering": False}
    if not args.no_audio:
        audio = probe_audio(args.seconds)
        audio["skipped"] = False
    report["audio"] = audio

    report["ready"] = {
        "midiIn": bool(midi.get("flow8Devices")),
        "telemetry": bool(midi.get("summary", {}).get("telemetryObserved")),
        "usbMeters": bool(audio.get("metering")),
        "programChangeObserved": int(midi.get("summary", {}).get("programChanges", 0) or 0),
    }
    return report


def format_report(report: Mapping[str, Any]) -> str:
    lines = [
        "FLOW 8 SAFE HARDWARE PROBE (no MIDI is sent)",
        f"  MIDI IN  devices: {', '.join(d['name'] for d in report['midiInDevices']) or 'none'}",
        f"  MIDI OUT devices: {', '.join(d['name'] for d in report['midiOutDevices']) or 'none'}",
    ]
    midi = report.get("midi", {})
    if midi.get("skipped"):
        lines.append("  MIDI IN listen: skipped (--no-midi)")
    elif not midi.get("available"):
        lines.append("  MIDI IN listen: NO FLOW 8 MIDI IN FOUND")
    else:
        summary = midi.get("summary", {})
        lines += [
            f"  MIDI IN listen: {midi['listenedSeconds']:.1f}s on {midi['flow8Devices'][0]['name']}",
            f"    messages {summary.get('totalMessages', 0)} | mapped CC {summary.get('mappedCount', 0)}"
            f" | unmapped CC {summary.get('unmappedCc', 0)} | PC {summary.get('programChanges', 0)}",
        ]
        for entry in summary.get("mappedParameters", [])[:12]:
            lines.append(f"    {entry['paramId']}: {entry['count']} message(s), last {entry['lastValue']}")
        if not summary.get("telemetryObserved"):
            lines.append("    no allowlisted telemetry arrived; move a fader on the mixer and retry")
    audio = report.get("audio", {})
    if audio.get("skipped"):
        lines.append("  USB meters: skipped (--no-audio)")
    else:
        lines.append(
            f"  USB meters: {'RUNNING' if audio.get('metering') else 'NOT RECEIVING'}"
            f" | frames {audio.get('framesReceived', 0)} | status {audio.get('status', {}).get('state')}"
            f" ({audio.get('status', {}).get('detail')})"
        )
        for strip, level in list(audio.get("levels", {}).items())[:6]:
            lines.append(f"    {strip}: peak {level.get('peak')} dBFS / rms {level.get('rms')} dBFS")
    ready = report.get("ready", {})
    lines.append(
        "  READY: MIDI IN " + ("yes" if ready.get("midiIn") else "no")
        + " | telemetry " + ("yes" if ready.get("telemetry") else "not observed")
        + " | USB meters " + ("yes" if ready.get("usbMeters") else "no")
        + " | Program Change observed " + str(ready.get("programChangeObserved", 0))
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.hw_probe",
        description="Read-only FLOW 8 readiness probe. It never sends MIDI.",
    )
    parser.add_argument("--safe", action="store_true",
                        help="explicitly select the only mode (no MIDI is ever sent)")
    parser.add_argument("--seconds", type=float, default=5.0,
                        help="listen window for MIDI and audio (default 5)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--no-midi", action="store_true", help="skip the MIDI IN listen")
    parser.add_argument("--no-audio", action="store_true", help="skip the USB meter check")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_report(args)
    except Exception as error:  # a probe must never crash a show day
        if args.json:
            print(json.dumps({"safe": True, "sentMidi": False, "error": str(error)}))
        else:
            print(f"PROBE FAILED (nothing was sent): {error}")
        return EXIT_ERROR
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else format_report(report))
    if not report["midi"].get("flow8Devices"):
        return EXIT_NO_DEVICE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
