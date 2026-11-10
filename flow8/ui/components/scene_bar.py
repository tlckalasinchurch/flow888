"""Scene snapshot controls: eight slots, CAPTURE and RECALL (UI.2-T5).

Presentation only. The bar never touches the service: it reports which slot the
operator chose and which button was pressed, and the mixer console performs the
capture or recall through ``Flow8Service`` and reports the truthful outcome.
+48V phantom power is not part of a scene and is deliberately absent here.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable, Optional

from flow8.ui import theme

SLOT_COUNT = 8


def slot_name(slot: int) -> str:
    """The service-side scene name for a UI slot (1-8)."""
    return f"SCENE {slot}"


class SceneBar(tk.Frame):
    """Slot selector plus CAPTURE and RECALL buttons, sized for one banner row."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        on_capture: Optional[Callable[[int], None]] = None,
        on_recall: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self._on_capture = on_capture
        self._on_recall = on_recall
        self.selected_slot = 1
        self._populated: set[int] = set()
        self._enabled = True
        self.slot_buttons: dict[int, tk.Button] = {}
        self._build()
        self._refresh()

    def _build(self) -> None:
        colors = theme.COLORS
        tk.Label(
            self, text="SCENES", font=self.fonts["status_key"],
            fg=colors["text_secondary"], bg=colors["background"],
        ).pack(side="left", padx=(0, 6))

        for slot in range(1, SLOT_COUNT + 1):
            button = tk.Button(
                self,
                font=self.fonts["caption"],
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=3,
                pady=1,
                highlightthickness=2,
                command=lambda s=slot: self.select_slot(s),
            )
            button.pack(side="left", padx=1)
            self.slot_buttons[slot] = button

        self.capture_button = self._action_button("CAPTURE", self._capture_clicked)
        self.capture_button.pack(side="left", padx=(8, 2))
        self.recall_button = self._action_button("RECALL", self._recall_clicked)
        self.recall_button.pack(side="left")

    def _action_button(self, text: str, command: Callable[[], None]) -> tk.Button:
        colors = theme.COLORS
        return tk.Button(
            self,
            text=text,
            font=self.fonts["eyebrow"],
            bg=colors["surface_alt"],
            fg=colors["text"],
            activebackground=colors["cyan"],
            activeforeground=colors["background"],
            disabledforeground=colors["text_muted"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=1,
            command=command,
        )

    # -- state ----------------------------------------------------------------

    def select_slot(self, slot: int) -> None:
        if not 1 <= slot <= SLOT_COUNT:
            raise ValueError(f"scene slot must be 1-{SLOT_COUNT}, got {slot}")
        self.selected_slot = slot
        self._refresh()

    def set_populated(self, slots: Iterable[int]) -> None:
        self._populated = {s for s in slots if 1 <= s <= SLOT_COUNT}
        self._refresh()

    def set_enabled(self, enabled: bool) -> None:
        """Disable everything when there is no command service to capture from."""
        self._enabled = bool(enabled)
        self._refresh()

    def slot_populated(self, slot: int) -> bool:
        return slot in self._populated

    def _refresh(self) -> None:
        colors = theme.COLORS
        for slot, button in self.slot_buttons.items():
            populated = slot in self._populated
            selected = slot == self.selected_slot
            # State is shown by text as well as colour: ● saved, ○ empty.
            button.configure(
                text=f"{slot}{'●' if populated else '○'}",
                bg=colors["surface_alt"],
                fg=colors["cyan"] if populated else colors["text_muted"],
                activebackground=colors["surface_hover"],
                activeforeground=colors["text"],
                highlightbackground=colors["cyan"] if selected else colors["border"],
                highlightcolor=colors["cyan"],
                state="normal" if self._enabled else "disabled",
            )
        self.capture_button.configure(state="normal" if self._enabled else "disabled")
        can_recall = self._enabled and self.selected_slot in self._populated
        self.recall_button.configure(state="normal" if can_recall else "disabled")

    # -- actions ----------------------------------------------------------------

    def _capture_clicked(self) -> None:
        if self._on_capture is not None:
            self._on_capture(self.selected_slot)

    def _recall_clicked(self) -> None:
        if self._on_recall is not None:
            self._on_recall(self.selected_slot)
