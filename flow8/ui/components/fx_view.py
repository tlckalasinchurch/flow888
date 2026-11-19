"""FLOW 8 Effects Rack View (Phase 2.4).

Displays FLOW 8 FX 1 & FX 2 return bus faders (Ch 11-12, CC 7), 4x4 v1.14 preset
tile grids (16 presets each for FX 1 Reverb and FX 2 Delay/Mod), Decay/Feedback
mode indicators, and curated FX starting points. Continuous FX DSP parameters
and Program Change slot switching are honestly marked READ-ONLY / UNSUPPORTED.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

from flow8.parameter_mapping import fader_midi_to_db
from flow8.presets import list_fx_presets
from flow8.ui import theme
from flow8.ui.components.channel_detail import ChannelDetailPanel
from flow8.ui.components.controls import UnipolarSlider


class FxView(tk.Frame):
    """FX Rack screen with 4x4 v1.14 preset grids and strict protocol honesty."""

    FX_PRESETS = ChannelDetailPanel.FX_PRESETS_V114

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
        self.fx_grids: dict[str, list[tk.Button]] = {"fx1": [], "fx2": []}
        self._build()
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_medium"]

        hdr = tk.Frame(self, bg=colors["background"])
        hdr.pack(fill="x", padx=pad, pady=(8, 4))
        tk.Label(
            hdr, text="Effects Rack", font=self.fonts["title"],
            fg=colors["text"], bg=colors["background"],
        ).pack(side="left")
        tk.Label(
            hdr, text="SEND / RETURN  ·  4x4 FX 1 & FX 2 ENGINES", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(12, 0), pady=(6, 0))

        # Status Bar
        info = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=10, pady=4,
        )
        info.pack(fill="x", padx=pad, pady=(0, 6))
        tk.Label(
            info, text="2 FX RETURN BUSES (MIDI CH 11–12)", font=self.fonts["caption"],
            fg=colors["success"], bg=colors["pill_bg"],
            highlightbackground=colors["success"], highlightthickness=1,
            padx=8, pady=1,
        ).pack(side="left")
        tk.Label(
            info,
            text="Slot Program Change & Decay/Predelay/Feedback knobs are UNSUPPORTED / READ-ONLY (Conflict C-09)",
            font=self.fonts["caption"], fg=colors["warning"], bg=colors["surface"],
        ).pack(side="right")

        # FX 1 & FX 2 Return Fader + 4x4 Preset Tile Grid Cards
        slots = tk.Frame(self, bg=colors["background"])
        slots.pack(fill="both", expand=True, padx=pad, pady=(0, 6))
        slots.grid_columnconfigure(0, weight=1, uniform="fx_col")
        slots.grid_columnconfigure(1, weight=1, uniform="fx_col")
        slots.grid_rowconfigure(0, weight=1)

        engine_specs = (
            ("fx1", "01  FX 1 RETURN (REVERB)", "Master FX 1 return · MIDI Ch 11 CC 7 · DECAY (INSTRUMENT / VOCAL)", colors["purple"]),
            ("fx2", "02  FX 2 RETURN (DELAY / MOD)", "Master FX 2 return · MIDI Ch 12 CC 7 · FEEDBACK (DULL / BRIGHT · TAP)", colors["cyan"]),
        )
        for idx, (bus_id, title, desc, border_col) in enumerate(engine_specs):
            card = tk.Frame(
                slots, bg=colors["card_strip"],
                highlightbackground=border_col, highlightthickness=1,
                padx=10, pady=8,
            )
            card.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 4, 4 if idx == 0 else 0))
            top = tk.Frame(card, bg=colors["card_strip"])
            top.pack(fill="x")
            tk.Label(top, text=title, font=self.fonts["subtitle"], fg=colors["text"], bg=colors["card_strip"]).pack(side="left")
            tk.Label(top, textvariable=self.fx_labels[bus_id], font=self.fonts["status_value"], fg=border_col, bg=colors["card_strip"]).pack(side="right")
            tk.Label(card, text=desc, font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["card_strip"]).pack(anchor="w", pady=(1, 4))
            UnipolarSlider(
                card, variable=self.fx_vars[bus_id],
                command=lambda val, b=bus_id: self._on_fx_drag(b, val),
                default=0, accent=border_col,
            ).pack(fill="x", pady=(0, 6))

            # 4x4 Official FLOW 8 v1.14 Preset Grid (16 tiles)
            grid_hdr = tk.Frame(card, bg=colors["card_strip"])
            grid_hdr.pack(fill="x", pady=(0, 2))
            tk.Label(
                grid_hdr,
                text=f"{bus_id.upper()} 16 PRESET 4x4 GRID (READ-ONLY · UNSUPPORTED OVER MIDI)",
                font=self.fonts["status_key"], fg=border_col, bg=colors["card_strip"],
            ).pack(side="left")

            grid = tk.Frame(card, bg=colors["background_alt"], padx=3, pady=3)
            grid.pack(fill="both", expand=True)
            for c in range(4):
                grid.grid_columnconfigure(c, weight=1, uniform=f"{bus_id}_c")
            for r in range(4):
                grid.grid_rowconfigure(r, weight=1, uniform=f"{bus_id}_r")

            for p_idx, p_name in enumerate(self.FX_PRESETS[bus_id]):
                r, c = divmod(p_idx, 4)
                tile = tk.Button(
                    grid,
                    text=f"{p_idx + 1:02d} {p_name}",
                    font=self.fonts["status_key"],
                    bg=colors["surface_alt"],
                    fg=colors["text_secondary"],
                    disabledforeground=colors["text_secondary"],
                    bd=0,
                    relief="flat",
                    state="disabled",
                    padx=2,
                    pady=2,
                )
                tile.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                self.fx_grids[bus_id].append(tile)

        # Reference FX Presets Catalog Footer (Read-only)
        cat = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=10, pady=6,
        )
        cat.pack(fill="x", padx=pad, pady=(0, 8))
        tk.Label(
            cat, text="REFERENCE FX STARTING POINTS (READ-ONLY — PROGRAM CHANGE NOT IN ALLOWLIST)",
            font=self.fonts["eyebrow"], fg=colors["text"], bg=colors["surface"],
        ).pack(anchor="w", pady=(0, 2))

        row = tk.Frame(cat, bg=colors["surface"])
        row.pack(fill="x")
        for fx in list_fx_presets():
            pill = tk.Label(
                row, text=f"{fx.name} ({fx.group})", font=self.fonts["caption"],
                fg=colors["purple_soft"], bg=colors["background_alt"], padx=6, pady=2,
            )
            pill.pack(side="left", padx=(0, 6))

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
