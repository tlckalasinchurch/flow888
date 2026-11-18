"""Evidence-safe output helpers: every tool writes a NEW file and never touches an existing one.

Files are created with exclusive-create mode ("x"), so an existing file (for example a historical
evidence log) can never be opened for writing. Names carry a UTC timestamp and the process id.
"""
import datetime
import os
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def open_exclusive(path):
    """Open a new text file for writing. Raises FileExistsError if it already exists."""
    return open(path, "x", encoding="utf-8")


def _open_exclusive_bytes(path):
    return open(path, "xb")


def _candidate(directory, stem, suffix, n):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path(directory) / f"{stem}_{stamp}_p{os.getpid()}_{n}{suffix}"


def _write(directory, stem, suffix, data, binary):
    Path(directory).mkdir(parents=True, exist_ok=True)
    for n in range(1000):
        path = _candidate(directory, stem, suffix, n)
        try:
            handle = _open_exclusive_bytes(path) if binary else open_exclusive(path)
        except FileExistsError:
            continue
        with handle:
            handle.write(data)
        return str(path)
    raise FileExistsError(f"could not find a free name for {stem}{suffix} in {directory}")


def write_unique(directory, stem, suffix, text):
    """Write *text* to a new uniquely named file and return its path."""
    return _write(directory, stem, suffix, text, binary=False)


def write_unique_bytes(directory, stem, suffix, data):
    """Write *data* to a new uniquely named file and return its path."""
    return _write(directory, stem, suffix, data, binary=True)
