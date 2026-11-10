"""Navigation rail for the FLOW 8 Cyber Neon shell.

Only the Mixer destination is reachable in UI.2-T1. The remaining four are
present, visibly disabled, and labelled ``NOT IMPLEMENTED`` so the operator can
see the roadmap gap. They never open a page and never pretend to work.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

from flow8.ui import theme
from flow8.ui.components import widget_texts


@dataclass(frozen=True)
class NavItem:
    """One navigation destination and its honest availability."""

    key: str
    label: str
    enabled: bool
    note: str = ""


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("mixer", "Mixer", True),
    NavItem("routing", "Routing", False, "NOT IMPLEMENTED"),
    NavItem("fx", "FX", False, "NOT IMPLEMENTED"),
    NavItem("scenes", "Scenes", False, "NOT IMPLEMENTED"),
    NavItem("recording", "Recording", False, "NOT IMPLEMENTED"),
)


class Navigation(tk.Frame):
    """Vertical destination rail with restrained neon active state."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        on_select: Optional[Callable[[str], bool]] = None,
    ) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["background_alt"],
            width=theme.NAVIGATION_WIDTH,
        )
        self.grid_propagate(False)
        self.fonts = fonts
        self._on_select = on_select
        self.items: dict[str, NavItem] = {item.key: item for item in NAV_ITEMS}
        self.buttons: dict[str, tk.Button] = {}
        self._accent_bars: dict[str, tk.Frame] = {}
        self.selected: Optional[str] = None
        self._build()

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        tk.Label(
            self,
            text="WORKSPACE",
            font=self.fonts["eyebrow"],
            fg=colors["text_muted"],
            bg=colors["background_alt"],
            anchor="w",
        ).pack(
            fill="x",
            padx=spacing["spacing_large"],
            pady=(spacing["spacing_large"], spacing["spacing_small"]),
        )

        for item in NAV_ITEMS:
            self._build_row(item)

        # Faint rail edge separating navigation from the workspace.
        tk.Frame(self, bg=colors["border"], width=1).place(
            relx=1.0, rely=0.0, relheight=1.0, anchor="ne"
        )

    def _build_row(self, item: NavItem) -> None:
        colors = theme.COLORS
        row = tk.Frame(
            self,
            bg=colors["background_alt"],
            height=theme.NAV_ITEM_HEIGHT,
        )
        row.pack(fill="x")
        row.pack_propagate(False)

        bar = tk.Frame(row, bg=colors["background_alt"], width=3)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)
        self._accent_bars[item.key] = bar

        cell = tk.Frame(row, bg=colors["background_alt"])
        cell.pack(side="left", fill="both", expand=True, padx=(6, 14), pady=(10, 6))

        button = tk.Button(
            cell,
            text=item.label,
            font=self.fonts["nav"],
            anchor="w",
            bd=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2" if item.enabled else "",
            padx=0,
            pady=0,
            bg=colors["background_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["text"],
            disabledforeground=colors["text_muted"],
            state="normal" if item.enabled else "disabled",
            command=lambda key=item.key: self._activate(key),
        )
        button.pack(fill="x")
        self.buttons[item.key] = button

        if item.note:
            tk.Label(
                cell,
                text=item.note,
                font=self.fonts["caption"],
                fg=colors["warning"],
                bg=colors["background_alt"],
                anchor="w",
            ).pack(fill="x")

        if item.enabled:
            button.bind("<Enter>", lambda _event, key=item.key: self._hover(key, True))
            button.bind("<Leave>", lambda _event, key=item.key: self._hover(key, False))

    # -- interaction --------------------------------------------------------

    def _activate(self, key: str) -> None:
        if self._on_select is not None:
            self._on_select(key)
        else:
            self.select(key)

    def _hover(self, key: str, entering: bool) -> None:
        if key == self.selected:
            return
        button = self.buttons[key]
        button.configure(
            bg=theme.COLORS["surface_hover"] if entering else theme.COLORS["background_alt"]
        )

    def is_enabled(self, key: str) -> bool:
        item = self.items.get(key)
        return bool(item and item.enabled)

    def select(self, key: str) -> bool:
        """Highlight *key* if it is a real destination. Returns success."""
        item = self.items.get(key)
        if item is None or not item.enabled:
            return False
        if self.selected == key:
            return True

        if self.selected is not None:
            self._paint(self.selected, active=False)

        self.selected = key
        self._paint(key, active=True)
        return True

    def _paint(self, key: str, active: bool) -> None:
        colors = theme.COLORS
        button = self.buttons[key]
        bar = self._accent_bars[key]
        if active:
            bar.configure(bg=colors["cyan"])
            button.configure(
                bg=colors["surface_alt"],
                fg=colors["cyan"],
                font=self.fonts["nav_active"],
            )
        else:
            bar.configure(bg=colors["background_alt"])
            button.configure(
                bg=colors["background_alt"],
                fg=colors["text_secondary"],
                font=self.fonts["nav"],
            )

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered in the rail."""
        return widget_texts(self)
