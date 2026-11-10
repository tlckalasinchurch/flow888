"""Channel Detail Inspector for the FLOW 8 Cyber Neon console (UI2-T4-01).

Scope of this ticket, and nothing more:

* show which target is selected (one of the 7 logical input strips, or Main L/R);
* +48V phantom power for MIC 1 and MIC 2 only, ON behind an explicit
  confirmation dialog;
* an analog-gain PREVIEW that never dispatches (the dB mapping is an
  unverified approximation);
* commanded / observed values kept apart, with no hardware claims.

Architecture: this module is presentation only. Every command goes
``UI -> Flow8Service.set_phantom`` and from there through the existing parameter
engine and command boundary. It imports no MIDI driver, performs no encoding,
and never decides a parameter mapping.

Main L/R is its own target (``MAIN_TARGET``). It is not logical input strip 8.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.parameter_mapping import gain_midi_to_db
from flow8.ui import theme
from flow8.ui.components.controls import HorizontalSlider
from flow8.ui.safety_dialogs import (
    AnalogGainSafetyGate,
    PhantomPowerConfirmationDialog,
    PhantomPowerSafetyGate,
)

logger = logging.getLogger(__name__)

PHANTOM_CHANNELS = PhantomPowerSafetyGate.ALLOWED_CHANNELS
NO_RELAY_NOTE = "N/A — NO HARDWARE RELAY"
NO_PREAMP_NOTE = "N/A — NO ANALOG PREAMP"
NO_SERVICE_NOTE = "NO COMMAND SERVICE (offline shell) — +48V NOT SENT"


# ---------------------------------------------------------------------------
# Selection identity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SelectionTarget:
    """Identity of the inspected target.

    ``input`` targets use the existing logical strip numbers 1..7. ``main`` is
    the separate Main L/R master target and carries no strip number.
    """

    kind: str
    index: Optional[int] = None

    def __post_init__(self) -> None:
        if self.kind == "input":
            if (
                isinstance(self.index, bool)
                or not isinstance(self.index, int)
                or self.index not in LOGICAL_CHANNELS
            ):
                raise ValueError(
                    f"Input strips are logical channels 1-7; got {self.index!r}"
                )
        elif self.kind == "main":
            if self.index is not None:
                raise ValueError("Main L/R is not a numbered strip")
        else:
            raise ValueError(f"Unknown selection kind {self.kind!r}")

    @classmethod
    def input(cls, index: int) -> "SelectionTarget":
        return cls("input", index)


MAIN_TARGET = SelectionTarget("main")


def _valid_phantom_channel(channel_index: Any) -> bool:
    return (
        isinstance(channel_index, int)
        and not isinstance(channel_index, bool)
        and channel_index in PHANTOM_CHANNELS
    )


class _GainPreviewSlider(HorizontalSlider):
    """Preview slider over the raw 0-127 domain, without the pan centre detent."""

    def __init__(self, master, variable, command=None, default=0, accent=None, **kw):
        super().__init__(
            master, variable, command, default,
            accent or theme.COLORS["warning"], **kw,
        )

    def _value_from_event(self, event: tk.Event) -> int:
        w = max(self.winfo_width(), 60)
        left, right = self.PAD_X, w - self.PAD_X
        frac = (event.x - left) / float(right - left)
        return max(self.minimum, min(self.maximum, round(frac * self.maximum)))

    def _redraw(self) -> None:
        colors = theme.COLORS
        self.delete("all")
        h = max(self.winfo_height(), 28)
        cy = h / 2
        x = self._x_for(self.variable.get())
        left = self._x_for(0)
        self.create_rectangle(
            left, cy - 3, max(self.winfo_width(), 60) - self.PAD_X, cy + 3,
            fill=colors["background"], outline=colors["border"],
        )
        self.create_rectangle(left, cy - 2, x, cy + 2, fill=self.accent, outline="")
        hw = self.HANDLE_W / 2
        self.create_rectangle(
            x - hw, cy - 11, x + hw, cy + 11,
            fill=colors["surface_hover"], outline=self.accent, width=2,
        )


# ---------------------------------------------------------------------------
# Inspector panel
# ---------------------------------------------------------------------------

class ChannelDetailPanel(tk.Frame):
    """Right-hand docked inspector for the selected channel target."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_close: Optional[Callable[[], None]] = None,
        on_phantom_changed: Optional[Callable[[int, bool], None]] = None,
    ) -> None:
        colors = theme.COLORS
        super().__init__(
            master,
            bg=colors["surface"],
            highlightbackground=colors["cyan"],
            highlightthickness=1,
            bd=0,
        )
        self.pack_propagate(False)
        self.fonts = fonts
        self._service = service
        self._on_close = on_close
        self._on_phantom_changed = on_phantom_changed

        self.target: Optional[SelectionTarget] = None
        self._attached = False

        # phantom state
        self.phantom_available = False
        self._phantom_dialog: Optional[PhantomPowerConfirmationDialog] = None
        self._phantom_token: Optional[object] = None
        self._phantom_busy = False

        # gain preview state
        self.gain_available = False
        self.gain_gate: Optional[AnalogGainSafetyGate] = None
        self._gain_baseline = 0

        self.title_var = tk.StringVar(value="NO SELECTION")
        self.subtitle_var = tk.StringVar(value="")
        self.error_var = tk.StringVar(value="")
        self.phantom_cmd_var = tk.StringVar(value="—")
        self.phantom_obs_var = tk.StringVar(value="UNKNOWN")
        self.phantom_sync_var = tk.StringVar(value="UNSYNCED")
        self.phantom_note_var = tk.StringVar(value="")
        self.gain_cmd_var = tk.StringVar(value="")
        self.gain_preview_var = tk.IntVar(value=0)
        self.gain_preview_text_var = tk.StringVar(value="")
        self.gain_note_var = tk.StringVar(value="")

        # Text must wrap to the panel's current width (248-320 px), not a fixed one.
        self._wrap_labels: list[tk.Label] = []
        self.bind("<Configure>", self._rewrap)

        self._build()

    def _rewrap(self, _event: Optional[tk.Event] = None) -> None:
        wrap = max(120, self.winfo_width() - 28)
        for label in self._wrap_labels:
            label.configure(wraplength=wrap, justify="left")

    # -- construction -------------------------------------------------------

    def _label(self, parent, textvariable=None, text=None, font="caption",
               fg="text_secondary", bg="surface", **pack) -> tk.Label:
        colors = theme.COLORS
        kwargs: dict[str, Any] = dict(
            font=self.fonts[font], fg=colors[fg], bg=colors[bg], anchor="w",
        )
        if textvariable is not None:
            kwargs["textvariable"] = textvariable
        else:
            kwargs["text"] = text
        label = tk.Label(parent, **kwargs)
        self._wrap_labels.append(label)
        if pack is not None:
            label.pack(**pack)
        return label

    def _build(self) -> None:
        colors = theme.COLORS
        self.body = tk.Frame(self, bg=colors["surface"])
        self.body.pack(fill="both", expand=True, padx=10, pady=8)

        # Header row
        header = tk.Frame(self.body, bg=colors["surface"])
        header.pack(fill="x")
        self._label(header, text="CHANNEL DETAIL", font="eyebrow", fg="cyan_soft",
                    side="left")
        self.close_button = tk.Button(
            header,
            text="CLOSE ✕",
            font=self.fonts["eyebrow"],
            bg=colors["surface_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["text"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=2,
            command=self._handle_close,
        )
        self.close_button.pack(side="right")

        self._label(self.body, textvariable=self.title_var, font="subtitle",
                    fg="text", fill="x", pady=(6, 0))
        self._label(self.body, textvariable=self.subtitle_var, font="caption",
                    fg="text_muted", fill="x")
        self._divider()

        # --- +48V phantom --------------------------------------------------
        self._label(self.body, text="+48V PHANTOM POWER", font="eyebrow",
                    fg="warning", fill="x")
        status = tk.Frame(self.body, bg=colors["surface"])
        status.pack(fill="x", pady=(3, 0))
        self._status_cell(status, "CMD", self.phantom_cmd_var, "cyan_soft")
        self._status_cell(status, "OBS", self.phantom_obs_var, "purple_soft")
        tk.Label(
            status, textvariable=self.phantom_sync_var, font=self.fonts["caption"],
            fg=colors["warning"], bg=colors["surface_alt"], padx=5, pady=1,
        ).pack(side="right")

        self.phantom_button = tk.Button(
            self.body,
            text="+48V",
            font=self.fonts["eyebrow"],
            bg=colors["surface_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["warning"],
            activeforeground=colors["background"],
            disabledforeground=colors["text_muted"],
            bd=0,
            relief="flat",
            cursor="hand2",
            pady=5,
            command=self._on_phantom_button,
        )
        self.phantom_button.pack(fill="x", pady=(5, 0))
        self._label(self.body, textvariable=self.phantom_note_var, font="caption",
                    fg="text_muted", fill="x", pady=(2, 0))
        self._divider()

        # --- analog gain preview ------------------------------------------
        self._label(self.body, text="ANALOG GAIN · PREVIEW ONLY", font="eyebrow",
                    fg="warning", fill="x")
        self._gain_cmd_label = self._label(
            self.body, textvariable=self.gain_cmd_var, font="caption",
            fg="text_secondary", fill="x", pady=(3, 0),
        )

        self._gain_controls = tk.Frame(self.body, bg=colors["surface"])
        self.gain_slider = _GainPreviewSlider(
            self._gain_controls,
            variable=self.gain_preview_var,
            command=self._on_gain_preview,
            default=0,
        )
        self.gain_slider.pack(fill="x", pady=(2, 0))
        self._label(self._gain_controls, textvariable=self.gain_preview_text_var,
                    font="caption", fg="warning", fill="x")
        buttons = tk.Frame(self._gain_controls, bg=colors["surface"])
        buttons.pack(fill="x", pady=(4, 0))
        self.gain_cancel_btn = tk.Button(
            buttons, text="CANCEL PREVIEW", font=self.fonts["eyebrow"],
            bg=colors["surface_alt"], fg=colors["text_secondary"],
            activebackground=colors["surface_hover"], activeforeground=colors["text"],
            bd=0, relief="flat", cursor="hand2", padx=6, pady=3,
            command=self.cancel_gain_preview,
        )
        self.gain_cancel_btn.pack(side="left")
        self.gain_apply_btn = tk.Button(
            buttons, text="APPLY — GATED", font=self.fonts["eyebrow"],
            bg=colors["surface_alt"], fg=colors["text_muted"],
            disabledforeground=colors["text_muted"], bd=0, relief="flat",
            padx=6, pady=3, state="disabled",
        )
        self.gain_apply_btn.pack(side="right")
        self._label(self._gain_controls,
                    text="Hardware gain dispatch is blocked: the dB mapping is an "
                         "unverified approximation.",
                    font="caption", fg="text_muted", fill="x", pady=(3, 0)
                    ).configure(wraplength=280, justify="left")
        self._label(self.body, textvariable=self.gain_note_var, font="caption",
                    fg="text_muted", fill="x")
        self._divider()

        # --- footer ---------------------------------------------------------
        self._label(
            self.body,
            text="CMD = last software command · OBS = device input only · "
                 "HW APPLIED: UNKNOWN",
            font="caption", fg="text_muted", fill="x",
        ).configure(wraplength=290, justify="left")
        self.error_label = tk.Label(
            self.body, textvariable=self.error_var, font=self.fonts["caption"],
            fg=colors["danger"], bg=colors["surface"], anchor="w",
            wraplength=290, justify="left",
        )
        self.error_label.pack(fill="x", pady=(4, 0))
        self._wrap_labels.append(self.error_label)

    def _divider(self) -> None:
        tk.Frame(self.body, bg=theme.COLORS["border"], height=1).pack(fill="x", pady=6)

    def _status_cell(self, parent, name: str, variable: tk.StringVar, fg: str) -> None:
        colors = theme.COLORS
        cell = tk.Frame(parent, bg=colors["surface"])
        cell.pack(side="left", padx=(0, 10))
        tk.Label(cell, text=f"{name}:", font=self.fonts["status_key"],
                 fg=colors["text_muted"], bg=colors["surface"]).pack(side="left")
        tk.Label(cell, textvariable=variable, font=self.fonts["status_value"],
                 fg=colors[fg], bg=colors["surface"]).pack(side="left", padx=(3, 0))

    # -- target display -------------------------------------------------------

    def show_target(self, target: Optional[SelectionTarget]) -> None:
        """Display *target*. Selection itself never dispatches anything."""
        if target is None:
            self.clear()
            return
        # A pending +48V dialog is deliberately left alone here: it is bound to
        # the channel it was opened for and can never be redirected by a change
        # of selection. Closing the inspector (clear) is what cancels it.
        self.target = target
        self.error_var.set("")
        self._attach()

        if target.kind == "main":
            self.title_var.set("MAIN L/R")
            self.subtitle_var.set("Master output bus · separate from the 7 input strips")
            index = None
        else:
            index = target.index
            spec = LOGICAL_CHANNELS[index]
            self.title_var.set(f"CHANNEL {index:02d}")
            self.subtitle_var.set(f"{spec.name} · MIDI CH {spec.midi_channel}")

        self._configure_phantom(index)
        self._configure_gain(index)

    def clear(self) -> None:
        """Forget the target, cancel any pending dialog, release subscriptions."""
        self._dismiss_dialog()
        self.detach()
        self.target = None
        self.title_var.set("NO SELECTION")
        self.subtitle_var.set("")
        self.error_var.set("")

    # -- service subscription ---------------------------------------------------

    def _attach(self) -> None:
        if self._attached or self._service is None:
            return
        add = getattr(self._service, "add_listener", None)
        if callable(add):
            add(self._on_state_event)
            self._attached = True

    def detach(self) -> None:
        """Remove the state listener. Safe to call repeatedly."""
        if not self._attached:
            return
        self._attached = False
        remove = getattr(self._service, "remove_listener", None)
        if callable(remove):
            try:
                remove(self._on_state_event)
            except Exception:
                logger.exception("Could not remove channel-detail listener")

    def _on_state_event(self, param_id: str, value: Any) -> None:
        """Service callback; may run on the MIDI thread, so only schedule."""
        if not self._attached or self.target is None:
            return
        try:
            self.after_idle(self._refresh_if_attached)
        except (tk.TclError, RuntimeError):
            return

    def _refresh_if_attached(self) -> None:
        if not self._attached or self.target is None:
            return
        try:
            self._refresh_phantom()
            self._refresh_gain_command()
        except tk.TclError:
            return

    def _state(self, param_id: str):
        if self._service is None:
            return None
        try:
            return self._service.state_store.get_parameter(param_id)
        except Exception:
            return None

    # -- phantom --------------------------------------------------------------

    def _configure_phantom(self, index: Optional[int]) -> None:
        self.phantom_available = _valid_phantom_channel(index)
        if not self.phantom_available:
            self.phantom_cmd_var.set("—")
            self.phantom_obs_var.set("—")
            self.phantom_sync_var.set("UNSYNCED")
            self.phantom_note_var.set(NO_RELAY_NOTE)
            self.phantom_button.configure(
                text="+48V UNAVAILABLE", state="disabled",
                bg=theme.COLORS["surface_alt"], cursor="arrow",
            )
            return
        if self._service is None:
            self.phantom_cmd_var.set("—")
            self.phantom_obs_var.set("UNKNOWN")
            self.phantom_note_var.set(NO_SERVICE_NOTE)
            self.phantom_button.configure(
                text="+48V — NO COMMAND SERVICE", state="disabled",
                bg=theme.COLORS["surface_alt"], cursor="arrow",
            )
            return
        self.phantom_note_var.set(
            "ON asks for confirmation. Nothing is sent until you confirm."
        )
        self._refresh_phantom()

    def _commanded_phantom(self, channel_index: int) -> bool:
        state = self._state(f"ch{channel_index}.phantom")
        return bool(state.commanded_value) if state is not None else False

    def _refresh_phantom(self) -> None:
        target = self.target
        if target is None or target.kind != "input" or not self.phantom_available:
            return
        if self._service is None:
            return
        colors = theme.COLORS
        state = self._state(f"ch{target.index}.phantom")
        commanded = bool(state.commanded_value) if state is not None else False
        observed = state.observed_value if state is not None else None
        self.phantom_cmd_var.set("ON" if commanded else "OFF")
        self.phantom_obs_var.set(
            "UNKNOWN" if observed is None else ("ON" if observed else "OFF")
        )
        synced = (
            state is not None
            and getattr(getattr(state, "sync_status", None), "value", None) == "SYNCED"
        )
        # "SYNCED" is a forbidden hardware claim (ui.status.FORBIDDEN_CLAIMS); say
        # only what is known: the input echo currently equals the software command.
        self.phantom_sync_var.set("OBS = CMD" if synced else "UNSYNCED")
        if commanded:
            self.phantom_button.configure(
                text="+48V COMMANDED ON — TURN OFF", state="normal",
                bg=colors["warning"], fg=colors["background"], cursor="hand2",
            )
        else:
            self.phantom_button.configure(
                text="+48V COMMANDED OFF — REQUEST ON", state="normal",
                bg=colors["surface_alt"], fg=colors["text_secondary"], cursor="hand2",
            )

    def _on_phantom_button(self) -> None:
        target = self.target
        if target is None or target.kind != "input" or not self.phantom_available:
            return
        self.request_phantom(target.index, not self._commanded_phantom(target.index))

    def request_phantom(self, channel_index: int, enabled: bool) -> bool:
        """Request a +48V change for *channel_index* (explicit, never inferred).

        ON opens a confirmation dialog bound to *channel_index*; nothing is sent
        until the user confirms. OFF is sent immediately. Returns True when a
        dialog was opened or a command was accepted by the service.
        """
        self.error_var.set("")
        if not _valid_phantom_channel(channel_index):
            self.error_var.set(
                "+48V is available on MIC 1 and MIC 2 only — NOT SENT"
            )
            return False
        if self._service is None:
            self.error_var.set(NO_SERVICE_NOTE)
            return False
        if self._phantom_dialog is not None or self._phantom_busy:
            return False
        if enabled:
            return self._open_phantom_dialog(channel_index)
        return self._send_phantom_off(channel_index)

    def _open_phantom_dialog(self, channel_index: int) -> bool:
        # Supersede any stale pending request before minting a new token.
        if self._phantom_token is not None:
            PhantomPowerSafetyGate.revoke_token(self._phantom_token)
        token = PhantomPowerSafetyGate.issue_token(channel_index)
        self._phantom_token = token
        try:
            dialog = PhantomPowerConfirmationDialog(
                self,
                channel_index,
                on_confirm=lambda _tok: self._on_phantom_confirmed(channel_index, token),
                on_cancel=lambda: self._on_phantom_cancelled(token),
                confirmation_token=token,
            )
        except Exception as error:
            PhantomPowerSafetyGate.revoke_token(token)
            self._phantom_token = None
            self.error_var.set(f"+48V NOT SENT — {error}")
            return False
        self._phantom_dialog = dialog
        return True

    def _on_phantom_cancelled(self, token: object) -> None:
        if token is self._phantom_token:
            PhantomPowerSafetyGate.revoke_token(token)
            self._phantom_dialog = None
            self._phantom_token = None
        self._refresh_phantom()

    def _on_phantom_confirmed(self, channel_index: int, token: object) -> None:
        # A stale or repeated confirmation must never dispatch.
        if token is not self._phantom_token or self._phantom_busy:
            return
        self._phantom_dialog = None
        self._phantom_token = None
        self._phantom_busy = True
        try:
            PhantomPowerSafetyGate.confirm_and_dispatch(
                self._service, channel_index, token
            )
        except Exception as error:
            self._phantom_failed(channel_index, error)
        else:
            self._phantom_done(channel_index)
        finally:
            self._phantom_busy = False

    def _send_phantom_off(self, channel_index: int) -> bool:
        self._phantom_busy = True
        try:
            PhantomPowerSafetyGate.disable_and_dispatch(self._service, channel_index)
        except Exception as error:
            self._phantom_failed(channel_index, error)
            return False
        else:
            self._phantom_done(channel_index)
            return True
        finally:
            self._phantom_busy = False

    def _phantom_done(self, channel_index: int) -> None:
        self.error_var.set("")
        self._refresh_phantom()
        self._notify_phantom_changed(channel_index)

    def _phantom_failed(self, channel_index: int, error: Exception) -> None:
        logger.warning("+48V command for channel %s failed: %s", channel_index, error)
        # Present the last accepted commanded value, never the rejected request.
        self.error_var.set(f"+48V NOT SENT — {error}")
        self._refresh_phantom()
        self._notify_phantom_changed(channel_index)

    def _notify_phantom_changed(self, channel_index: int) -> None:
        if self._on_phantom_changed is not None:
            try:
                self._on_phantom_changed(
                    channel_index, self._commanded_phantom(channel_index)
                )
            except Exception:
                logger.exception("Phantom presentation callback failed")

    def _dismiss_dialog(self) -> None:
        dialog = self._phantom_dialog
        if dialog is None:
            return
        try:
            if dialog.winfo_exists():
                dialog._cancel()
        except tk.TclError:
            pass
        finally:
            if self._phantom_token is not None:
                PhantomPowerSafetyGate.revoke_token(self._phantom_token)
            self._phantom_dialog = None
            self._phantom_token = None

    # -- analog gain preview (never dispatches) -------------------------------

    def _configure_gain(self, index: Optional[int]) -> None:
        self.gain_available = index in AnalogGainSafetyGate.ALLOWED_CHANNELS
        if not self.gain_available:
            self.gain_gate = None
            self._gain_controls.pack_forget()
            self.gain_cmd_var.set("")
            self.gain_note_var.set(NO_PREAMP_NOTE)
            return
        self.gain_note_var.set("")
        raw = self._commanded_gain_raw(index)
        self._gain_baseline = raw if raw is not None else 0
        self.gain_gate = AnalogGainSafetyGate(
            index, initial_gain_db=gain_midi_to_db(self._gain_baseline)
        )
        self.gain_slider.default = self._gain_baseline
        self.gain_preview_var.set(self._gain_baseline)
        self._refresh_gain_command()
        self._update_gain_text(self._gain_baseline)
        self._gain_controls.pack(fill="x", after=self._gain_cmd_label, pady=(2, 0))

    def _commanded_gain_raw(self, index: int) -> Optional[int]:
        state = self._state(f"ch{index}.gain")
        raw = getattr(state, "commanded_raw_midi", None) if state is not None else None
        return raw if isinstance(raw, int) and not isinstance(raw, bool) else None

    def _refresh_gain_command(self) -> None:
        if not self.gain_available or self.target is None:
            return
        raw = self._commanded_gain_raw(self.target.index)
        if raw is None:
            self.gain_cmd_var.set("CMD: NOT COMMANDED")
        else:
            self.gain_cmd_var.set(f"CMD: RAW {raw}/127 · UNVERIFIED")

    def _update_gain_text(self, raw: int) -> None:
        db = gain_midi_to_db(raw)
        self.gain_preview_text_var.set(
            f"PREVIEW RAW {raw}/127 · Approx. {db:+.1f} dB · UNVERIFIED — NOT SENT"
        )

    def _on_gain_preview(self, value: str) -> None:
        """Slider interaction: stage a preview only. Never touches the service."""
        if self.gain_gate is None:
            return
        raw = max(0, min(127, int(value)))
        self.gain_gate.stage_preview(gain_midi_to_db(raw))
        self._update_gain_text(raw)

    def cancel_gain_preview(self) -> None:
        """Discard the staged preview and restore the original value."""
        if self.gain_gate is None:
            return
        self.gain_gate.cancel_staged()
        self.gain_preview_var.set(self._gain_baseline)
        self._update_gain_text(self._gain_baseline)

    # -- lifecycle ------------------------------------------------------------

    def _handle_close(self) -> None:
        if self._on_close is not None:
            self._on_close()
        else:
            self.clear()

    def destroy(self) -> None:
        try:
            self._dismiss_dialog()
        except Exception:
            logger.exception("Could not dismiss +48V dialog on destroy")
        self.detach()
        super().destroy()
