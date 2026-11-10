"""Safety gates for destructive or electrically significant mixer actions."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Optional


class _PhantomToken:
    __slots__ = ("channel_index", "nonce", "active", "consumed")

    def __init__(self, channel_index: int, nonce: object) -> None:
        self.channel_index = channel_index
        self.nonce = nonce
        self.active = True
        self.consumed = False


@dataclass
class PhantomConfirmation:
    """Handle owned by one active confirmation request/dialog."""

    gate: "PhantomPowerSafetyGate"
    channel_index: int
    token: _PhantomToken
    dialog: Optional[tk.Toplevel] = None
    service: Any = None
    on_complete: Any = None

    @property
    def confirmation_token(self) -> _PhantomToken:
        return self.token

    def cancel(self) -> None:
        self.gate.cancel(self)


class PhantomPowerSafetyGate:
    """Single-use, channel-bound capability gate for +48V enable."""

    ALLOWED_CHANNELS = frozenset((1, 2))

    def __init__(self) -> None:
        self._active: dict[int, PhantomConfirmation] = {}

    def request_confirmation(
        self,
        channel_index: int,
        parent: Optional[tk.Misc] = None,
        service: Any = None,
        on_complete: Any = None,
    ) -> PhantomConfirmation:
        if channel_index not in self.ALLOWED_CHANNELS:
            raise ValueError("+48V is available only on MIC 1 and MIC 2")
        previous = self._active.pop(channel_index, None)
        if previous is not None:
            previous.token.active = False
            self._close_dialog(previous)
        request = PhantomConfirmation(
            gate=self,
            channel_index=channel_index,
            token=_PhantomToken(channel_index, object()),
            service=service,
            on_complete=on_complete,
        )
        self._active[channel_index] = request
        if parent is not None:
            self._show_dialog(parent, request)
        return request

    def confirm_and_dispatch(
        self, service: Any, channel_index: int, confirmation_token: Any
    ) -> bool:
        """Consume a valid capability exactly once, then dispatch +48V ON."""
        if not isinstance(confirmation_token, _PhantomToken):
            return False
        if service is None:
            self.cancel(self._active.get(channel_index)) if channel_index in self._active else None
            return False
        request = self._active.get(channel_index)
        if request is None or request.token is not confirmation_token:
            return False
        token = confirmation_token
        if (
            not token.active
            or token.consumed
            or token.channel_index != channel_index
            or channel_index not in self.ALLOWED_CHANNELS
        ):
            return False
        token.consumed = True
        token.active = False
        self._active.pop(channel_index, None)
        self._close_dialog(request)
        service.set_phantom(channel_index, True)
        if request.on_complete:
            request.on_complete(True)
        return True

    def cancel(self, request: PhantomConfirmation) -> None:
        if self._active.get(request.channel_index) is request:
            self._active.pop(request.channel_index, None)
        request.token.active = False
        self._close_dialog(request)

    def _show_dialog(self, parent: tk.Misc, request: PhantomConfirmation) -> None:
        dialog = tk.Toplevel(parent)
        request.dialog = dialog
        dialog.title("Confirm +48V Phantom Power")
        dialog.transient(parent)
        dialog.resizable(False, False)
        body = tk.Frame(dialog, padx=20, pady=16)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text=f"Enable +48V Phantom Power on MIC {request.channel_index}?",
            justify="left",
        ).pack(anchor="w")
        tk.Label(
            body,
            text="Confirm only if the connected microphone/input requires phantom power.",
            justify="left",
        ).pack(anchor="w", pady=(8, 14))
        actions = tk.Frame(body)
        actions.pack(anchor="e")
        tk.Button(actions, text="Cancel", command=request.cancel).pack(side="left", padx=(0, 8))
        tk.Button(
            actions,
            text="Confirm +48V",
            command=lambda: self.confirm_and_dispatch(
                request.service,
                request.channel_index,
                request.token,
            ),
        ).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", request.cancel)
        dialog.bind("<Escape>", lambda _event: request.cancel())
        dialog.grab_set()

    @staticmethod
    def _close_dialog(request: PhantomConfirmation) -> None:
        if request.dialog is not None and request.dialog.winfo_exists():
            try:
                request.dialog.grab_release()
            except tk.TclError:
                pass
            request.dialog.destroy()
            request.dialog = None
