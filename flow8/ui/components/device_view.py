"""CueAir Gen Z/Alpha Device Connection View (Figma node 5:444).

Surfaces USB MIDI port status, connect/disconnect controls, Wi-Fi/LAN remote
hub toggle, and an honest pre-flight checklist (Bluetooth BLE marked UNSUPPORTED).
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional

from flow8.ui import theme


class DeviceView(tk.Frame):
    """Device Connection & Setup screen aligned with Figma (5:444)."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_connect: Optional[Callable[[], Any]] = None,
        on_disconnect: Optional[Callable[[], Any]] = None,
        on_toggle_lan: Optional[Callable[[], Any]] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_toggle_lan = on_toggle_lan
        self.port_status_var = tk.StringVar(value="MIDI PORTS CLOSED")
        self.port_detail_var = tk.StringVar(value="OUT closed · IN closed · not hardware-confirmed")
        self._build()
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_large"]

        hdr = tk.Frame(self, bg=colors["background"])
        hdr.pack(fill="x", padx=pad, pady=(pad, 10))
        tk.Label(
            hdr, text="Connect Device", font=self.fonts["title"],
            fg=colors["text"], bg=colors["background"],
        ).pack(side="left")
        tk.Label(
            hdr, text="SETUP  ·  FIND YOUR MIXER", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(12, 0), pady=(6, 0))

        # Hero Card
        hero = tk.Frame(
            self, bg=colors["card_hero"],
            highlightbackground=colors["halo"], highlightthickness=1,
            padx=16, pady=14,
        )
        hero.pack(fill="x", padx=pad, pady=(0, 10))
        tk.Label(
            hero, text="DEVICE SETUP", font=self.fonts["caption"],
            fg=colors["cyan"], bg=colors["pill_bg"],
            highlightbackground=colors["cyan"], highlightthickness=1,
            padx=8, pady=2,
        ).pack(anchor="w")
        tk.Label(
            hero, text="Behringer FLOW 8 — USB MIDI", font=self.fonts["subtitle"],
            fg=colors["text"], bg=colors["card_hero"],
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(
            hero, textvariable=self.port_status_var, font=self.fonts["body"],
            fg=colors["success"], bg=colors["card_hero"],
        ).pack(anchor="w")
        tk.Label(
            hero, textvariable=self.port_detail_var, font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["card_hero"],
        ).pack(anchor="w")

        # Connection Methods
        methods = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=14, pady=12,
        )
        methods.pack(fill="x", padx=pad, pady=(0, 10))
        tk.Label(
            methods, text="CONNECTION METHODS", font=self.fonts["eyebrow"],
            fg=colors["text"], bg=colors["surface"],
        ).pack(anchor="w", pady=(0, 6))

        usb_row = tk.Frame(methods, bg=colors["background_alt"], highlightbackground=colors["border"], highlightthickness=1, padx=10, pady=8)
        usb_row.pack(fill="x", pady=3)
        tk.Label(usb_row, text="USB MIDI (WinMM) — Recommended · Stable control", font=self.fonts["body"], fg=colors["text"], bg=colors["background_alt"]).pack(side="left")
        tk.Label(usb_row, text="SELECTED", font=self.fonts["caption"], fg=colors["success"], bg=colors["pill_bg"], padx=8, pady=2).pack(side="right")

        lan_row = tk.Frame(methods, bg=colors["background_alt"], highlightbackground=colors["border"], highlightthickness=1, padx=10, pady=8)
        lan_row.pack(fill="x", pady=3)
        tk.Label(lan_row, text="Wi-Fi / LAN Remote Hub (HTTP + SSE)", font=self.fonts["body"], fg=colors["text"], bg=colors["background_alt"]).pack(side="left")
        if self._on_toggle_lan is not None:
            tk.Button(
                lan_row, text="TOGGLE LAN HUB", font=self.fonts["caption"],
                bg=colors["pill_bg"], fg=colors["cyan"], bd=0, relief="flat", cursor="hand2", padx=8, pady=2,
                command=self._on_toggle_lan,
            ).pack(side="right")

        bt_row = tk.Frame(methods, bg=colors["background_alt"], highlightbackground=colors["border"], highlightthickness=1, padx=10, pady=8)
        bt_row.pack(fill="x", pady=3)
        tk.Label(bt_row, text="Bluetooth BLE Control", font=self.fonts["body"], fg=colors["text_muted"], bg=colors["background_alt"]).pack(side="left")
        tk.Label(bt_row, text="UNSUPPORTED", font=self.fonts["caption"], fg=colors["text_muted"], bg=colors["surface"], padx=8, pady=2).pack(side="right")

        # Checklist + Actions
        checks = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=14, pady=12,
        )
        checks.pack(fill="x", padx=pad, pady=(0, 12))
        tk.Label(checks, text="BEFORE YOU START", font=self.fonts["eyebrow"], fg=colors["text"], bg=colors["surface"]).pack(anchor="w", pady=(0, 6))
        for item in ("Mixer powered on", "USB cable connected to host", "WinMM FLOW 8 MIDI IN / OUT enumerated"):
            tk.Label(checks, text=f"✓  {item}", font=self.fonts["body"], fg=colors["text_secondary"], bg=colors["surface"]).pack(anchor="w", pady=1)

        cta_row = tk.Frame(self, bg=colors["background"])
        cta_row.pack(fill="x", padx=pad)
        if self._on_connect is not None:
            tk.Button(
                cta_row, text="CONNECT TO FLOW 8  →", font=self.fonts["eyebrow"],
                bg=colors["surface_hover"], fg=colors["cyan"],
                highlightbackground=colors["cyan"], highlightthickness=1,
                bd=0, relief="flat", cursor="hand2", padx=16, pady=10,
                command=self._on_connect,
            ).pack(side="left", padx=(0, 10))
        if self._on_disconnect is not None:
            tk.Button(
                cta_row, text="DISCONNECT", font=self.fonts["eyebrow"],
                bg=colors["surface"], fg=colors["danger"],
                highlightbackground=colors["danger"], highlightthickness=1,
                bd=0, relief="flat", cursor="hand2", padx=16, pady=10,
                command=self._on_disconnect,
            ).pack(side="left")

    def refresh(self) -> None:
        if self.service is None:
            self.port_status_var.set("NO COMMAND SERVICE (OFFLINE)")
            self.port_detail_var.set("OUT closed · IN closed · not hardware-confirmed")
            return
        out_open = self.service.midi_out_open
        in_open = self.service.midi_in_open
        listening = self.service.midi_in_listening
        if out_open and in_open and listening:
            self.port_status_var.set("MIDI PORTS OPEN")
        elif out_open or in_open:
            self.port_status_var.set("MIDI PORTS PARTIAL")
        else:
            self.port_status_var.set("MIDI PORTS CLOSED")
        self.port_detail_var.set(
            f"OUT {'open' if out_open else 'closed'} · IN {'open' if in_open else 'closed'} · not hardware-confirmed"
        )
