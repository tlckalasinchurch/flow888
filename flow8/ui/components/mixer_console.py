"""7-Strip Mixer Console Component for FLOW 8 Cyber Neon Workstation.

Renders exactly 7 logical channel strips plus 1 Main L/R master strip
according to the Behringer FLOW 8 Hardware Domain Model.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.parameter_mapping import fader_midi_to_db, pan_midi_to_percent
from flow8.ui import theme


def format_db(raw_val: int) -> str:
    """Format raw 0-127 MIDI value as user-friendly dB string."""
    if raw_val <= 0:
        return "-inf dB"
    db = fader_midi_to_db(raw_val)
    if db >= 0:
        return f"+{db:.1f} dB"
    return f"{db:.1f} dB"


def format_pan(raw_val: int) -> str:
    """Format raw 0-127 MIDI value as Pan/Balance string."""
    pct = pan_midi_to_percent(raw_val)
    if pct == 0.0:
        return "C"
    elif pct < 0:
        return f"L{abs(int(pct))}"
    else:
        return f"R{int(pct)}"


class ChannelStripWidget(tk.Frame):
    """Single channel strip widget inside the mixer console."""

    def __init__(
        self,
        master: tk.Misc,
        channel_index: int,
        title: str,
        subtitle: str,
        kind_badge: str,
        pan_label: str,
        has_phantom: bool,
        fonts: dict,
        service: Any = None,
        is_master: bool = False,
    ) -> None:
        colors = theme.COLORS
        super().__init__(
            master,
            bg=colors["surface"],
            highlightbackground=colors["cyan"] if is_master else colors["border"],
            highlightthickness=1,
            bd=0,
            padx=8,
            pady=8,
        )
        self.channel_index = channel_index
        self.is_master = is_master
        self.fonts = fonts
        self.service = service
        self.has_phantom = has_phantom
        self._is_updating = False

        # State tracking
        self.fader_val = tk.IntVar(value=101 if is_master else 0)  # default unity for main, 0 for inputs
        self.pan_val = tk.IntVar(value=64)  # center
        self.is_muted = tk.BooleanVar(value=False)
        self.is_phantom = tk.BooleanVar(value=False)

        self.db_label_var = tk.StringVar(value=format_db(self.fader_val.get()))
        self.pan_label_var = tk.StringVar(value=format_pan(self.pan_val.get()))

        self._build(title, subtitle, kind_badge, pan_label)

    def _build(self, title: str, subtitle: str, kind_badge: str, pan_label: str) -> None:
        colors = theme.COLORS

        # 1. Strip Header
        hdr = tk.Frame(self, bg=colors["surface"])
        hdr.pack(fill="x", pady=(0, 6))

        # Channel Number & Type Badge
        top_row = tk.Frame(hdr, bg=colors["surface"])
        top_row.pack(fill="x")

        ch_num_text = "MAIN" if self.is_master else f"{self.channel_index:02d}"
        tk.Label(
            top_row,
            text=ch_num_text,
            font=self.fonts["eyebrow"],
            fg=colors["cyan"] if self.is_master else colors["cyan_soft"],
            bg=colors["surface"],
        ).pack(side="left")

        tk.Label(
            top_row,
            text=kind_badge,
            font=self.fonts["caption"],
            fg=colors["purple_soft"] if not self.is_master else colors["lime"],
            bg=colors["surface_alt"],
            padx=4,
            pady=1,
        ).pack(side="right")

        # Name
        tk.Label(
            hdr,
            text=title,
            font=self.fonts["subtitle"] if self.is_master else self.fonts["nav_active"],
            fg=colors["text"],
            bg=colors["surface"],
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        tk.Label(
            hdr,
            text=subtitle,
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["surface"],
            anchor="w",
        ).pack(fill="x")

        # Divider
        tk.Frame(self, bg=colors["border"], height=1).pack(fill="x", pady=6)

        # 2. Phantom Power (if supported, e.g. Ch 1 & 2)
        if self.has_phantom:
            self.phantom_btn = tk.Button(
                self,
                text="+48V",
                font=self.fonts["caption"],
                bg=colors["surface_alt"],
                fg=colors["text_muted"],
                activebackground=colors["warning"],
                activeforeground=colors["background"],
                bd=0,
                relief="flat",
                cursor="hand2",
                pady=2,
                command=self._toggle_phantom,
            )
            self.phantom_btn.pack(fill="x", pady=(0, 6))

        # 3. Pan / Balance Control
        pan_frame = tk.Frame(self, bg=colors["surface"])
        pan_frame.pack(fill="x", pady=(0, 6))

        pan_top = tk.Frame(pan_frame, bg=colors["surface"])
        pan_top.pack(fill="x")
        tk.Label(
            pan_top,
            text=pan_label,
            font=self.fonts["caption"],
            fg=colors["text_secondary"],
            bg=colors["surface"],
        ).pack(side="left")

        tk.Label(
            pan_top,
            textvariable=self.pan_label_var,
            font=self.fonts["status_key"],
            fg=colors["cyan_soft"],
            bg=colors["surface"],
        ).pack(side="right")

        self.pan_scale = tk.Scale(
            pan_frame,
            from_=0,
            to=127,
            orient="horizontal",
            showvalue=False,
            variable=self.pan_val,
            bg=colors["surface_alt"],
            troughcolor=colors["background"],
            activebackground=colors["cyan"],
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            length=110,
            command=self._on_pan_drag,
        )
        self.pan_scale.pack(fill="x", pady=(2, 0))

        # 4. Mute Button (Inputs only)
        if not self.is_master:
            self.mute_btn = tk.Button(
                self,
                text="MUTE",
                font=self.fonts["eyebrow"],
                bg=colors["surface_alt"],
                fg=colors["text_secondary"],
                activebackground=colors["danger"],
                activeforeground=colors["text"],
                bd=0,
                relief="flat",
                cursor="hand2",
                pady=6,
                command=self._toggle_mute,
            )
            self.mute_btn.pack(fill="x", pady=(4, 8))
        else:
            # Spacer for alignment
            tk.Frame(self, bg=colors["surface"], height=32).pack(fill="x", pady=(4, 8))

        # 5. Fader Level dB readout
        tk.Label(
            self,
            textvariable=self.db_label_var,
            font=self.fonts["status_value"],
            fg=colors["cyan"] if self.is_master else colors["text"],
            bg=colors["background_alt"],
            pady=4,
        ).pack(fill="x", pady=(0, 6))

        # 6. Vertical Volume Fader
        fader_container = tk.Frame(self, bg=colors["surface"])
        fader_container.pack(fill="both", expand=True, pady=(0, 6))

        self.fader_scale = tk.Scale(
            fader_container,
            from_=127,
            to=0,
            orient="vertical",
            showvalue=False,
            variable=self.fader_val,
            bg=colors["surface_alt"],
            troughcolor=colors["background"],
            activebackground=colors["cyan"] if self.is_master else colors["cyan_soft"],
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            width=16,
            command=self._on_fader_drag,
        )
        self.fader_scale.pack(fill="both", expand=True)

        # 7. Strip Footer Number
        tk.Label(
            self,
            text=ch_num_text,
            font=self.fonts["eyebrow"],
            fg=colors["text_muted"],
            bg=colors["surface"],
        ).pack(side="bottom", pady=(4, 0))

    # -- User Interactions --------------------------------------------------

    def _on_fader_drag(self, val_str: str) -> None:
        if self._is_updating:
            return
        val = int(val_str)
        self.db_label_var.set(format_db(val))
        if self.service and self.service.is_connected:
            self.service.set_fader(self.channel_index, val)

    def _on_pan_drag(self, val_str: str) -> None:
        if self._is_updating:
            return
        val = int(val_str)
        self.pan_label_var.set(format_pan(val))
        if self.service and self.service.is_connected:
            self.service.set_pan(self.channel_index, val)

    def _toggle_mute(self) -> None:
        new_mute = not self.is_muted.get()
        self.is_muted.set(new_mute)
        self._update_mute_ui(new_mute)
        if self.service and self.service.is_connected:
            self.service.set_mute(self.channel_index, new_mute)

    def _update_mute_ui(self, muted: bool) -> None:
        colors = theme.COLORS
        if hasattr(self, "mute_btn"):
            if muted:
                self.mute_btn.configure(
                    bg=colors["danger"],
                    fg=colors["text"],
                    text="MUTED",
                )
            else:
                self.mute_btn.configure(
                    bg=colors["surface_alt"],
                    fg=colors["text_secondary"],
                    text="MUTE",
                )

    def _toggle_phantom(self) -> None:
        new_val = not self.is_phantom.get()
        self.is_phantom.set(new_val)
        colors = theme.COLORS
        if new_val:
            self.phantom_btn.configure(bg=colors["warning"], fg=colors["background"])
        else:
            self.phantom_btn.configure(bg=colors["surface_alt"], fg=colors["text_muted"])
        if self.service and self.service.is_connected:
            self.service.set_phantom(self.channel_index, new_val)

    # -- External Sync Updates (from Hardware MIDI) ------------------------

    def sync_fader(self, raw_val: int) -> None:
        self._is_updating = True
        try:
            self.fader_val.set(raw_val)
            self.db_label_var.set(format_db(raw_val))
        finally:
            self._is_updating = False

    def sync_pan(self, raw_val: int) -> None:
        self._is_updating = True
        try:
            self.pan_val.set(raw_val)
            self.pan_label_var.set(format_pan(raw_val))
        finally:
            self._is_updating = False

    def sync_mute(self, is_muted: bool) -> None:
        self.is_muted.set(is_muted)
        self._update_mute_ui(is_muted)


class MixerConsole(tk.Frame):
    """Container holding the 7 logical input channel strips + 1 Master strip."""

    def __init__(self, master: tk.Misc, fonts: dict, service: Any = None) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.strips: Dict[int, ChannelStripWidget] = {}
        self._build()

        if self.service:
            self.service.add_listener(self._on_service_param_update)

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        # Console Header Banner
        banner = tk.Frame(self, bg=colors["background"])
        banner.pack(fill="x", padx=spacing["spacing_large"], pady=(spacing["spacing_medium"], spacing["spacing_small"]))

        tk.Label(
            banner,
            text="FLOW 8 MIXER CONSOLE",
            font=self.fonts["subtitle"],
            fg=colors["cyan"],
            bg=colors["background"],
        ).pack(side="left")

        tk.Label(
            banner,
            text="7 LOGICAL STRIPS + MAIN L/R MASTER",
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["background"],
        ).pack(side="left", padx=(spacing["spacing_medium"], 0))

        # Strips Container
        strips_container = tk.Frame(self, bg=colors["background"])
        strips_container.pack(fill="both", expand=True, padx=spacing["spacing_large"], pady=(0, spacing["spacing_large"]))

        # Grid configuration: 8 columns (1-7 strips + 8 main)
        for col in range(8):
            strips_container.grid_columnconfigure(col, weight=1, uniform="strip")
        strips_container.grid_rowconfigure(0, weight=1)

        # Strip Metadata definitions according to FLOW 8 Domain Model
        specs = [
            (1, "Mic 1", "Midas Preamp", "XLR", "PAN", True),
            (2, "Mic 2", "Midas Preamp", "XLR", "PAN", True),
            (3, "Line 3", "Mic / Line", "COMBO", "PAN", False),
            (4, "Line 4", "Mic / Line", "COMBO", "PAN", False),
            (5, "Ch 5/6", "Stereo Line / Hi-Z", "TRS", "BAL", False),
            (6, "Ch 7/8", "Stereo Line / Hi-Z", "TRS", "BAL", False),
            (7, "USB / BT", "Audio Return", "USB", "BAL", False),
        ]

        for idx, title, subtitle, kind_badge, pan_label, has_phantom in specs:
            strip = ChannelStripWidget(
                master=strips_container,
                channel_index=idx,
                title=title,
                subtitle=subtitle,
                kind_badge=kind_badge,
                pan_label=pan_label,
                has_phantom=has_phantom,
                fonts=self.fonts,
                service=self.service,
                is_master=False,
            )
            strip.grid(row=0, column=idx - 1, sticky="nsew", padx=3, pady=2)
            self.strips[idx] = strip

        # Master Strip (Main L/R, channel_index=8)
        master_strip = ChannelStripWidget(
            master=strips_container,
            channel_index=8,
            title="Main L/R",
            subtitle="Master Output",
            kind_badge="MASTER",
            pan_label="BAL",
            has_phantom=False,
            fonts=self.fonts,
            service=self.service,
            is_master=True,
        )
        master_strip.grid(row=0, column=7, sticky="nsew", padx=(8, 3), pady=2)
        self.strips[8] = master_strip

    def _on_service_param_update(self, param_id: str, value: Any) -> None:
        """Handle incoming hardware state updates from service (thread-safe dispatch to Tk)."""
        try:
            self.after_idle(lambda: self._apply_update(param_id, value))
        except Exception:
            pass

    def _apply_update(self, param_id: str, value: Any) -> None:
        """Apply parameter update on Tkinter main thread."""
        parts = param_id.split(".")
        if len(parts) != 2:
            return
        target, param = parts[0], parts[1]

        ch = None
        if target.startswith("ch") and target[2:].isdigit():
            ch = int(target[2:])
        elif target == "main":
            ch = 8

        if ch and ch in self.strips:
            strip = self.strips[ch]
            if param == "fader":
                strip.sync_fader(int(value))
            elif param in ("pan", "balance"):
                strip.sync_pan(int(value))
            elif param == "mute":
                strip.sync_mute(bool(value))
