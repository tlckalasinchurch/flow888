"""
CueAir-adapted Audio Engineering Preset Browser for Behringer FLOW 8.
Docked/modal component allowing sound engineers to preview and apply curated
channel strips with Level Preservation Guarantee.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any, Callable, Optional, List

from flow8.presets import (
    ChannelPreset,
    list_channel_presets,
    get_channel_preset,
)
from flow8.ui import theme

logger = logging.getLogger(__name__)


class PresetPickerDialog(tk.Toplevel):
    """
    Modal Preset Picker for applying CueAir acoustic profiles to the selected channel.
    """

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        channel_index: int,
        channel_name: str,
        service: Any = None,
        on_applied: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(master)
        self.fonts = fonts
        self.channel_index = channel_index
        self.channel_name = channel_name
        self.service = service
        self.on_applied = on_applied

        self.title(f"Acoustic Presets — {channel_name}")
        self.geometry("640x520")
        self.minsize(580, 460)
        self.configure(bg=theme.COLORS["background"])

        self.transient(master)
        self.grab_set()

        self.selected_category_var = tk.StringVar(value="All")
        self.preserve_levels_var = tk.BooleanVar(value=True)
        self.selected_preset_id: Optional[str] = None
        self.status_var = tk.StringVar(value="")

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        colors = theme.COLORS

        # Header
        header = tk.Frame(self, bg=colors["surface"], padx=14, pady=10)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"ACOUSTIC PRESET BROWSER · CH {self.channel_index} ({self.channel_name})",
            font=self.fonts["title"],
            fg=colors["cyan"],
            bg=colors["surface"],
        ).pack(side="left")

        # Category Filter Bar
        cat_bar = tk.Frame(self, bg=colors["surface_alt"], padx=10, pady=6)
        cat_bar.pack(fill="x")

        tk.Label(
            cat_bar,
            text="CATEGORY:",
            font=self.fonts["eyebrow"],
            fg=colors["text_muted"],
            bg=colors["surface_alt"],
        ).pack(side="left", padx=(0, 8))

        categories = ["All", "Speech", "Vocal", "Acoustic", "Bass", "Drums", "Utility"]
        for cat in categories:
            btn = tk.Button(
                cat_bar,
                text=cat.upper(),
                font=self.fonts["caption"],
                bg=colors["surface"],
                fg=colors["text_secondary"],
                activebackground=colors["cyan"],
                activeforeground=colors["background"],
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda c=cat: self._on_select_category(c),
            )
            btn.pack(side="left", padx=2)

        # Split Body (List on left, Details on right)
        body = tk.Frame(self, bg=colors["background"], padx=10, pady=10)
        body.pack(fill="both", expand=True)

        # Left: Preset Listbox
        list_frame = tk.Frame(body, bg=colors["surface"], bd=1, relief="solid")
        list_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.listbox = tk.Listbox(
            list_frame,
            font=self.fonts["body"],
            bg=colors["surface"],
            fg=colors["text"],
            selectbackground=colors["cyan"],
            selectforeground=colors["background"],
            bd=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Right: Detail Card
        self.detail_frame = tk.Frame(body, bg=colors["surface"], bd=1, relief="solid", padx=12, pady=10)
        self.detail_frame.pack(side="right", fill="both", expand=True, padx=(6, 0))

        self.detail_title = tk.Label(
            self.detail_frame,
            text="Select a preset to inspect",
            font=self.fonts["subtitle"],
            fg=colors["cyan_soft"],
            bg=colors["surface"],
            anchor="w",
        )
        self.detail_title.pack(fill="x")

        self.detail_summary = tk.Label(
            self.detail_frame,
            text="",
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["surface"],
            wraplength=260,
            justify="left",
            anchor="w",
        )
        self.detail_summary.pack(fill="x", pady=(4, 8))

        # Parameters Spec Preview
        self.specs_frame = tk.Frame(self.detail_frame, bg=colors["surface_alt"], padx=8, pady=6)
        self.specs_frame.pack(fill="x", pady=4)

        self.lbl_eq = tk.Label(
            self.specs_frame, text="EQ: —", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["surface_alt"], anchor="w"
        )
        self.lbl_eq.pack(fill="x")

        self.lbl_lowcut = tk.Label(
            self.specs_frame, text="Low Cut: —", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["surface_alt"], anchor="w"
        )
        self.lbl_lowcut.pack(fill="x")

        self.lbl_comp = tk.Label(
            self.specs_frame, text="Compressor: —", font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["surface_alt"], anchor="w"
        )
        self.lbl_comp.pack(fill="x")

        # Acoustic Rationale Notes
        self.lbl_notes = tk.Label(
            self.detail_frame,
            text="",
            font=self.fonts["caption"],
            fg=colors["purple_soft"],
            bg=colors["surface"],
            wraplength=260,
            justify="left",
            anchor="w",
        )
        self.lbl_notes.pack(fill="x", pady=8)

        # Footer Actions
        footer = tk.Frame(self, bg=colors["surface"], padx=14, pady=10)
        footer.pack(fill="x")

        chk = tk.Checkbutton(
            footer,
            text="Preserve Fader & Gain (Safe Mix)",
            variable=self.preserve_levels_var,
            font=self.fonts["caption"],
            fg=colors["warning"],
            bg=colors["surface"],
            activebackground=colors["surface"],
            activeforeground=colors["warning"],
            selectcolor=colors["surface_alt"],
        )
        chk.pack(side="left")

        self.apply_button = tk.Button(
            footer,
            text="APPLY PRESET",
            font=self.fonts["eyebrow"],
            bg=colors["cyan"],
            fg=colors["background"],
            activebackground=colors["cyan_soft"],
            activeforeground=colors["background"],
            disabledforeground=colors["text_muted"],
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            state="disabled",
            command=self._on_apply,
        )
        self.apply_button.pack(side="right", padx=(8, 0))

        cancel_button = tk.Button(
            footer,
            text="CLOSE",
            font=self.fonts["eyebrow"],
            bg=colors["surface_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["text"],
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.destroy,
        )
        cancel_button.pack(side="right")

        tk.Label(
            footer,
            textvariable=self.status_var,
            font=self.fonts["caption"],
            fg=colors["success"],
            bg=colors["surface"],
        ).pack(side="right", padx=10)

    def _on_select_category(self, cat: str) -> None:
        self.selected_category_var.set(cat)
        self._refresh_list()

    def _refresh_list(self) -> None:
        cat = self.selected_category_var.get()
        presets = list_channel_presets(cat)
        self.listbox.delete(0, tk.END)
        self._current_presets = presets
        for p in presets:
            self.listbox.insert(tk.END, f"[{p.category}] {p.name}")

        if presets:
            self.listbox.selection_set(0)
            self._update_details(presets[0])
        else:
            self.apply_button.configure(state="disabled")

    def _on_listbox_select(self, _event: tk.Event) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._current_presets):
            self._update_details(self._current_presets[idx])

    def _update_details(self, preset: ChannelPreset) -> None:
        self.selected_preset_id = preset.id
        self.detail_title.configure(text=preset.name)
        self.detail_summary.configure(text=preset.summary)

        eq_text = f"EQ: Low {preset.eq_low_db:+.1f}dB | L-Mid {preset.eq_low_mid_db:+.1f}dB | H-Mid {preset.eq_hi_mid_db:+.1f}dB | Hi {preset.eq_hi_db:+.1f}dB"
        self.lbl_eq.configure(text=eq_text)

        if preset.low_cut_hz is not None:
            self.lbl_lowcut.configure(text=f"Low Cut (HPF): {preset.low_cut_hz:.0f} Hz (Ch 1-4)")
        else:
            self.lbl_lowcut.configure(text="Low Cut: Bypass / Not applicable")

        if preset.compressor_percent is not None:
            self.lbl_comp.configure(text=f"Compressor: {preset.compressor_percent:.0f}% intensity (Ch 1-4)")
        else:
            self.lbl_comp.configure(text="Compressor: Bypass / Not applicable")

        notes_summary = "\n".join(f"• {k}: {v}" for k, v in list(preset.notes.items())[:3])
        self.lbl_notes.configure(text=f"Acoustic Rationale:\n{notes_summary}")

        self.apply_button.configure(state="normal")
        self.status_var.set("")

    def _on_apply(self) -> None:
        if not self.selected_preset_id or not self.service:
            return

        preserve = self.preserve_levels_var.get()
        success = self.service.apply_channel_preset(
            self.channel_index,
            self.selected_preset_id,
            preserve_levels=preserve,
        )
        if success:
            preset = get_channel_preset(self.selected_preset_id)
            preset_name = preset.name if preset else self.selected_preset_id
            self.status_var.set(f"Applied '{preset_name}'!")
            if self.on_applied:
                self.on_applied(self.selected_preset_id)
        else:
            self.status_var.set("Failed to apply preset")
