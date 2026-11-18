"""CueAir Gen Z/Alpha Monitor Routing View (Figma node 5:496).

Controls Monitor 1 & Monitor 2 channel send levels (CC 14/15) and bus master
faders (Ch 9-10, CC 7). PHONES LEVEL is honestly marked ANALOG / HARDWARE ONLY.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.parameter_mapping import fader_midi_to_db
from flow8.ui import theme
from flow8.ui.components.controls import UnipolarSlider


class RoutingView(tk.Frame):
    """Full-page Monitor Routing screen aligned with Figma (5:496)."""

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
        self.active_bus = "mon1"
        self._updating = False
        self.bus_buttons: dict[str, tk.Button] = {}
        self.send_vars: dict[int, tk.IntVar] = {ch: tk.IntVar(value=0) for ch in range(1, 8)}
        self.send_labels: dict[int, tk.StringVar] = {ch: tk.StringVar(value="-inf dB") for ch in range(1, 8)}
        self.master_var = tk.IntVar(value=0)
        self.master_label = tk.StringVar(value="-inf dB")
        self._build()
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_large"]

        hdr = tk.Frame(self, bg=colors["background"])
        hdr.pack(fill="x", padx=pad, pady=(pad, 10))
        tk.Label(
            hdr, text="Monitor Routing", font=self.fonts["title"],
            fg=colors["text"], bg=colors["background"],
        ).pack(side="left")
        tk.Label(
            hdr, text="OUTPUTS  ·  STAGE MONITOR MIX", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(12, 0), pady=(6, 0))

        # Bus Selector Card
        sel_card = tk.Frame(
            self, bg=colors["card_hero"],
            highlightbackground=colors["halo"], highlightthickness=1,
            padx=14, pady=10,
        )
        sel_card.pack(fill="x", padx=pad, pady=(0, 10))
        tk.Label(
            sel_card, text="MONITOR BUS DESTINATION", font=self.fonts["eyebrow"],
            fg=colors["text_secondary"], bg=colors["card_hero"],
        ).pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(sel_card, bg=colors["card_hero"])
        btn_row.pack(fill="x")
        for bus_id, label in (("mon1", "MONITOR 1 (CC 14)"), ("mon2", "MONITOR 2 (CC 15)")):
            btn = tk.Button(
                btn_row, text=label, font=self.fonts["eyebrow"],
                bg=colors["pill_bg"], fg=colors["cyan"],
                bd=0, relief="flat", cursor="hand2", padx=12, pady=5,
                highlightthickness=1,
                command=lambda b=bus_id: self.select_bus(b),
            )
            btn.pack(side="left", padx=(0, 8))
            self.bus_buttons[bus_id] = btn

        # Channel Send Levels Card
        sends_card = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=14, pady=10,
        )
        sends_card.pack(fill="both", expand=True, padx=pad, pady=(0, 10))
        tk.Label(
            sends_card, text="CHANNEL SEND LEVELS", font=self.fonts["eyebrow"],
            fg=colors["text"], bg=colors["surface"],
        ).pack(anchor="w", pady=(0, 8))

        accents = (
            colors["cyan"], colors["purple"], colors["lime"],
            colors["warning"], colors["danger"], colors["cyan_soft"], colors["purple_soft"],
        )
        for ch in range(1, 8):
            spec = LOGICAL_CHANNELS[ch]
            row = tk.Frame(sends_card, bg=colors["surface"])
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text=f"CH {ch:02d} · {spec.name}", font=self.fonts["body"],
                fg=colors["text"], bg=colors["surface"], width=22, anchor="w",
            ).pack(side="left")

            slider = UnipolarSlider(
                row,
                variable=self.send_vars[ch],
                command=lambda val, c=ch: self._on_send_drag(c, val),
                default=0,
                accent=accents[ch - 1],
            )
            slider.pack(side="left", fill="x", expand=True, padx=10)

            tk.Label(
                row, textvariable=self.send_labels[ch], font=self.fonts["status_key"],
                fg=colors["text_secondary"], bg=colors["surface"], width=16, anchor="e",
            ).pack(side="right")

        # Bus Master + Analog Phones Honesty Row
        bottom = tk.Frame(self, bg=colors["background"])
        bottom.pack(fill="x", padx=pad, pady=(0, pad))

        master_card = tk.Frame(
            bottom, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=14, pady=10,
        )
        master_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        m_hdr = tk.Frame(master_card, bg=colors["surface"])
        m_hdr.pack(fill="x")
        tk.Label(
            m_hdr, text="BUS MASTER LEVEL", font=self.fonts["eyebrow"],
            fg=colors["text"], bg=colors["surface"],
        ).pack(side="left")
        tk.Label(
            m_hdr, textvariable=self.master_label, font=self.fonts["status_value"],
            fg=colors["cyan"], bg=colors["surface"],
        ).pack(side="right")
        UnipolarSlider(
            master_card, variable=self.master_var,
            command=self._on_master_drag, default=0, accent=colors["cyan"],
        ).pack(fill="x", pady=(6, 0))

        phones_card = tk.Frame(
            bottom, bg=colors["safety_bg"],
            highlightbackground=colors["safety_border"], highlightthickness=1,
            padx=14, pady=10,
        )
        phones_card.pack(side="right", fill="y")
        tk.Label(
            phones_card, text="PHONES OUTPUT · HARDWARE ONLY", font=self.fonts["eyebrow"],
            fg=colors["danger"], bg=colors["safety_bg"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            phones_card,
            text="FLOW 8 Phones knob is an analog pot (no MIDI control).\nStart low before raising monitor bus levels.",
            font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["safety_bg"], justify="left",
        ).pack(anchor="w", pady=(2, 0))

        self._paint_bus_buttons()

    def _paint_bus_buttons(self) -> None:
        colors = theme.COLORS
        for bid, btn in self.bus_buttons.items():
            active = bid == self.active_bus
            btn.configure(
                fg=colors["success"] if active else colors["text_secondary"],
                highlightbackground=colors["success"] if active else colors["border"],
                bg=colors["pill_bg"] if active else colors["surface"],
            )

    def select_bus(self, bus_id: str) -> None:
        if bus_id in ("mon1", "mon2"):
            self.active_bus = bus_id
            self._paint_bus_buttons()
            self.refresh()

    def refresh(self) -> None:
        if self.service is None:
            return
        self._updating = True
        try:
            for ch in range(1, 8):
                st = self.service.state_store.get_parameter(f"ch{ch}.send_{self.active_bus}")
                raw = st.commanded_raw_midi if st and st.commanded_raw_midi is not None else 0
                self.send_vars[ch].set(int(raw))
                self.send_labels[ch].set(self._fmt(int(raw)))
            mst = self.service.state_store.get_parameter(f"{self.active_bus}.fader")
            mraw = mst.commanded_raw_midi if mst and mst.commanded_raw_midi is not None else 0
            self.master_var.set(int(mraw))
            self.master_label.set(self._fmt(int(mraw)))
        finally:
            self._updating = False

    @staticmethod
    def _fmt(raw: int) -> str:
        return "-inf dB (0)" if raw == 0 else f"{fader_midi_to_db(raw):+.1f} dB ({raw})"

    def _on_send_drag(self, ch: int, val_str: str) -> None:
        if self._updating or self.service is None:
            return
        raw = max(0, min(127, int(val_str)))
        self.send_labels[ch].set(self._fmt(raw))
        self.service.set_send(ch, self.active_bus, raw, unit="raw")
        if self.on_feedback:
            self.on_feedback(f"CH {ch} SEND {self.active_bus.upper()} COMMANDED")

    def _on_master_drag(self, val_str: str) -> None:
        if self._updating or self.service is None:
            return
        raw = max(0, min(127, int(val_str)))
        self.master_label.set(self._fmt(raw))
        self.service.set_bus_fader(self.active_bus, raw)
        if self.on_feedback:
            self.on_feedback(f"{self.active_bus.upper()} MASTER FADER COMMANDED")
