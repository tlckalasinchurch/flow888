"""Hardware safety gates and confirmation dialogs for FLOW 8 controls (UI.2-T4-02).

Enforces non-negotiable hardware safety for high-risk parameters:
1. +48V Phantom Power:
   - Requires explicit confirmation before enabling.
   - Restricted strictly to Mic inputs 1 and 2 (channels 1 & 2).
   - Cancel produces zero dispatch.
   - Dispatches only through Flow8Service -> Flow8CommandBoundary.
2. Analog Preamp Gain:
   - Staged editing workflow: Preview -> Apply -> Confirm.
   - Disallow continuous or drag-based dispatch.
   - Gated when mapping is an unverified approximation.
"""

from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from flow8.ui import theme


# S1.2: the headless phantom safety policy lives in flow8.safety (shared with the service and the command
# boundary). The names are re-exported here so existing imports keep working.
from flow8 import safety as _safety
from flow8.safety import (  # noqa: F401  (re-exports)
    PhantomPowerConfirmationToken,
    PhantomPowerSafetyGate,
    _PhantomPendingRequest,
)


class PhantomPowerConfirmationDialog(tk.Toplevel):
    """Cyber Neon modal confirmation dialog for +48V phantom power."""

    def __init__(
        self,
        parent: tk.Misc,
        channel_index: int,
        on_confirm: Callable[[PhantomPowerConfirmationToken], None],
        on_cancel: Optional[Callable[[], None]] = None,
        confirmation_token: Optional[PhantomPowerConfirmationToken] = None,
    ) -> None:
        super().__init__(parent)
        PhantomPowerSafetyGate.validate_channel(channel_index)

        self.channel_index = channel_index
        if confirmation_token is None:
            self.confirmation_token = PhantomPowerSafetyGate.issue_token(channel_index)
        else:
            # A caller-supplied token must already be gate-issued; a forged one is
            # rejected by confirm_and_dispatch, so it is never re-registered here.
            self.confirmation_token = confirmation_token

        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self.confirmed = False
        self._resolved = False

        self.title("+48V PHANTOM POWER WARNING")
        self.configure(bg=theme.COLORS["background"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        self._build()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _: self._cancel())

    def _build(self) -> None:
        colors = theme.COLORS
        padding = 16

        container = tk.Frame(self, bg=colors["surface"], padx=padding, pady=padding)
        container.pack(fill="both", expand=True, padx=2, pady=2)

        # Header Badge
        header_frame = tk.Frame(container, bg=colors["surface"])
        header_frame.pack(fill="x", pady=(0, 12))

        tk.Label(
            header_frame,
            text=f"TARGET: CHANNEL {self.channel_index:02d} (MIC {self.channel_index})",
            font=("Segoe UI", 11, "bold"),
            fg=colors["cyan"],
            bg=colors["surface_alt"],
            padx=8,
            pady=4,
        ).pack(side="left")

        tk.Label(
            header_frame,
            text="+48V RELAY",
            font=("Segoe UI", 9, "bold"),
            fg=colors["danger"],
            bg=colors["surface_alt"],
            padx=8,
            pady=4,
        ).pack(side="right")

        # Warning Body
        tk.Label(
            container,
            text=PhantomPowerSafetyGate.WARNING_TEXT,
            font=("Segoe UI", 10),
            fg=colors["text"],
            bg=colors["surface"],
            justify="left",
            wraplength=420,
        ).pack(fill="x", pady=(0, 16))

        # Action Buttons
        btn_row = tk.Frame(container, bg=colors["surface"])
        btn_row.pack(fill="x", pady=(8, 0))

        tk.Button(
            btn_row,
            text="CANCEL",
            font=("Segoe UI", 10, "bold"),
            fg=colors["text_secondary"],
            bg=colors["surface_alt"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["text"],
            relief="flat",
            padx=16,
            pady=6,
            command=self._cancel,
        ).pack(side="left")

        tk.Button(
            btn_row,
            text="CONFIRM +48V",
            font=("Segoe UI", 10, "bold"),
            fg=colors["background"],
            bg=colors["danger"],
            activebackground=colors["warning"],
            activeforeground=colors["background"],
            relief="flat",
            padx=16,
            pady=6,
            command=self._confirm,
        ).pack(side="right")

    def _cancel(self) -> None:
        # One-shot: a dialog resolves exactly once, so a late or repeated event
        # can never turn into a second callback.
        if self._resolved:
            return
        self._resolved = True
        self.confirmed = False
        PhantomPowerSafetyGate.revoke_token(self.confirmation_token)
        try:
            if self._on_cancel:
                self._on_cancel()
        finally:
            self.destroy()

    def _confirm(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.confirmed = True
        try:
            self._on_confirm(self.confirmation_token)
        finally:
            self.destroy()


class AnalogGainSafetyGate:
    """Staged editing safety controller for Analog Preamp Gain.

    Workflow:
        Preview -> Apply -> Confirm.
    Enforces that continuous slider dragging or preview does not dispatch to hardware.
    Gated against unverified firmware dB curves.
    """

    ALLOWED_CHANNELS = (1, 2, 3, 4)
    MIN_DB = -20.0
    MAX_DB = 60.0

    def __init__(self, channel_index: int, initial_gain_db: float = 0.0) -> None:
        if channel_index not in self.ALLOWED_CHANNELS:
            raise ValueError(
                f"Analog preamp gain is restricted to Channels 1-4. Channel {channel_index} has no analog preamp."
            )
        self.channel_index = channel_index
        self.current_gain_db = float(initial_gain_db)
        self.preview_gain_db = float(initial_gain_db)
        self.is_staged = False

    @staticmethod
    def is_verified_mapping_available() -> bool:
        """Check whether the analog gain dB calibration curve is verified on hardware.

        The FLOW 8 discrete Midas step curve is an UNVERIFIED APPROXIMATION in parameter_mapping.py.
        """
        # S1.2 (D2): the answer comes from the shared policy; there is no other way to change it.
        return "gain" not in _safety.BLOCKED_PARAMETER_TYPES

    def stage_preview(self, proposed_db: float) -> float:
        """Stage a proposed gain value for preview without dispatching."""
        clamped = max(self.MIN_DB, min(self.MAX_DB, float(proposed_db)))
        self.preview_gain_db = clamped
        self.is_staged = (self.preview_gain_db != self.current_gain_db)
        return self.preview_gain_db

    def cancel_staged(self) -> float:
        """Cancel staged changes and preserve previous applied state."""
        self.preview_gain_db = self.current_gain_db
        self.is_staged = False
        return self.current_gain_db

    def commit_gain(self, service: Any, confirmed: bool = False) -> bool:
        """Attempt to commit gain. Needs a verified mapping AND explicit confirmation.

        No analog-gain dispatch path exists yet, so even a verified, confirmed commit
        must not claim success without sending: it stays gated until one is wired.
        """
        if not self.is_verified_mapping_available():
            raise RuntimeError(
                f"Hardware gain dispatch is gated: Preamp Gain dB curve is an UNVERIFIED APPROXIMATION. "
                f"Physical hardware calibration evidence is required before automatic dispatch."
            )
        if not confirmed:
            raise RuntimeError("Gain commit requires explicit confirmation; nothing sent.")
        raise NotImplementedError("No analog-gain dispatch path exists; nothing sent.")
