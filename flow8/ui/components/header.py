"""Application header showing product identity and truthful MIDI port state."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

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
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        on_retry: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["background"],
            height=theme.HEADER_HEIGHT,
        )
        self.grid_propagate(False)
        self.fonts = fonts
        self.status = status
        self._callbacks = {
            "CONNECT": on_connect,
            "DISCONNECT": on_disconnect,
            "RETRY": on_retry,
        }
        self.connection_buttons: dict[str, tk.Button] = {}
        self.device_status_var = tk.StringVar(
            value="MIDI PORTS CLOSED"
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
        """CONNECT / DISCONNECT / RETRY, packed left of the status pill."""
        colors = theme.COLORS
        controls = tk.Frame(self, bg=colors["background"])
        controls.pack(side="right", padx=(0, theme.TOKENS["spacing_medium"]), pady=16)
        for label in ("CONNECT", "DISCONNECT", "RETRY"):
            callback = self._callbacks[label]
            button = tk.Button(
                controls,
                text=label,
                font=self.fonts["caption"],
                bg=colors["surface_alt"],
                fg=colors["text"],
                activebackground=colors["cyan"],
                activeforeground=colors["background"],
                disabledforeground=colors["text_muted"],
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=5,
                state="normal" if callback else "disabled",
                command=callback or (lambda: None),
            )
            button.pack(side="left", padx=(0, 4))
            self.connection_buttons[label] = button

    def set_connection_controls(self, connect: bool, disconnect: bool, retry: bool) -> None:
        """Enable only the actions that make sense for the current connection state."""
        for label, enabled in (("CONNECT", connect), ("DISCONNECT", disconnect), ("RETRY", retry)):
            allowed = enabled and self._callbacks[label] is not None
            self.connection_buttons[label].configure(state="normal" if allowed else "disabled")

    def set_connection_busy(self, text: str) -> None:
        """Show an attempt in progress; the next port-status update replaces it."""
        colors = theme.COLORS
        self.device_status_var.set(text)
        self.pill.configure(highlightbackground=colors["warning"])
        self.status_label.configure(fg=colors["warning"])
        self.dot.itemconfig(self.dot_oval, fill=colors["warning"])

    def set_midi_port_status(
        self,
        midi_out_open: bool,
        midi_in_open: bool,
        error: str | None = None,
        midi_in_listening: bool = False,
    ) -> None:
        """Show open endpoint state without claiming FLOW 8 hardware confirmation."""
        colors = theme.COLORS
        if midi_out_open and midi_in_open and midi_in_listening:
            label = "MIDI PORTS OPEN"
            color = colors["success"]
        elif midi_out_open or midi_in_open:
            label = "MIDI PORTS PARTIAL"
            color = colors["warning"]
        elif error:
            label = "MIDI PORTS ERROR"
            color = colors["danger"]
        else:
            label = "MIDI PORTS CLOSED"
            color = colors["text_muted"]

        self.device_status_var.set(label)
        self.pill.configure(highlightbackground=color)
        self.status_label.configure(fg=color)
        self.dot.itemconfig(self.dot_oval, fill=color)

    def _divider(self, parent: tk.Misc, padx: int, height: int) -> tk.Frame:
        divider = tk.Frame(parent, bg=theme.COLORS["border"], width=1, height=height)
        divider.pack(side="left", padx=padx, fill="y")
        divider.pack_propagate(False)
        return divider

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered in the header."""
        return widget_texts(self)
