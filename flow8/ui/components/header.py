"""Application header: product identity plus device state.

The header states what exists: the FLOW 8 product identity and the live
connection status to the hardware.
"""

from __future__ import annotations

import tkinter as tk

from flow8.ui import theme
from flow8.ui.components import widget_texts
from flow8.ui.status import SessionStatus


class Header(tk.Frame):
    """Top identity band for the FLOW 8 Cyber Neon shell."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        status: SessionStatus,
        on_connect=None,
        on_disconnect=None,
        on_retry=None,
    ) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["background"],
            height=theme.HEADER_HEIGHT,
        )
        self.grid_propagate(False)
        self.fonts = fonts
        self.status = status
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_retry = on_retry
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
        self._build_connection_controls()

        # Hairline closing the band
        tk.Frame(self, bg=colors["border"], height=1).place(
            relx=0.0, rely=1.0, relwidth=1.0, anchor="sw"
        )

    def _build_device_pill(self) -> None:
        colors = theme.COLORS
        self.pill = tk.Frame(
            self,
            bg=colors["surface"],
            highlightbackground=colors["warning"],
            highlightthickness=1,
            bd=0,
        )
        self.pill.pack(
            side="right",
            padx=(0, theme.TOKENS["spacing_large"]),
            pady=16,
        )

        self.dot = tk.Canvas(
            self.pill,
            width=8,
            height=8,
            bg=colors["surface"],
            highlightthickness=0,
            bd=0,
        )
        self.dot.pack(side="left", padx=(10, 6))
        self.dot_oval = self.dot.create_oval(1, 1, 7, 7, fill=colors["warning"], outline="")

        self.status_label = tk.Label(
            self.pill,
            textvariable=self.device_status_var,
            font=self.fonts["caption"],
            fg=colors["warning"],
            bg=colors["surface"],
            padx=0,
            pady=6,
        )
        self.status_label.pack(side="left", padx=(0, 10))

    def _build_connection_controls(self) -> None:
        colors = theme.COLORS
        controls = tk.Frame(self, bg=colors["background"])
        controls.pack(side="right", padx=(0, theme.TOKENS["spacing_medium"]))
        for label, callback in (
            ("CONNECT", self.on_connect),
            ("DISCONNECT", self.on_disconnect),
            ("RETRY", self.on_retry),
        ):
            tk.Button(
                controls,
                text=label,
                command=callback,
                font=self.fonts["caption"],
                bg=colors["surface_alt"],
                fg=colors["text_secondary"],
                activebackground=colors["cyan"],
                activeforeground=colors["background"],
                bd=0,
                relief="flat",
                padx=6,
                pady=3,
            ).pack(side="left", padx=2)

    def set_device_status(self, is_connected: bool, device_name: str = "FLOW 8") -> None:
        """Update the header device status pill."""
        colors = theme.COLORS
        if is_connected:
            self.device_status_var.set(f"DEVICE STATUS: {device_name} CONNECTED")
            self.pill.configure(highlightbackground=colors["success"])
            self.status_label.configure(fg=colors["success"])
            self.dot.itemconfig(self.dot_oval, fill=colors["success"])
        else:
            self.device_status_var.set("DEVICE STATUS: NOT CONNECTED")
            self.pill.configure(highlightbackground=colors["warning"])
            self.status_label.configure(fg=colors["warning"])
            self.dot.itemconfig(self.dot_oval, fill=colors["warning"])

    def _divider(self, parent: tk.Misc, padx: int, height: int) -> tk.Frame:
        divider = tk.Frame(parent, bg=theme.COLORS["border"], width=1, height=height)
        divider.pack(side="left", padx=padx, fill="y")
        divider.pack_propagate(False)
        return divider

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered in the header."""
        return widget_texts(self)
