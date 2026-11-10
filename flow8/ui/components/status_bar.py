"""Status bar: what the software knows, and live hardware indicators.

Each value is a StringVar fed from SessionStatus or updated via hardware discovery.
"""

from __future__ import annotations

import tkinter as tk

from flow8.ui import theme
from flow8.ui.components import widget_texts
from flow8.ui.status import SessionStatus


class StatusBar(tk.Frame):
    """Bottom band of transport and capability facts."""

    def __init__(self, master: tk.Misc, fonts: dict, status: SessionStatus) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["background_alt"],
            height=theme.STATUS_BAR_HEIGHT,
        )
        self.grid_propagate(False)
        self.fonts = fonts
        self.status = status
        self.values: dict[str, tk.StringVar] = {
            "midi": tk.StringVar(value=status.midi),
            "midi_out": tk.StringVar(value=status.midi_out),
            "midi_in": tk.StringVar(value=status.midi_in),
            "usb_audio": tk.StringVar(value=status.usb_audio),
            "audio_telemetry": tk.StringVar(value=status.audio_telemetry),
            "hardware_observation": tk.StringVar(value=status.hardware_observation),
        }
        self.feedback_var = tk.StringVar(value="")
        self._build()

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        tk.Frame(self, bg=colors["border"], height=1).place(
            relx=0.0, rely=0.0, relwidth=1.0, anchor="nw"
        )

        fields = tk.Frame(self, bg=colors["background_alt"])
        fields.pack(side="left", fill="both", expand=True, padx=(spacing["spacing_large"], 0))

        for index, (label, value) in enumerate(self.status.transport_rows()):
            if index:
                divider = tk.Frame(fields, bg=colors["border"], width=1, height=14)
                divider.pack(side="left", padx=spacing["spacing_medium"])
                divider.pack_propagate(False)

            key = "".join(
                (character.lower() if character.isalnum() else "_")
                for character in label
            ).strip("_")

            tk.Label(
                fields,
                text=f"{label}:",
                font=self.fonts["status_key"],
                fg=colors["text_muted"],
                bg=colors["background_alt"],
            ).pack(side="left", padx=(0, 6))

            tk.Label(
                fields,
                textvariable=self.values[key],
                font=self.fonts["status_value"],
                fg=colors["text_secondary"],
                bg=colors["background_alt"],
            ).pack(side="left")

        tk.Label(
            self,
            textvariable=self.feedback_var,
            font=self.fonts["status_key"],
            fg=colors["warning"],
            bg=colors["background_alt"],
        ).pack(side="right", padx=(0, spacing["spacing_medium"]))
        tk.Label(
            self,
            text="WORKSTATION UI.2",
            font=self.fonts["status_key"],
            fg=colors["cyan_soft"],
            bg=colors["background_alt"],
        ).pack(side="right", padx=(0, spacing["spacing_large"]))

    def set_hardware_status(self, is_connected: bool) -> None:
        """Update status bar indicators based on live connection."""
        if is_connected:
            self.values["midi"].set("CONNECTED (MIDI I/O)")
            self.values["midi_out"].set("CONNECTED")
            self.values["midi_in"].set("CONNECTED")
            self.values["usb_audio"].set("NOT INTEGRATED")
            self.values["audio_telemetry"].set("NO TELEMETRY")
            self.values["hardware_observation"].set("UNCONFIRMED")
        else:
            self.values["midi"].set("UNKNOWN")
            self.values["midi_out"].set("DISCONNECTED")
            self.values["midi_in"].set("DISCONNECTED")
            self.values["usb_audio"].set("NOT INTEGRATED")
            self.values["audio_telemetry"].set("NO TELEMETRY")
            self.values["hardware_observation"].set("UNCONFIRMED")

    def show_feedback(self, message: str) -> None:
        """Show the latest truthful command/transport feedback."""
        self.feedback_var.set(message)

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered in the bar."""
        return widget_texts(self)
