"""Cyber Neon design tokens for the FLOW 8 desktop shell (UI.2-T1).

Presentation-only module. It defines colour, spacing and typography values and
resolves font families against the fonts actually installed on this machine.
It performs no hardware access and transmits no MIDI.

Rendering honesty — what Tk can and cannot do here:

* Tk's classic widgets draw square corners and expose no blur or shadow
  primitive. The radius tokens below are recorded for future canvas-drawn
  controls; this build does NOT render rounded corners and does not claim to.
* The "glow" in this shell is approximated with layered 1 px borders, accent
  bars and surface contrast. No blur filter is applied or implied.
* Tk has no animation or transition primitive, so no state change is animated
  in this build. Nothing in the interface flashes or pulses.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

# ---------------------------------------------------------------------------
# Colour palette — CYBER NEON / balanced glow
# ---------------------------------------------------------------------------

COLORS = {
    "background": "#080B12",
    "background_alt": "#0D1220",
    "surface": "#131A28",
    "surface_alt": "#1A2435",
    "surface_hover": "#202D40",
    "border": "#29384B",

    "text": "#F4F7FF",
    "text_secondary": "#A4B1C6",
    "text_muted": "#68788F",

    "cyan": "#00E5FF",
    "cyan_soft": "#54F0FF",
    "purple": "#A855F7",
    "purple_soft": "#C084FC",
    "lime": "#C6FF00",

    "success": "#39D98A",
    "warning": "#FFB84D",
    "danger": "#FF5470",

    # Single-pixel halo ring used behind accent surfaces. This is a dimmed
    # cyan, not a blur: it is the whole "glow" budget for a panel.
    "halo": "#0D3F49",
}

# ---------------------------------------------------------------------------
# Spacing and radius scale
# ---------------------------------------------------------------------------

TOKENS = {
    "radius_small": 8,
    "radius_medium": 12,
    "radius_large": 16,
    "spacing_small": 8,
    "spacing_medium": 12,
    "spacing_large": 20,
    "spacing_xlarge": 28,
}

# ---------------------------------------------------------------------------
# Window and layout metrics
# ---------------------------------------------------------------------------

WINDOW_TITLE = "FLOW 8 — Cyber Neon Workstation"
WINDOW_DEFAULT_SIZE = (1600, 900)
WINDOW_MIN_SIZE = (1366, 768)
# Vertical room left for the Windows taskbar when clamping to a small display.
TASKBAR_ALLOWANCE = 48

HEADER_HEIGHT = 68
STATUS_BAR_HEIGHT = 36
NAVIGATION_WIDTH = 232
NAV_ITEM_HEIGHT = 48

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONT_PREFERENCES = ("Inter", "Segoe UI", "Arial")
MONO_PREFERENCES = ("JetBrains Mono", "Cascadia Mono", "Consolas", "Courier New")


def resolve_family(root: tk.Misc, preferences: tuple[str, ...]) -> str:
    """Return the first installed font family from *preferences*.

    Falls back to Tk's own default family so the shell never fails to start
    because of a missing typeface.
    """
    installed = {name.lower(): name for name in tkfont.families(root)}
    for preference in preferences:
        match = installed.get(preference.lower())
        if match:
            return match
    return tkfont.nametofont("TkDefaultFont", root=root).actual("family")


def build_fonts(root: tk.Misc) -> dict[str, tkfont.Font]:
    """Build the shell's font set, resolving families against *root*'s fonts."""
    sans = resolve_family(root, FONT_PREFERENCES)
    mono = resolve_family(root, MONO_PREFERENCES)

    def make(family: str, size: int, weight: str = "normal") -> tkfont.Font:
        return tkfont.Font(root=root, family=family, size=size, weight=weight)

    return {
        "title": make(sans, 22, "bold"),
        "brand_meta": make(sans, 10),
        "eyebrow": make(sans, 8, "bold"),
        "nav": make(sans, 11),
        "nav_active": make(sans, 11, "bold"),
        "caption": make(sans, 8),
        "section": make(sans, 30, "bold"),
        "subtitle": make(sans, 13, "bold"),
        "body": make(sans, 10),
        "status_key": make(mono, 8),
        "status_value": make(mono, 9),
    }


def apply_base_theme(root: tk.Misc) -> None:
    """Apply the window-level Cyber Neon foundation."""
    root.configure(bg=COLORS["background"])
