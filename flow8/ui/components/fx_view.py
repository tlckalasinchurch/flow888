"""CueAir Gen Z/Alpha FX Rack View (Figma node 5:301).

Displays FLOW 8 FX 1 & FX 2 return bus faders (Ch 11-12, CC 7), channel FX
send overview, and the curated FX preset catalog. Continuous FX DSP parameters
(Decay, Predelay, Feedback, Slot 3) are honestly marked UNSUPPORTED on FLOW 8.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

from flow8.parameter_mapping import fader_midi_to_db
from flow8.presets import list_fx_presets
from flow8.ui import theme
from flow8.ui.components.controls import UnipolarSlider


class FxView(tk.Frame):
    """FX Rack screen aligned with Figma (5:301) with strict protocol honesty."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_feedback: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self._updating = False
        self.fx_vars = {"fx1": tk.IntVar(value=0), "fx2": tk.IntVar(value=0)}
        self.fx_labels = {"fx1": tk.StringVar(value="-inf dB"), "fx2": tk.StringVar(value="-inf dB")}
        self._build()
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_large"]

        hdr = tk.Frame(self, bg=colors["background"])
        hdr.pack(fill="x", padx=pad, pady=(pad, 10))
        tk.Label(
            hdr, text="Effects Rack", font=self.fonts["title"],
            fg=colors["text"], bg=colors["background"],
        ).pack(side="left")
        tk.Label(
            hdr, text="SEND / RETURN  ·  GLOBAL FX", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(12, 0), pady=(6, 0))

        # Status Bar
        info = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=12, pady=8,
        )
        info.pack(fill="x", padx=pad, pady=(0, 10))
        tk.Label(
            info, text="2 FX RETURN BUSES (MIDI CH 11–12)", font=self.fonts["caption"],
            fg=colors["success"], bg=colors["pill_bg"],
            highlightbackground=colors["success"], highlightthickness=1,
            padx=8, pady=2,
        ).pack(side="left")
        tk.Label(
            info,
            text="Slot Program Change & Decay/Predelay/Feedback knobs are UNSUPPORTED / NOT IN ALLOWLIST",
            font=self.fonts["caption"], fg=colors["warning"], bg=colors["surface"],
        ).pack(side="right")

        # FX 1 & FX 2 Return Fader Cards
        slots = tk.Frame(self, bg=colors["background"])
        slots.pack(fill="x", padx=pad, pady=(0, 10))

        for idx, (bus_id, title, desc, border_col) in enumerate((
            ("fx1", "01  FX 1 RETURN (REVERB)", "Master FX 1 return level · MIDI Ch 11 CC 7", colors["purple"]),
            ("fx2", "02  FX 2 RETURN (DELAY / MOD)", "Master FX 2 return level · MIDI Ch 12 CC 7", colors["cyan"]),
        )):
            card = tk.Frame(
                slots, bg=colors["card_strip"],
                highlightbackground=border_col, highlightthickness=1,
                padx=14, pady=12,
            )
            card.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else 8, 0))
            top = tk.Frame(card, bg=colors["card_strip"])
            top.pack(fill="x")
            tk.Label(top, text=title, font=self.fonts["subtitle"], fg=colors["text"], bg=colors["card_strip"]).pack(side="left")
            tk.Label(top, textvariable=self.fx_labels[bus_id], font=self.fonts["status_value"], fg=border_col, bg=colors["card_strip"]).pack(side="right")
            tk.Label(card, text=desc, font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["card_strip"]).pack(anchor="w", pady=(2, 8))
            UnipolarSlider(
                card, variable=self.fx_vars[bus_id],
                command=lambda val, b=bus_id: self._on_fx_drag(b, val),
                default=0, accent=border_col,
            ).pack(fill="x")
            tk.Label(
                card,
                text="DECAY / MIX / PREDELAY / TIME / FEEDBACK: UNSUPPORTED (Fixed by FLOW 8 firmware slot)",
                font=self.fonts["caption"], fg=colors["text_muted"], bg=colors["card_strip"],
            ).pack(anchor="w", pady=(8, 0))

        # Reference FX Presets Catalog (Read-only)
        cat = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=14, pady=10,
        )
        cat.pack(fill="both", expand=True, padx=pad, pady=(0, pad))
        tk.Label(
            cat, text="REFERENCE FX STARTING POINTS (READ-ONLY — PROGRAM CHANGE NOT IN ALLOWLIST)",
            font=self.fonts["eyebrow"], fg=colors["text"], bg=colors["surface"],
        ).pack(anchor="w", pady=(0, 6))

        for fx in list_fx_presets():
            row = tk.Frame(cat, bg=colors["background_alt"], highlightbackground=colors["border"], highlightthickness=1, padx=10, pady=6)
            row.pack(fill="x", pady=3)
            tk.Label(
                row, text=f"{fx.name} ({fx.group})", font=self.fonts["body"],
                fg=colors["purple_soft"], bg=colors["background_alt"],
            ).pack(side="left")
            tk.Label(
                row, text=fx.summary, font=self.fonts["caption"],
                fg=colors["text_secondary"], bg=colors["background_alt"],
            ).pack(side="right")

    def refresh(self) -> None:
        if self.service is None:
            return
        self._updating = True
        try:
            for bid in ("fx1", "fx2"):
                st = self.service.state_store.get_parameter(f"{bid}.fader")
                raw = st.commanded_raw_midi if st and st.commanded_raw_midi is not None else 0
                self.fx_vars[bid].set(int(raw))
                self.fx_labels[bid].set("-inf dB (0)" if raw == 0 else f"{fader_midi_to_db(int(raw)):+.1f} dB ({raw})")
        finally:
            self._updating = False

    def _on_fx_drag(self, bus_id: str, val_str: str) -> None:
        if self._updating or self.service is None:
            return
        raw = max(0, min(127, int(val_str)))
        self.fx_labels[bus_id].set("-inf dB (0)" if raw == 0 else f"{fader_midi_to_db(raw):+.1f} dB ({raw})")
        self.service.set_bus_fader(bus_id, raw)
        if self.on_feedback:
            self.on_feedback(f"{bus_id.upper()} RETURN LEVEL COMMANDED")
