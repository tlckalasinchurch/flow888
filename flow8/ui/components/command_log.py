"""Auditable command log panel for the FLOW 8 mixer console.

Dispatch status and hardware application are displayed as separate facts.
The panel never infers hardware application from a successful driver dispatch.
"""

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk
from typing import Any, Iterable

from flow8.ui import theme


class CommandLogPanel(tk.Frame):
    """Scrollable, newest-first view of command attempts and their evidence."""

    def __init__(self, master: tk.Misc, fonts: dict) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["surface"],
            highlightbackground=theme.COLORS["border"],
            highlightthickness=1,
            height=174,
        )
        self.pack_propagate(False)
        self.fonts = fonts
        self._build()

    def _build(self) -> None:
        colors = theme.COLORS
        heading = tk.Frame(self, bg=colors["surface"])
        heading.pack(fill="x", padx=10, pady=(6, 3))

        tk.Label(
            heading,
            text="COMMAND LOG",
            font=self.fonts["status_key"],
            fg=colors["cyan"],
            bg=colors["surface"],
        ).pack(side="left")

        legend = tk.Frame(heading, bg=colors["surface"])
        legend.pack(side="left", padx=(12, 0))

        for label, foreground in (
            ("CMD · LAST SENT", colors["cyan_soft"]),
            ("OBS · DEVICE INPUT", colors["purple_soft"]),
            ("UNSYNCED", colors["warning"]),
        ):
            tk.Label(
                legend,
                text=label,
                font=self.fonts["caption"],
                fg=foreground,
                bg=colors["surface_alt"],
                padx=6,
                pady=3,
            ).pack(side="left", padx=(0, 5))

        # Connection events are not mixer commands, so they get their own line
        # instead of being mixed into the audited command table.
        self.notice_var = tk.StringVar(value="")
        self.notice_label = tk.Label(
            heading,
            textvariable=self.notice_var,
            font=self.fonts["caption"],
            fg=colors["text_secondary"],
            bg=colors["surface"],
        )
        self.notice_label.pack(side="left", padx=(12, 0))

        self.count_var = tk.StringVar(value="0 EVENTS")
        tk.Label(
            heading,
            textvariable=self.count_var,
            font=self.fonts["status_key"],
            fg=colors["text_secondary"],
            bg=colors["surface_alt"],
            padx=8,
            pady=3,
        ).pack(side="right")

        body = tk.Frame(self, bg=colors["surface"])
        body.pack(fill="both", expand=True, padx=8, pady=(0, 7))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self)
        style.configure(
            "Flow8.Treeview",
            background=colors["background_alt"],
            fieldbackground=colors["background_alt"],
            foreground=colors["text"],
            rowheight=26,
            font=self.fonts["status_key"],
            borderwidth=0,
        )
        style.configure(
            "Flow8.Treeview.Heading",
            background=colors["surface_alt"],
            foreground=colors["text_secondary"],
            font=self.fonts["status_key"],
            relief="flat",
        )
        style.map(
            "Flow8.Treeview",
            background=[("selected", colors["surface_hover"])],
            foreground=[("selected", colors["cyan"])],
        )

        columns = (
            "time", "parameter", "commanded", "observed",
            "midi", "dispatch", "applied", "error",
        )
        self.tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            height=4,
            style="Flow8.Treeview",
        )
        headings = {
            "time": ("TIME", 72),
            "parameter": ("PARAMETER", 128),
            "commanded": ("CMD", 76),
            "observed": ("OBSERVED", 82),
            "midi": ("MIDI CH / CC · DATA", 154),
            "dispatch": ("DISPATCH", 132),
            "applied": ("HW APPLIED", 84),
            "error": ("ERROR", 210),
        }
        for key, (label, width) in headings.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=52, anchor="w", stretch=True)

        # Dispatch colours communicate transport state only, never hardware application.
        self.tree.tag_configure(
            "driver_dispatched",
            foreground=colors["cyan_soft"],
        )
        self.tree.tag_configure(
            "accepted_offline",
            foreground=colors["text_secondary"],
        )
        self.tree.tag_configure(
            "dispatch_problem",
            foreground=colors["danger"],
        )
        self.tree.tag_configure(
            "dispatch_unknown",
            foreground=colors["warning"],
        )

        vertical = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        self.empty_label = tk.Label(
            body,
            text="NO COMMANDS YET",
            font=self.fonts["status_key"],
            fg=colors["text_muted"],
            bg=colors["background_alt"],
            padx=10,
            pady=5,
        )
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    @staticmethod
    def _format_entry(entry: Any) -> tuple[str, ...]:
        timestamp = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S")
        observed = (
            str(entry.observed_value)
            if entry.observed_value is not None
            else "UNKNOWN"
        )
        if entry.midi_channel is None or entry.midi_cc is None:
            midi = "—"
        else:
            raw_value = (
                entry.raw_midi_sent
                if entry.raw_midi_sent is not None
                else entry.raw_midi_prepared
            )
            evidence = "sent" if entry.driver_dispatched else "prepared"
            midi = f"Ch {entry.midi_channel} / CC {entry.midi_cc} · {evidence} {raw_value}"

        if entry.hardware_applied is True:
            applied = "APPLIED"
        elif entry.hardware_applied is False:
            applied = "NOT APPLIED"
        else:
            applied = "UNKNOWN"

        return (
            timestamp,
            entry.param_id,
            str(entry.target_value),
            observed,
            midi,
            entry.dispatch_status,
            applied,
            (entry.error_message or "—")[:160],
        )

    NOTICE_LIMIT = 90

    def set_notice(self, text: str, problem: bool = False) -> None:
        """Show the latest connection event (full text stays in the status bar)."""
        shown = text if len(text) <= self.NOTICE_LIMIT else text[: self.NOTICE_LIMIT - 1] + "…"
        colors = theme.COLORS
        self.notice_var.set(shown)
        self.notice_label.configure(fg=colors["danger"] if problem else colors["text_secondary"])

    def set_entries(self, entries: Iterable[Any]) -> None:
        """Replace the visible snapshot, keeping the newest command at the top."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        snapshot = list(entries)
        self.count_var.set(f"{len(snapshot)} EVENTS")
        if snapshot:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

        for index, entry in enumerate(reversed(snapshot)):
            status = str(entry.dispatch_status)
            if status == "DRIVER_DISPATCHED":
                tag = "driver_dispatched"
            elif status == "ACCEPTED_OFFLINE":
                tag = "accepted_offline"
            elif status in ("REJECTED", "VALIDATION_FAILED", "DISPATCH_FAILED"):
                tag = "dispatch_problem"
            else:
                tag = "dispatch_unknown"

            self.tree.insert(
                "",
                "end",
                iid=f"command-{index}",
                values=self._format_entry(entry),
                tags=(tag,),
            )

        self.tree.yview_moveto(0.0)
