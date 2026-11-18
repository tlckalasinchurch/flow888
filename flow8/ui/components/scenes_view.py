"""CueAir Gen Z/Alpha Scene Manager View (Figma node 5:372).

Provides 8-slot snapshot capture/recall, JSON library import/export,
and explicit SCENE RECALL PROTECTION (never touches +48V or preamp gain).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
from typing import Any, Callable, Optional

from flow8.library_io import export_library_json, import_library_json
from flow8.ui import theme
from flow8.ui.components.scene_bar import SLOT_COUNT, slot_name


class ScenesView(tk.Frame):
    """Full-page Scene Manager aligned with Figma CueAir Scene Manager (5:372)."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_feedback: Optional[Callable[[str], None]] = None,
        on_recalled: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self.on_recalled = on_recalled
        self.current_scene_var = tk.StringVar(value="NONE LOADED")
        self.current_meta_var = tk.StringVar(value="Capture or recall a scene slot below")
        self._slot_rows: dict[int, tuple[tk.Label, tk.Button]] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_large"]

        # Header
        hdr = tk.Frame(self, bg=colors["background"])
        hdr.pack(fill="x", padx=pad, pady=(pad, 10))
        tk.Label(
            hdr, text="Scenes", font=self.fonts["title"],
            fg=colors["text"], bg=colors["background"],
        ).pack(side="left")
        tk.Label(
            hdr, text="SNAPSHOTS  ·  SHOW PRESETS", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(12, 0), pady=(6, 0))

        # Hero Current Scene Card (#14243A)
        hero = tk.Frame(
            self, bg=colors["card_hero"],
            highlightbackground=colors["halo"], highlightthickness=1,
            padx=16, pady=12,
        )
        hero.pack(fill="x", padx=pad, pady=(0, 10))

        pill = tk.Label(
            hero, text="● CURRENT SCENE", font=self.fonts["caption"],
            fg=colors["success"], bg=colors["pill_bg"],
            highlightbackground=colors["success"], highlightthickness=1,
            padx=8, pady=2,
        )
        pill.pack(anchor="w")
        tk.Label(
            hero, textvariable=self.current_scene_var, font=self.fonts["subtitle"],
            fg=colors["text"], bg=colors["card_hero"],
        ).pack(anchor="w", pady=(6, 2))
        tk.Label(
            hero, textvariable=self.current_meta_var, font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["card_hero"],
        ).pack(anchor="w")

        # Quick Actions Row
        actions = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=10, pady=8,
        )
        actions.pack(fill="x", padx=pad, pady=(0, 10))

        self.save_next_btn = self._pill_btn(
            actions, "+ SAVE NEXT EMPTY", colors["lime"], self._save_next_empty
        )
        self.save_next_btn.pack(side="left", padx=(0, 8))
        self.import_btn = self._pill_btn(
            actions, "IMPORT LIBRARY (JSON)", colors["purple"], self._import_json
        )
        self.import_btn.pack(side="left", padx=(0, 8))
        self.export_btn = self._pill_btn(
            actions, "EXPORT LIBRARY (JSON)", colors["cyan"], self._export_json
        )
        self.export_btn.pack(side="left")

        # Scene Library (8 Slots)
        lib = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=14, pady=12,
        )
        lib.pack(fill="both", expand=True, padx=pad, pady=(0, 10))

        tk.Label(
            lib, text="YOUR SCENES (SLOTS 01–08)", font=self.fonts["eyebrow"],
            fg=colors["text"], bg=colors["surface"],
        ).pack(anchor="w", pady=(0, 8))

        accents = (colors["cyan"], colors["purple"], colors["warning"], colors["danger"])
        for slot in range(1, SLOT_COUNT + 1):
            accent = accents[(slot - 1) % len(accents)]
            row = tk.Frame(
                lib, bg=colors["background_alt"],
                highlightbackground=colors["border"], highlightthickness=1,
                padx=10, pady=6,
            )
            row.pack(fill="x", pady=3)

            badge = tk.Label(
                row, text=f"{slot:02d}", font=self.fonts["eyebrow"],
                fg=accent, bg=colors["surface_hover"],
                highlightbackground=accent, highlightthickness=1,
                width=4, pady=4,
            )
            badge.pack(side="left", padx=(0, 10))

            info = tk.Frame(row, bg=colors["background_alt"])
            info.pack(side="left", fill="x", expand=True)
            tk.Label(
                info, text=slot_name(slot), font=self.fonts["body"],
                fg=colors["text"], bg=colors["background_alt"], anchor="w",
            ).pack(fill="x")
            meta_lbl = tk.Label(
                info, text="Empty slot", font=self.fonts["caption"],
                fg=colors["text_secondary"], bg=colors["background_alt"], anchor="w",
            )
            meta_lbl.pack(fill="x")

            cap_btn = self._pill_btn(
                row, "SAVE", colors["lime"], lambda s=slot: self._capture_slot(s)
            )
            cap_btn.pack(side="right", padx=(6, 0))
            load_btn = self._pill_btn(
                row, "LOAD", colors["cyan"], lambda s=slot: self._recall_slot(s)
            )
            load_btn.pack(side="right")
            self._slot_rows[slot] = (meta_lbl, load_btn)

        # Scene Recall Protection Card
        safety = tk.Frame(
            self, bg=colors["safety_bg"],
            highlightbackground=colors["safety_border"], highlightthickness=1,
            padx=12, pady=8,
        )
        safety.pack(fill="x", padx=pad, pady=(0, pad))
        tk.Label(
            safety, text="SCENE RECALL PROTECTION", font=self.fonts["eyebrow"],
            fg=colors["danger"], bg=colors["safety_bg"], anchor="w",
        ).pack(fill="x")
        tk.Label(
            safety,
            text="Recalls fader, pan, mute, EQ, HPF, comp, and sends as 1 atomic undo step. +48V and Preamp Gain are never altered.",
            font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["safety_bg"], anchor="w",
        ).pack(fill="x")

    def _pill_btn(self, parent: tk.Misc, text: str, accent: str, command: Callable[[], None]) -> tk.Button:
        colors = theme.COLORS
        return tk.Button(
            parent, text=text, font=self.fonts["caption"],
            bg=colors["pill_bg"], fg=accent,
            activebackground=colors["surface_hover"], activeforeground=accent,
            disabledforeground=colors["text_muted"],
            highlightbackground=accent, highlightthickness=1,
            bd=0, relief="flat", cursor="hand2", padx=10, pady=4,
            command=command,
        )

    def _report(self, msg: str) -> None:
        if self.on_feedback:
            self.on_feedback(msg)

    def refresh(self) -> None:
        names = set(self.service.scenes.names()) if self.service is not None else set()
        for slot, (meta_lbl, load_btn) in self._slot_rows.items():
            sname = slot_name(slot)
            if sname in names:
                snap = self.service.scenes.get(sname)
                count = sum(len(v) for v in snap.parameters.values())
                meta_lbl.configure(text=f"{len(snap.parameters)} channels · {count} parameters")
                load_btn.configure(state="normal")
            else:
                meta_lbl.configure(text="Empty slot")
                load_btn.configure(state="disabled")

    def _capture_slot(self, slot: int) -> None:
        if self.service is None:
            return
        sname = slot_name(slot)
        try:
            snap = self.service.capture_scene(sname)
            self.current_scene_var.set(sname)
            count = sum(len(v) for v in snap.parameters.values())
            self.current_meta_var.set(f"Saved {len(snap.parameters)} channels · {count} values")
            self._report(f"SCENE CAPTURED — {sname} · {count} VALUES")
        except Exception as exc:
            self._report(f"SCENE CAPTURE REJECTED — {exc}")
        self.refresh()

    def _recall_slot(self, slot: int) -> None:
        if self.service is None:
            return
        sname = slot_name(slot)
        try:
            res = self.service.recall_scene(sname)
            self.current_scene_var.set(sname)
            self.current_meta_var.set(f"Recalled · {res.applied} applied, {len(res.failed)} failed")
            self._report(f"SCENE RECALLED — {sname}")
            if self.on_recalled:
                self.on_recalled()
        except Exception as exc:
            self._report(f"SCENE RECALL FAILED — {exc}")
        self.refresh()

    def _save_next_empty(self) -> None:
        if self.service is None:
            return
        names = set(self.service.scenes.names())
        for slot in range(1, SLOT_COUNT + 1):
            if slot_name(slot) not in names:
                self._capture_slot(slot)
                return
        self._capture_slot(1)

    def _import_json(self) -> None:
        if self.service is None:
            return
        path = filedialog.askopenfilename(
            title="Import FLOW 8 Library JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            res = import_library_json(self.service, path)
            self._report(f"LIBRARY IMPORTED — {res['applied']} PARAMETERS APPLIED")
            if self.on_recalled:
                self.on_recalled()
        except Exception as exc:
            self._report(f"LIBRARY IMPORT FAILED — {exc}")

    def _export_json(self) -> None:
        if self.service is None:
            return
        path = filedialog.asksaveasfilename(
            title="Export FLOW 8 Library JSON",
            defaultextension=".json",
            initialfile="New_8.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            export_library_json(self.service, path)
            self._report(f"LIBRARY EXPORTED — {path}")
        except Exception as exc:
            self._report(f"LIBRARY EXPORT FAILED — {exc}")
