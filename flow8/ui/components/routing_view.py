"""FLOW 8 Visual Configure Inputs & Monitor Routing View (Phase 2.4).

Combines:
* Visual CONFIGURE INPUTS panel: 8 physical input jacks (MIC 1–2 XLR with +48V
  Hold-to-Toggle / Safety Gate, COMBO 3–4 with Hi-Z badges, LINE 5/6 & 7/8 with
  per-jack meters in5..in8, Hi-Z badges, and STEREO/MONO link indicators);
* Monitor 1 & Monitor 2 channel send levels (CC 14/15) and bus master faders;
* Output Pads (-10 dBV MAIN L/R & MON 1/2 status) & PHONES OUTPUT · HARDWARE ONLY.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Mapping, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.parameter_mapping import fader_midi_to_db
from flow8.ui import theme
from flow8.ui.components.controls import UnipolarSlider


PHYSICAL_JACK_SPECS = (
    {"num": 1, "label": "MIC 1", "jack": "XLR", "meter": "ch1", "ch": 1, "phantom": True, "hiz": False},
    {"num": 2, "label": "MIC 2", "jack": "XLR", "meter": "ch2", "ch": 2, "phantom": True, "hiz": False},
    {"num": 3, "label": "COMBO 3", "jack": "XLR/TRS", "meter": "ch3", "ch": 3, "phantom": False, "hiz": True},
    {"num": 4, "label": "COMBO 4", "jack": "XLR/TRS", "meter": "ch4", "ch": 4, "phantom": False, "hiz": True},
    {"num": 5, "label": "LINE 5 (L)", "jack": "TRS", "meter": "in5", "ch": 5, "phantom": False, "hiz": False},
    {"num": 6, "label": "LINE 6 (R)", "jack": "TRS", "meter": "in6", "ch": 5, "phantom": False, "hiz": True},
    {"num": 7, "label": "LINE 7 (L)", "jack": "TRS", "meter": "in7", "ch": 6, "phantom": False, "hiz": False},
    {"num": 8, "label": "LINE 8 (R)", "jack": "TRS", "meter": "in8", "ch": 6, "phantom": False, "hiz": True},
)


class RoutingView(tk.Frame):
    """Visual Configure Inputs & Monitor Routing Workstation View."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_feedback: Optional[Callable[[str], None]] = None,
        on_phantom_request: Optional[Callable[[int, bool], None]] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self._on_phantom_request = on_phantom_request
        self.active_bus = "mon1"
        self._updating = False
        self.bus_buttons: dict[str, tk.Button] = {}
        self.send_vars: dict[int, tk.IntVar] = {ch: tk.IntVar(value=0) for ch in range(1, 8)}
        self.send_labels: dict[int, tk.StringVar] = {ch: tk.StringVar(value="-inf dB") for ch in range(1, 8)}
        self.master_var = tk.IntVar(value=0)
        self.master_label = tk.StringVar(value="-inf dB")

        self.jack_meters: dict[int, tk.Canvas] = {}
        self.jack_phantom_buttons: dict[int, tk.Button] = {}
        self.stereo_link_labels: dict[str, tk.Label] = {}
        self.output_pad_labels: dict[str, tk.Label] = {}
        self._phantom_hold_ids: dict[int, Optional[str]] = {1: None, 2: None}

        self._build()
        if self.service is not None:
            add_meter = getattr(self.service, "add_meter_listener", None)
            if callable(add_meter):
                add_meter(self._on_meter_event)
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_medium"]

        hdr = tk.Frame(self, bg=colors["background"])
        hdr.pack(fill="x", padx=pad, pady=(8, 4))
        tk.Label(
            hdr, text="Configure Inputs & Monitor Routing", font=self.fonts["subtitle"],
            fg=colors["text"], bg=colors["background"],
        ).pack(side="left")
        tk.Label(
            hdr, text="PHYSICAL I/O JACKS (IN 1–8)  ·  +48V  ·  HI-Z  ·  STAGE MONITOR MIX",
            font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(12, 0), pady=(2, 0))

        # 1. Visual CONFIGURE INPUTS Panel (8 Physical Jacks + Stereo/Mono Link 5/6 & 7/8)
        io_card = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=10, pady=6,
        )
        io_card.pack(fill="x", padx=pad, pady=(0, 6))

        io_top = tk.Frame(io_card, bg=colors["surface"])
        io_top.pack(fill="x", pady=(0, 4))
        tk.Label(
            io_top, text="CONFIGURE INPUTS (PHYSICAL JACKS 1–8 · PRE-FADER USB METERS)",
            font=self.fonts["eyebrow"], fg=colors["cyan"], bg=colors["surface"],
        ).pack(side="left")
        tk.Label(
            io_top, text="HOLD +48V TO TOGGLE ON MIC 1–2",
            font=self.fonts["status_key"], fg=colors["warning"], bg=colors["surface"],
        ).pack(side="right")

        jacks_grid = tk.Frame(io_card, bg=colors["surface"])
        jacks_grid.pack(fill="x")
        for col in range(8):
            jacks_grid.grid_columnconfigure(col, weight=1, uniform="jack_col")

        for col, spec in enumerate(PHYSICAL_JACK_SPECS):
            jnum = spec["num"]
            jcard = tk.Frame(
                jacks_grid, bg=colors["background_alt"],
                highlightbackground=colors["border"], highlightthickness=1,
                padx=5, pady=4,
            )
            jcard.grid(row=0, column=col, sticky="nsew", padx=2, pady=1)

            j_hdr = tk.Frame(jcard, bg=colors["background_alt"])
            j_hdr.pack(fill="x")
            tk.Label(
                j_hdr, text=spec["label"], font=self.fonts["eyebrow"],
                fg=colors["text"], bg=colors["background_alt"],
            ).pack(side="left")
            tk.Label(
                j_hdr, text=spec["jack"], font=self.fonts["status_key"],
                fg=colors["cyan_soft"], bg=colors["surface_alt"], padx=3,
            ).pack(side="right")

            # Live Per-Jack USB Meter Bar (gated: only draws meter-bar when live feed is active)
            m_canvas = tk.Canvas(
                jcard, height=8, bg=colors["surface"],
                highlightthickness=1, highlightbackground=colors["border"], bd=0,
            )
            m_canvas.pack(fill="x", pady=(4, 4))
            self.jack_meters[jnum] = m_canvas

            # Bottom row: +48V Hold-to-Toggle (MIC 1–2) or Hi-Z Badge (COMBO 3–4, LINE 6/8) or Line label
            if spec["phantom"]:
                pbtn = tk.Button(
                    jcard,
                    text="+48V OFF (HOLD)",
                    font=self.fonts["status_key"],
                    bg=colors["surface_alt"],
                    fg=colors["text_secondary"],
                    activebackground=colors["warning"],
                    activeforeground=colors["background"],
                    bd=0,
                    relief="flat",
                    cursor="hand2",
                    pady=2,
                    command=lambda ch=spec["ch"]: self.request_jack_phantom(ch),
                )
                pbtn.pack(fill="x")
                pbtn.bind("<ButtonPress-1>", lambda _e, ch=spec["ch"]: self._on_phantom_hold_start(ch), add="+")
                pbtn.bind("<ButtonRelease-1>", lambda _e, ch=spec["ch"]: self._on_phantom_hold_end(ch), add="+")
                self.jack_phantom_buttons[spec["ch"]] = pbtn
            elif spec["hiz"]:
                tk.Label(
                    jcard, text="HI-Z INST READY", font=self.fonts["status_key"],
                    fg=colors["lime"], bg=colors["pill_bg"], pady=2,
                ).pack(fill="x")
            else:
                tk.Label(
                    jcard, text=f"→ CH {spec['ch']} PAIR", font=self.fonts["status_key"],
                    fg=colors["text_muted"], bg=colors["background_alt"], pady=2,
                ).pack(fill="x")

        # Stereo / Mono Link Row for 5/6 & 7/8 + -10 dBV Output Pads
        links_row = tk.Frame(io_card, bg=colors["surface"])
        links_row.pack(fill="x", pady=(4, 0))
        for pair_key, pair_label in (("5/6", "LINE 5/6 LINK: STEREO / MONO (LOCKED)"), ("7/8", "LINE 7/8 LINK: STEREO / MONO (LOCKED)")):
            lbl = tk.Label(
                links_row, text=pair_label, font=self.fonts["status_key"],
                fg=colors["purple_soft"], bg=colors["background_alt"], padx=8, pady=2,
            )
            lbl.pack(side="left", padx=(0, 6))
            self.stereo_link_labels[pair_key] = lbl

        for pad_key, pad_label in (("main", "MAIN OUT: -10 dBV PAD (LOCKED)"), ("mon", "MON 1/2 OUT: -10 dBV PAD (LOCKED)")):
            plbl = tk.Label(
                links_row, text=pad_label, font=self.fonts["status_key"],
                fg=colors["warning"], bg=colors["background_alt"], padx=8, pady=2,
            )
            plbl.pack(side="right", padx=(6, 0))
            self.output_pad_labels[pad_key] = plbl

        # 2. Monitor Bus Selector + Channel Send Levels Card
        sends_card = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=12, pady=8,
        )
        sends_card.pack(fill="both", expand=True, padx=pad, pady=(0, 6))

        sel_hdr = tk.Frame(sends_card, bg=colors["surface"])
        sel_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(
            sel_hdr, text="MONITOR BUS DESTINATION & CHANNEL SENDS", font=self.fonts["eyebrow"],
            fg=colors["text"], bg=colors["surface"],
        ).pack(side="left")

        for bus_id, label in (("mon1", "MONITOR 1 (CC 14)"), ("mon2", "MONITOR 2 (CC 15)")):
            btn = tk.Button(
                sel_hdr, text=label, font=self.fonts["eyebrow"],
                bg=colors["pill_bg"], fg=colors["cyan"],
                bd=0, relief="flat", cursor="hand2", padx=10, pady=2,
                highlightthickness=1,
                command=lambda b=bus_id: self.select_bus(b),
            )
            btn.pack(side="right", padx=(6, 0))
            self.bus_buttons[bus_id] = btn

        accents = (
            colors["cyan"], colors["purple"], colors["lime"],
            colors["warning"], colors["danger"], colors["cyan_soft"], colors["purple_soft"],
        )
        for ch in range(1, 8):
            spec = LOGICAL_CHANNELS[ch]
            row = tk.Frame(sends_card, bg=colors["surface"])
            row.pack(fill="x", pady=2)
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

        # 3. Bus Master + Analog Phones Honesty Row
        bottom = tk.Frame(self, bg=colors["background"])
        bottom.pack(fill="x", padx=pad, pady=(0, 8))

        master_card = tk.Frame(
            bottom, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=12, pady=6,
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
        ).pack(fill="x", pady=(4, 0))

        phones_card = tk.Frame(
            bottom, bg=colors["safety_bg"],
            highlightbackground=colors["safety_border"], highlightthickness=1,
            padx=12, pady=6,
        )
        phones_card.pack(side="right", fill="y")
        tk.Label(
            phones_card, text="PHONES OUTPUT · HARDWARE ONLY", font=self.fonts["eyebrow"],
            fg=colors["danger"], bg=colors["safety_bg"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            phones_card,
            text="FLOW 8 Phones knob is an analog pot (no MIDI control). Start low before raising monitor bus levels.",
            font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["safety_bg"], justify="left",
        ).pack(anchor="w", pady=(2, 0))

        self._paint_bus_buttons()

    # -- +48V Hold-to-Toggle & Safety Gate on MIC 1–2 -----------------------

    def _on_phantom_hold_start(self, ch: int) -> None:
        aid = self._phantom_hold_ids.get(ch)
        if aid is not None:
            try:
                self.after_cancel(aid)
            except tk.TclError:
                pass
        self._phantom_hold_ids[ch] = self.after(550, lambda c=ch: self.request_jack_phantom(c))

    def _on_phantom_hold_end(self, ch: int) -> None:
        aid = self._phantom_hold_ids.get(ch)
        if aid is not None:
            try:
                self.after_cancel(aid)
            except tk.TclError:
                pass
            self._phantom_hold_ids[ch] = None

    def request_jack_phantom(self, ch: int) -> bool:
        """Ask the Inspector to toggle +48V on MIC 1 or MIC 2.

        This view never touches the phantom safety gate itself: the request is
        delegated to the Inspector's confirmation flow (the only +48V route).
        """
        if ch not in (1, 2) or self.service is None or self._on_phantom_request is None:
            return False
        st = self.service.state_store.get_parameter(f"ch{ch}.phantom")
        currently_on = bool(st.commanded_value) if st is not None else False
        self._on_phantom_request(ch, not currently_on)
        self.refresh()
        return True

    # -- Per-Jack Live USB Meters (in1..in8) --------------------------------

    def _on_meter_event(self, levels: dict[str, dict[str, float]]) -> None:
        try:
            self.after_idle(lambda lv=dict(levels): self.ingest_meter_levels(lv, live=True))
        except (tk.TclError, RuntimeError):
            pass

    def ingest_meter_levels(self, levels: Mapping[str, Mapping[str, float]], live: bool = True) -> None:
        """Render per-jack pre-fader USB signal meters (ch1..ch4, in5..in8) only when live=True."""
        colors = theme.COLORS
        for spec in PHYSICAL_JACK_SPECS:
            canvas = self.jack_meters.get(spec["num"])
            if canvas is None:
                continue
            canvas.delete("all")
            if not live or not levels:
                continue
            entry = levels.get(spec["meter"]) or levels.get(f"ch{spec['ch']}")
            if not entry:
                continue
            rms_db = float(entry.get("rms", -120.0))
            peak_db = float(entry.get("peak", -120.0))
            frac = max(0.0, min(1.0, (rms_db + 60.0) / 60.0))
            if frac <= 0.0:
                continue
            w = max(canvas.winfo_width(), 48)
            h = max(canvas.winfo_height(), 8)
            bar_color = (
                colors["danger"] if peak_db >= -0.5
                else (colors["warning"] if peak_db > -6.0 else colors["success"])
            )
            canvas.create_rectangle(
                0, 0, round(w * frac), h,
                fill=bar_color, outline="", tags=("meter-bar",),
            )

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
        colors = theme.COLORS
        self._updating = True
        try:
            for ch in (1, 2):
                pbtn = self.jack_phantom_buttons.get(ch)
                if pbtn is not None:
                    pst = self.service.state_store.get_parameter(f"ch{ch}.phantom")
                    on = bool(pst.commanded_value if (pst and pst.commanded_raw_midi is not None) else (pst.observed_value if pst else False))
                    pbtn.configure(
                        text="+48V ON (HOLD)" if on else "+48V OFF (HOLD)",
                        bg=colors["warning"] if on else colors["surface_alt"],
                        fg=colors["background"] if on else colors["text_secondary"],
                    )
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

    def destroy(self) -> None:
        for aid in self._phantom_hold_ids.values():
            if aid is not None:
                try:
                    self.after_cancel(aid)
                except tk.TclError:
                    pass
        if self.service is not None:
            rem = getattr(self.service, "remove_meter_listener", None)
            if callable(rem):
                rem(self._on_meter_event)
        super().destroy()
