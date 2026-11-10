"""Reusable widgets for the FLOW 8 Cyber Neon shell (UI.2-T1)."""

from __future__ import annotations

import tkinter as tk


def widget_texts(widget: tk.Misc) -> list[str]:
    """Return every static label string rendered inside *widget*, depth-first.

    Used by the UI test suite to assert what the shell actually shows without
    depending on widget class names or layout order.
    """
    found: list[str] = []
    try:
        text = widget.cget("text")
    except tk.TclError:
        text = ""
    if text:
        found.append(str(text))
    for child in widget.winfo_children():
        found.extend(widget_texts(child))
    return found
