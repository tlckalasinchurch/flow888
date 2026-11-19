"""FLOW 8 Workstation Scene & Snapshot Library View (Phase 2.3).

Provides:
* 15-slot Mixer Snapshots (01–15) + safety-locked Slot 16 (MIXER RESET, PC 16 blocked);
* WHAT TO LOAD Recall Scope filters (CH, FX, MAIN, MON + safety-locked ROUT);
* Partial recall & post-recall mix edit tracking (marks current scene EDITED);
* Searchable, sortable Thai-ready Snapshot Library (save, load, rename, delete, JSON import/export);
* Strict SCENE RECALL PROTECTION (+48V phantom power and preamp gain are never captured or recalled).
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import font as tkfont
from typing import Any, Callable, Iterable, Optional

from flow8.library_io import export_library_json, import_library_json
from flow8.service import RECALL_SCOPES
from flow8.snapshot_library import SnapshotLibrary, scope_counts
from flow8.ui import theme
from flow8.ui.components.scene_bar import SLOT_COUNT, slot_name

THAI_FONT_PREFERENCES = ("Segoe UI", "Leelawadee UI", "Tahoma", "Inter", "Arial")


def _format_scopes(scopes: dict[str, int]) -> str:
    active = [k for k in ("CH", "FX", "MAIN", "MON") if scopes.get(k, 0) > 0]
    return "·".join(active) if active else "Empty"


class ScenesView(tk.Frame):
    """Full-page 15-Slot Mixer Snapshots + Recall Scope + Thai-Ready Snapshot Library."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_feedback: Optional[Callable[[str], None]] = None,
        on_recalled: Optional[Callable[[], None]] = None,
        library: Optional[SnapshotLibrary] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self.on_recalled = on_recalled
        self.library = library if library is not None else SnapshotLibrary()

        thai_family = theme.resolve_family(self, THAI_FONT_PREFERENCES)
        self.thai_font = tkfont.Font(root=self, family=thai_family, size=10, weight="normal")
        self.thai_bold = tkfont.Font(root=self, family=thai_family, size=10, weight="bold")

        self._loaded_scene_name: Optional[str] = None
        self.scene_edited: bool = False
        self.current_scene_var = tk.StringVar(value="NONE LOADED")
        self.current_meta_var = tk.StringVar(value="Capture or recall a snapshot slot (01–15) or library preset")

        self.scope_vars: dict[str, tk.BooleanVar] = {
            sc: tk.BooleanVar(value=True) for sc in RECALL_SCOPES
        }
        self.scope_checks: dict[str, tk.Checkbutton] = {}

        self.lib_name_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")
        self.sort_mode_var = tk.StringVar(value="date")
        self.library_count_var = tk.StringVar(value="0 presets")

        self._slot_rows: dict[int, tuple[tk.Label, tk.Button]] = {}
        self.library_row_widgets: dict[str, dict[str, tk.Widget]] = {}

        self._build()
        self.search_var.trace_add("write", lambda *_: self._rebuild_library_list())
        self.refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        pad = theme.TOKENS["spacing_medium"]

        # 1. Top Header + Hero Status Bar (Compact single band for 1280x720 / 1366x768)
        top_band = tk.Frame(self, bg=colors["background"])
        top_band.pack(fill="x", padx=pad, pady=(8, 6))

        title_col = tk.Frame(top_band, bg=colors["background"])
        title_col.pack(side="left")
        tk.Label(
            title_col, text="Scenes & Snapshot Library", font=self.fonts["subtitle"],
            fg=colors["text"], bg=colors["background"], anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_col, text="15 MIXER SLOTS (01–15) · WHAT TO LOAD SCOPE · NAMED PRESETS",
            font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["background"], anchor="w",
        ).pack(anchor="w")

        # Current Scene Hero Pill on the right of top_band
        hero = tk.Frame(
            top_band, bg=colors["card_hero"],
            highlightbackground=colors["halo"], highlightthickness=1,
            padx=10, pady=4,
        )
        hero.pack(side="right")
        self.hero_badge = tk.Label(
            hero, text="● CURRENT SCENE", font=self.fonts["status_key"],
            fg=colors["success"], bg=colors["pill_bg"], padx=6, pady=1,
        )
        self.hero_badge.pack(side="left", padx=(0, 8))
        tk.Label(
            hero, textvariable=self.current_scene_var, font=self.thai_bold,
            fg=colors["text"], bg=colors["card_hero"],
        ).pack(side="left", padx=(0, 8))
        tk.Label(
            hero, textvariable=self.current_meta_var, font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["card_hero"],
        ).pack(side="left")

        # 2. WHAT TO LOAD (Recall Scope Filter) + Quick Actions Row
        scope_bar = tk.Frame(
            self, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=10, pady=5,
        )
        scope_bar.pack(fill="x", padx=pad, pady=(0, 6))

        tk.Label(
            scope_bar, text="WHAT TO LOAD:", font=self.fonts["eyebrow"],
            fg=colors["cyan"], bg=colors["surface"],
        ).pack(side="left", padx=(0, 8))

        for sc in RECALL_SCOPES:
            chk = tk.Checkbutton(
                scope_bar,
                text=sc,
                variable=self.scope_vars[sc],
                font=self.fonts["eyebrow"],
                fg=colors["text"],
                bg=colors["surface"],
                selectcolor=colors["surface_alt"],
                activebackground=colors["surface"],
                activeforeground=colors["cyan"],
                cursor="hand2",
            )
            chk.pack(side="left", padx=3)
            self.scope_checks[sc] = chk

        # Safety-locked ROUT scope checkbox
        self.rout_scope_label = tk.Label(
            scope_bar,
            text="☐ ROUT (LOCKED)",
            font=self.fonts["caption"],
            fg=colors["warning"],
            bg=colors["surface_alt"],
            padx=6,
            pady=2,
        )
        self.rout_scope_label.pack(side="left", padx=(6, 0))

        # Quick Actions on right side of scope_bar
        self.export_btn = self._pill_btn(
            scope_bar, "EXPORT JSON", colors["cyan"], self._export_json
        )
        self.export_btn.pack(side="right", padx=(4, 0))
        self.import_btn = self._pill_btn(
            scope_bar, "IMPORT JSON", colors["purple"], self._import_json
        )
        self.import_btn.pack(side="right", padx=(4, 0))
        self.save_next_btn = self._pill_btn(
            scope_bar, "+ SAVE NEXT EMPTY", colors["lime"], self._save_next_empty
        )
        self.save_next_btn.pack(side="right", padx=(4, 0))

        # 3. Main 2-Column Body: Left = 15 Mixer Snapshots + Reset (4x4 Grid), Right = Snapshot Library
        body = tk.Frame(self, bg=colors["background"])
        body.pack(fill="both", expand=True, padx=pad, pady=(0, 6))
        body.grid_columnconfigure(0, weight=3, uniform="scenes_col")
        body.grid_columnconfigure(1, weight=2, uniform="scenes_col")
        body.grid_rowconfigure(0, weight=1)

        # Left Column: 15 Slots + Slot 16 Reset (4x4 Grid)
        slots_panel = tk.Frame(
            body, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=8, pady=6,
        )
        slots_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        slots_hdr = tk.Frame(slots_panel, bg=colors["surface"])
        slots_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(
            slots_hdr, text="MIXER SNAPSHOTS (SLOTS 01–15 + RESET)",
            font=self.fonts["eyebrow"], fg=colors["text"], bg=colors["surface"],
        ).pack(side="left")

        grid_frame = tk.Frame(slots_panel, bg=colors["surface"])
        grid_frame.pack(fill="both", expand=True)
        for c in range(4):
            grid_frame.grid_columnconfigure(c, weight=1, uniform="slot_cell")
        for r in range(4):
            grid_frame.grid_rowconfigure(r, weight=1, uniform="slot_row")

        accents = (colors["cyan"], colors["purple"], colors["warning"], colors["lime"])
        for slot in range(1, SLOT_COUNT + 1):
            accent = accents[(slot - 1) % len(accents)]
            r, c = divmod(slot - 1, 4)
            cell = tk.Frame(
                grid_frame, bg=colors["background_alt"],
                highlightbackground=colors["border"], highlightthickness=1,
                padx=5, pady=3,
            )
            cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)

            top_row = tk.Frame(cell, bg=colors["background_alt"])
            top_row.pack(fill="x")
            tk.Label(
                top_row, text=f"{slot:02d}", font=self.fonts["eyebrow"],
                fg=accent, bg=colors["surface_hover"], padx=4, pady=0,
            ).pack(side="left")
            tk.Label(
                top_row, text=slot_name(slot), font=self.fonts["status_key"],
                fg=colors["text"], bg=colors["background_alt"],
            ).pack(side="left", padx=(4, 0))

            meta_lbl = tk.Label(
                cell, text="Empty slot", font=self.fonts["caption"],
                fg=colors["text_secondary"], bg=colors["background_alt"], anchor="w",
            )
            meta_lbl.pack(fill="x", pady=(2, 2))

            btn_row = tk.Frame(cell, bg=colors["background_alt"])
            btn_row.pack(fill="x", side="bottom")
            load_btn = self._compact_btn(
                btn_row, "LOAD", colors["cyan"], lambda s=slot: self._recall_slot(s)
            )
            load_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))
            cap_btn = self._compact_btn(
                btn_row, "SAVE", colors["lime"], lambda s=slot: self._capture_slot(s)
            )
            cap_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))
            self._slot_rows[slot] = (meta_lbl, load_btn)

        # 16th Cell: Safety-Locked Slot 16 (MIXER RESET — PC 16 on Ch 16 blocked)
        reset_cell = tk.Frame(
            grid_frame, bg=colors["safety_bg"],
            highlightbackground=colors["safety_border"], highlightthickness=1,
            padx=5, pady=3,
        )
        reset_cell.grid(row=3, column=3, sticky="nsew", padx=2, pady=2)
        r_top = tk.Frame(reset_cell, bg=colors["safety_bg"])
        r_top.pack(fill="x")
        tk.Label(
            r_top, text="16", font=self.fonts["eyebrow"],
            fg=colors["warning"], bg=colors["surface_alt"], padx=4, pady=0,
        ).pack(side="left")
        tk.Label(
            r_top, text="RESET", font=self.fonts["eyebrow"],
            fg=colors["danger"], bg=colors["safety_bg"],
        ).pack(side="left", padx=(4, 0))
        tk.Label(
            reset_cell, text="PC 16 Ch 16 Blocked", font=self.fonts["caption"],
            fg=colors["warning"], bg=colors["safety_bg"], anchor="w",
        ).pack(fill="x", pady=(2, 2))
        self.reset_slot_btn = tk.Button(
            reset_cell,
            text="LOCKED (SR-03)",
            font=self.fonts["status_key"],
            bg=colors["surface_alt"],
            fg=colors["text_muted"],
            disabledforeground=colors["warning"],
            bd=0,
            relief="flat",
            state="disabled",
            pady=1,
        )
        self.reset_slot_btn.pack(fill="x", side="bottom")

        # Right Column: Searchable / Sortable Thai-Ready Snapshot Library
        lib_panel = tk.Frame(
            body, bg=colors["surface"],
            highlightbackground=colors["border"], highlightthickness=1,
            padx=8, pady=6,
        )
        lib_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        lib_hdr = tk.Frame(lib_panel, bg=colors["surface"])
        lib_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(
            lib_hdr, text="SNAPSHOT LIBRARY (VOCALIST / VENUE)",
            font=self.fonts["eyebrow"], fg=colors["text"], bg=colors["surface"],
        ).pack(side="left")
        tk.Label(
            lib_hdr, textvariable=self.library_count_var,
            font=self.fonts["status_key"], fg=colors["cyan_soft"], bg=colors["surface"],
        ).pack(side="right")

        # Save New Named Snapshot Row (Supports Thai & English names)
        save_row = tk.Frame(lib_panel, bg=colors["surface"])
        save_row.pack(fill="x", pady=(0, 4))
        self.lib_name_entry = tk.Entry(
            save_row,
            textvariable=self.lib_name_var,
            font=self.thai_font,
            bg=colors["background_alt"],
            fg=colors["text"],
            insertbackground=colors["cyan"],
            highlightbackground=colors["border"],
            highlightcolor=colors["cyan"],
            highlightthickness=1,
            bd=0,
        )
        self.lib_name_entry.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 4))
        self.lib_save_btn = self._compact_btn(
            save_row, "+ SAVE PRESET", colors["lime"], self.save_to_library
        )
        self.lib_save_btn.pack(side="right")

        # Search & Sort Row
        filter_row = tk.Frame(lib_panel, bg=colors["surface"])
        filter_row.pack(fill="x", pady=(0, 4))
        tk.Label(
            filter_row, text="SEARCH:", font=self.fonts["status_key"],
            fg=colors["text_muted"], bg=colors["surface"],
        ).pack(side="left", padx=(0, 4))
        self.search_entry = tk.Entry(
            filter_row,
            textvariable=self.search_var,
            font=self.thai_font,
            bg=colors["background_alt"],
            fg=colors["text"],
            insertbackground=colors["cyan"],
            highlightbackground=colors["border"],
            highlightcolor=colors["cyan"],
            highlightthickness=1,
            bd=0,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 4))
        self.sort_btn = self._compact_btn(
            filter_row, "SORT: DATE", colors["cyan_soft"], self.toggle_sort_mode
        )
        self.sort_btn.pack(side="right")

        # Library Entries Container
        self.library_list_frame = tk.Frame(lib_panel, bg=colors["background_alt"])
        self.library_list_frame.pack(fill="both", expand=True)

        # 4. Bottom Safety Footer
        safety = tk.Frame(
            self, bg=colors["safety_bg"],
            highlightbackground=colors["safety_border"], highlightthickness=1,
            padx=10, pady=4,
        )
        safety.pack(fill="x", padx=pad, pady=(0, 6))
        tk.Label(
            safety, text="SCENE RECALL PROTECTION:", font=self.fonts["eyebrow"],
            fg=colors["danger"], bg=colors["safety_bg"],
        ).pack(side="left", padx=(0, 6))
        tk.Label(
            safety,
            text="Recalls fader, pan, mute, EQ, HPF, comp, and sends as 1 atomic undo step. +48V, Preamp Gain, and PC 16 Reset are strictly excluded.",
            font=self.fonts["caption"], fg=colors["text_secondary"], bg=colors["safety_bg"], anchor="w",
        ).pack(side="left", fill="x")

    def _pill_btn(self, parent: tk.Misc, text: str, accent: str, command: Callable[[], Any]) -> tk.Button:
        colors = theme.COLORS
        return tk.Button(
            parent, text=text, font=self.fonts["caption"],
            bg=colors["pill_bg"], fg=accent,
            activebackground=colors["surface_hover"], activeforeground=accent,
            disabledforeground=colors["text_muted"],
            highlightbackground=accent, highlightthickness=1,
            bd=0, relief="flat", cursor="hand2", padx=8, pady=2,
            command=command,
        )

    def _compact_btn(self, parent: tk.Misc, text: str, accent: str, command: Callable[[], Any]) -> tk.Button:
        colors = theme.COLORS
        return tk.Button(
            parent, text=text, font=self.fonts["status_key"],
            bg=colors["pill_bg"], fg=accent,
            activebackground=colors["surface_hover"], activeforeground=accent,
            disabledforeground=colors["text_muted"],
            bd=0, relief="flat", cursor="hand2", padx=6, pady=2,
            command=command,
        )

    def _report(self, msg: str) -> None:
        if self.on_feedback:
            self.on_feedback(msg)

    # -- Recall Scope (WHAT TO LOAD) ----------------------------------------

    def active_recall_scopes(self) -> list[str]:
        """Return currently checked WHAT TO LOAD recall scopes in canonical order."""
        return [sc for sc in RECALL_SCOPES if self.scope_vars[sc].get()]

    def set_recall_scope(self, scopes: Iterable[str]) -> None:
        wanted = {str(s).upper() for s in scopes}
        for sc in RECALL_SCOPES:
            self.scope_vars[sc].set(sc in wanted)

    def mark_scene_edited(self) -> None:
        if self._loaded_scene_name:
            self.scene_edited = True
            self.current_scene_var.set(f"{self._loaded_scene_name} · EDITED")

    # -- Refresh ------------------------------------------------------------

    def refresh(self) -> None:
        names = set(self.service.scenes.names()) if self.service is not None else set()
        for slot, (meta_lbl, load_btn) in self._slot_rows.items():
            sname = slot_name(slot)
            if sname in names:
                snap = self.service.scenes.get(sname)
                sc_str = _format_scopes(scope_counts(snap.parameters))
                count = sum(len(v) for v in snap.parameters.values())
                meta_lbl.configure(text=f"{sc_str} ({count})")
                load_btn.configure(state="normal")
            else:
                meta_lbl.configure(text="Empty slot")
                load_btn.configure(state="disabled")
        self._rebuild_library_list()

    def _capture_slot(self, slot: int) -> None:
        if self.service is None:
            return
        sname = slot_name(slot)
        try:
            snap = self.service.capture_scene(sname)
            self._loaded_scene_name = sname
            self.scene_edited = False
            self.current_scene_var.set(sname)
            count = sum(len(v) for v in snap.parameters.values())
            self.current_meta_var.set(f"Saved {len(snap.parameters)} targets · {count} values")
            self._report(f"SCENE CAPTURED — {sname} · {count} VALUES")
        except Exception as exc:
            self._report(f"SCENE CAPTURE REJECTED — {exc}")
        self.refresh()

    def _recall_slot(self, slot: int) -> None:
        if self.service is None:
            return
        sname = slot_name(slot)
        scopes = self.active_recall_scopes()
        if not scopes:
            self._report("SCENE RECALL REJECTED — SELECT AT LEAST ONE SCOPE IN WHAT TO LOAD")
            return
        full_scope = len(scopes) == len(RECALL_SCOPES)
        try:
            res = (
                self.service.recall_scene(sname)
                if full_scope
                else self.service.recall_scene(sname, scope=scopes)
            )
            self._loaded_scene_name = sname
            self.scene_edited = not full_scope
            self.current_scene_var.set(sname if full_scope else f"{sname} · EDITED")
            scope_note = "ALL SCOPES" if full_scope else "+".join(scopes)
            self.current_meta_var.set(f"Recalled ({scope_note}) · {res.applied} applied, {len(res.failed)} failed")
            self._report(f"SCENE RECALLED — {sname}" if full_scope else f"SCENE RECALLED ({scope_note}) — {sname}")
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

    # -- Snapshot Library (Named Presets with Thai Support) -----------------

    def toggle_sort_mode(self) -> str:
        new_mode = "name" if self.sort_mode_var.get() == "date" else "date"
        self.sort_mode_var.set(new_mode)
        self.sort_btn.configure(text=f"SORT: {new_mode.upper()}")
        self._rebuild_library_list()
        return new_mode

    def filtered_library_entries(self) -> list[dict[str, Any]]:
        entries = list(self.library.summaries())
        query = self.search_var.get().strip().lower()
        if query:
            entries = [e for e in entries if query in str(e.get("name", "")).lower()]
        if self.sort_mode_var.get() == "name":
            entries.sort(key=lambda e: str(e.get("name", "")).lower())
        else:
            entries.sort(key=lambda e: str(e.get("updatedAt", "")), reverse=True)
        return entries

    def save_to_library(self, name: Optional[str] = None, entry_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        if self.service is None:
            self._report("LIBRARY SAVE UNAVAILABLE — NO COMMAND SERVICE")
            return None
        chosen = (name if name is not None else self.lib_name_var.get()).strip()
        if not chosen:
            chosen = f"Preset {len(self.library.summaries()) + 1}"
        try:
            saved = self.library.save(chosen, self.service.known_mix_state(), entry_id=entry_id)
            self.lib_name_var.set("")
            self._report(f"LIBRARY SAVED — {saved['name']}")
            self._rebuild_library_list()
            return saved
        except Exception as exc:
            self._report(f"LIBRARY SAVE REJECTED — {exc}")
            return None

    def load_library_entry(self, entry_id: str) -> bool:
        if self.service is None:
            return False
        scopes = self.active_recall_scopes()
        if not scopes:
            self._report("LIBRARY LOAD REJECTED — SELECT AT LEAST ONE SCOPE IN WHAT TO LOAD")
            return False
        full_scope = len(scopes) == len(RECALL_SCOPES)
        try:
            entry = self.library.get(entry_id)
            params = self.library.parameters(entry_id)
            res = self.service.apply_mix_state(
                entry["name"], params, None if full_scope else scopes
            )
            self._loaded_scene_name = entry["name"]
            self.scene_edited = not full_scope
            self.current_scene_var.set(entry["name"] if full_scope else f"{entry['name']} · EDITED")
            scope_note = "ALL SCOPES" if full_scope else "+".join(scopes)
            self.current_meta_var.set(f"Library ({scope_note}) · {res.applied} applied")
            self._report(f"LIBRARY LOADED — {entry['name']}")
            if self.on_recalled:
                self.on_recalled()
            return True
        except Exception as exc:
            self._report(f"LIBRARY LOAD FAILED — {exc}")
            return False

    def rename_library_entry(self, entry_id: str, new_name: str) -> bool:
        try:
            self.library.rename(entry_id, new_name)
            self._report(f"LIBRARY RENAMED — {new_name.strip()}")
            self._rebuild_library_list()
            return True
        except Exception as exc:
            self._report(f"LIBRARY RENAME FAILED — {exc}")
            return False

    def delete_library_entry(self, entry_id: str) -> bool:
        try:
            self.library.delete(entry_id)
            self._report("LIBRARY ENTRY DELETED")
            self._rebuild_library_list()
            return True
        except Exception as exc:
            self._report(f"LIBRARY DELETE FAILED — {exc}")
            return False

    def export_snapshot_library_data(self) -> dict[str, Any]:
        return self.library.export()

    def import_snapshot_library_data(self, data: Any) -> dict[str, Any]:
        res = self.library.import_data(data)
        self._rebuild_library_list()
        return res

    def _rebuild_library_list(self) -> None:
        colors = theme.COLORS
        for child in self.library_list_frame.winfo_children():
            child.destroy()
        self.library_row_widgets.clear()

        all_entries = self.library.summaries()
        self.library_count_var.set(f"{len(all_entries)} preset{'s' if len(all_entries) != 1 else ''}")
        entries = self.filtered_library_entries()

        if not entries:
            msg = "No matching presets" if self.search_var.get().strip() else "Library is empty — enter a name above and click + SAVE PRESET"
            tk.Label(
                self.library_list_frame,
                text=msg,
                font=self.fonts["caption"],
                fg=colors["text_muted"],
                bg=colors["background_alt"],
                pady=12,
            ).pack(fill="x")
            return

        # Render up to 7 visible rows cleanly so 1280x720 never clips vertically
        for entry in entries[:7]:
            eid = entry["id"]
            row = tk.Frame(
                self.library_list_frame,
                bg=colors["surface"],
                highlightbackground=colors["border"],
                highlightthickness=1,
                padx=6,
                pady=3,
            )
            row.pack(fill="x", padx=3, pady=2)

            name_lbl = tk.Label(
                row,
                text=entry["name"],
                font=self.thai_bold,
                fg=colors["text"],
                bg=colors["surface"],
                anchor="w",
            )
            name_lbl.pack(side="left", fill="x", expand=True)

            sc_lbl = tk.Label(
                row,
                text=_format_scopes(entry.get("scopes", {})),
                font=self.fonts["status_key"],
                fg=colors["text_secondary"],
                bg=colors["surface"],
                padx=4,
            )
            sc_lbl.pack(side="left")

            del_btn = self._compact_btn(
                row, "DEL", colors["danger"], lambda i=eid: self.delete_library_entry(i)
            )
            del_btn.pack(side="right", padx=(2, 0))
            load_btn = self._compact_btn(
                row, "LOAD", colors["cyan"], lambda i=eid: self.load_library_entry(i)
            )
            load_btn.pack(side="right", padx=(2, 0))

            self.library_row_widgets[eid] = {
                "row": row,
                "name_label": name_lbl,
                "scope_label": sc_lbl,
                "load_btn": load_btn,
                "delete_btn": del_btn,
            }

    # -- File Import / Export -----------------------------------------------

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
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("format") == "flow8-snapshot-library-v1":
                res = self.import_snapshot_library_data(raw)
                self._report(f"SNAPSHOT LIBRARY IMPORTED — {res['added']} ADDED, {res['skipped']} SKIPPED")
            else:
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
            if self.library.summaries():
                Path(path).write_text(
                    json.dumps(self.export_snapshot_library_data(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                export_library_json(self.service, path)
            self._report(f"LIBRARY EXPORTED — {path}")
        except Exception as exc:
            self._report(f"LIBRARY EXPORT FAILED — {exc}")
