"""Application header: product identity plus honest device state.

The header states what exists: the FLOW 8 product identity and the fact that
device presence has NOT been verified. It deliberately carries no connected
indicator, no animated dot, and no green "ready" affordance.
"""

from __future__ import annotations

import tkinter as tk

from flow8.ui import theme
from flow8.ui.components import widget_texts
from flow8.ui.status import SessionStatus


class Header(tk.Frame):
    """Top identity band for the FLOW 8 Cyber Neon shell."""

    def __init__(self, master: tk.Misc, fonts: dict, status: SessionStatus) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["background"],
            height=theme.HEADER_HEIGHT,
        )
        # Fixed height band: children must never resize the header.
        self.grid_propagate(False)
        self.fonts = fonts
        self.status = status
        #: Single source of the header's device claim; asserted by tests.
        self.device_status_var = tk.StringVar(
            value=f"DEVICE STATUS: {status.device}"
        )
        self._build()

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        identity = tk.Frame(self, bg=colors["background"])
        identity.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(spacing["spacing_large"], 0),
        )

        accent = tk.Frame(identity, bg=colors["cyan"], width=4, height=30)
        accent.pack(side="left", padx=(0, spacing["spacing_medium"]))
        accent.pack_propagate(False)

        tk.Label(
            identity,
            text="FLOW 8",
            font=self.fonts["title"],
            fg=colors["text"],
            bg=colors["background"],
        ).pack(side="left")

        self._divider(identity, padx=spacing["spacing_medium"], height=26)

        tk.Label(
            identity,
            text="CYBER NEON WORKSTATION",
            font=self.fonts["eyebrow"],
            fg=colors["cyan_soft"],
            bg=colors["background"],
        ).pack(side="left")

        self._divider(identity, padx=spacing["spacing_medium"], height=18)

        tk.Label(
            identity,
            text="Behringer FLOW 8",
            font=self.fonts["brand_meta"],
            fg=colors["text_muted"],
            bg=colors["background"],
        ).pack(side="left")

        self._build_device_pill()

        # Single hairline closing the band; the shell's only strong separator.
        tk.Frame(self, bg=colors["border"], height=1).place(
            relx=0.0, rely=1.0, relwidth=1.0, anchor="sw"
        )

    def _build_device_pill(self) -> None:
        """Amber outline pill: attention, never a connection affirmation."""
        colors = theme.COLORS
        pill = tk.Frame(
            self,
            bg=colors["surface"],
            highlightbackground=colors["warning"],
            highlightthickness=1,
            bd=0,
        )
        pill.pack(
            side="right",
            padx=(0, theme.TOKENS["spacing_large"]),
            pady=16,
        )

        dot = tk.Canvas(
            pill,
            width=8,
            height=8,
            bg=colors["surface"],
            highlightthickness=0,
            bd=0,
        )
        dot.pack(side="left", padx=(10, 6))
        dot.create_oval(1, 1, 7, 7, fill=colors["warning"], outline="")

        tk.Label(
            pill,
            textvariable=self.device_status_var,
            font=self.fonts["caption"],
            fg=colors["warning"],
            bg=colors["surface"],
            padx=0,
            pady=6,
        ).pack(side="left", padx=(0, 10))

    def _divider(self, parent: tk.Misc, padx: int, height: int) -> tk.Frame:
        divider = tk.Frame(parent, bg=theme.COLORS["border"], width=1, height=height)
        divider.pack(side="left", padx=padx, fill="y")
        divider.pack_propagate(False)
        return divider

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered in the header."""
        return widget_texts(self)
