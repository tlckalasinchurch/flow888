"""Status bar showing independent MIDI port states and unintegrated capabilities."""

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
        self.feedback_var = tk.StringVar(value="")
        self.last_feedback_full = ""
        self.values: dict[str, tk.StringVar] = {
            "midi_out": tk.StringVar(value=status.midi_out),
            "midi_in": tk.StringVar(value=status.midi_in),
            "midi_error": tk.StringVar(value=status.midi_error),
            "usb_audio": tk.StringVar(value=status.usb_audio),
            "audio_telemetry": tk.StringVar(value=status.audio_telemetry),
            "hardware_observation": tk.StringVar(value=status.hardware_observation),
        }
        self.value_labels: dict[str, tk.Label] = {}
        self._build()

    def _color_for_value(self, key: str, value: str) -> str:
        colors = theme.COLORS
        if key == "midi_out":
            return colors["lime"] if value == "OPEN" else colors["danger"]
        if key == "midi_in":
            if value == "OPEN / LISTENING":
                return colors["lime"]
            if value == "OPEN / NOT LISTENING":
                return colors["warning"]
            return colors["danger"]
        return colors["text_secondary"]

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        tk.Frame(self, bg=colors["border"], height=1).place(
            relx=0.0, rely=0.0, relwidth=1.0, anchor="nw"
        )

        fields = tk.Frame(self, bg=colors["background_alt"])
        self._fields = fields
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

            val_fg = self._color_for_value(key, value)

            lbl = tk.Label(
                fields,
                textvariable=self.values[key],
                font=self.fonts["status_value"],
                fg=val_fg,
                bg=colors["background_alt"],
            )
            lbl.pack(side="left")
            self.value_labels[key] = lbl

        self._feedback_label = tk.Label(
            self,
            textvariable=self.feedback_var,
            font=self.fonts["status_key"],
            fg=colors["warning"],
            bg=colors["background_alt"],
        )
        self._feedback_label.pack(side="right", padx=(0, spacing["spacing_medium"]))
        # (The "WORKSTATION UI.2" tag that used to sit here duplicated the header and
        # took ~100 px that the feedback line needs at 1366 px.)
        self.bind("<Configure>", lambda _e: self._fit_feedback(), add="+")

    def show_feedback(self, message: str) -> None:
        """Show the latest truthful command feedback (software command, not hardware).

        The full text is kept in ``last_feedback_full``; the label shows as much as
        fits beside the port fields and ends with an ellipsis when it was cut.
        """
        self.last_feedback_full = message
        self._fit_feedback()

    def _fit_feedback(self) -> None:
        message = self.last_feedback_full
        # Field text may have just changed (e.g. a long MIDI error): let Tk recompute
        # their requested width before measuring the room that is left.
        self.update_idletasks()
        if self.winfo_width() <= 1:  # not laid out yet: nothing to measure against
            self.feedback_var.set(message)
            return
        used = (
            self._fields.winfo_reqwidth()
            + theme.TOKENS["spacing_large"]   # left padding of the field block
            + theme.TOKENS["spacing_medium"]  # right padding of this label
        )
        label = self._feedback_label
        # The label's own padding and border are part of its requested width.
        overhead = 2 * sum(
            int(float(str(label.cget(option))))
            for option in ("padx", "borderwidth", "highlightthickness")
        )
        available = self.winfo_width() - used - overhead

        def width(text: str) -> int:
            return int(self.tk.call("font", "measure", label.cget("font"), text))

        if width(message) <= available:
            self.feedback_var.set(message)
            return
        keep = len(message)
        while keep > 0 and width(message[:keep].rstrip() + "…") > available:
            keep -= 1
        self.feedback_var.set(message[:keep].rstrip() + "…" if keep else "")

    def set_midi_port_status(
        self,
        midi_out_open: bool,
        midi_in_open: bool,
        error: str | None = None,
        midi_in_listening: bool = False,
    ) -> None:
        """Render each port independently; opening MIDI is not hardware confirmation."""
        out_status = "OPEN" if midi_out_open else "CLOSED"
        self.values["midi_out"].set(out_status)
        if midi_in_open and midi_in_listening:
            in_status = "OPEN / LISTENING"
        elif midi_in_open:
            in_status = "OPEN / NOT LISTENING"
        else:
            in_status = "CLOSED"
        self.values["midi_in"].set(in_status)
        self.values["midi_error"].set((error or "NONE")[:48])
        # These capabilities remain unintegrated regardless of MIDI port state.
        self.values["usb_audio"].set("NOT INTEGRATED")
        self.values["audio_telemetry"].set("NO TELEMETRY")
        self.values["hardware_observation"].set("UNKNOWN")

        # Synchronize dynamic foreground colors with current endpoint states
        if "midi_out" in self.value_labels:
            self.value_labels["midi_out"].configure(
                fg=self._color_for_value("midi_out", out_status)
            )
        if "midi_in" in self.value_labels:
            self.value_labels["midi_in"].configure(
                fg=self._color_for_value("midi_in", in_status)
            )
        self._fit_feedback()  # the error field may now be wider or narrower

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered in the bar."""
        return widget_texts(self)
