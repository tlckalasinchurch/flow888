"""7-Strip Mixer Console Component for FLOW 8 Cyber Neon Workstation.

Renders exactly 7 logical channel strips plus 1 Main L/R master strip
according to the Behringer FLOW 8 Hardware Domain Model.
"""

from __future__ import annotations

import logging
import queue
import sys
import time
import tkinter as tk
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.service import RECONCILE_EVENT, STATE_CHANGED_EVENT
from flow8.parameter_mapping import fader_midi_to_db, pan_midi_to_percent
from flow8.ui import theme
from flow8.ui.components.controls import (
    HorizontalSlider,
    ProvenanceBadge,
    RotaryDial,
    VerticalFader,
)
from flow8.ui.components.command_log import CommandLogPanel
from flow8.ui.components.scene_bar import SceneBar, slot_name
from flow8.ui.components.channel_detail import (
    MAIN_TARGET,
    ChannelDetailPanel,
    SelectionTarget,
)

# Inspector sizing: ~320px when there is room, shrinking (never below the
# minimum) so each strip keeps a usable slot for its fader and controls.
INSPECTOR_MAX_WIDTH = 320
INSPECTOR_MIN_WIDTH = 248
MIN_STRIP_SLOT = 104


class ValueProvenance(str, Enum):
    """What the UI is entitled to claim about a displayed control value."""

    UNSYNCED_DEFAULT = "UNSYNCED_DEFAULT"
    COMMANDED = "COMMANDED"
    OBSERVED = "OBSERVED"
    DISPATCH_FAILED = "DISPATCH_FAILED"



def format_db(raw_val: int) -> str:
    """Show an explicitly approximate dB conversion and its raw MIDI value."""
    if raw_val <= 0:
        db_text = "-inf"
    else:
        db = fader_midi_to_db(raw_val)
        db_text = f"+{db:.1f}" if db >= 0 else f"{db:.1f}"
    return f"Approx. {db_text} dB · MIDI {raw_val}/127"


def format_pan(raw_val: int) -> str:
    """Format raw 0-127 MIDI value as Pan/Balance string."""
    pct = pan_midi_to_percent(raw_val)
    if pct == 0.0:
        return "C"
    elif pct < 0:
        return f"L{abs(int(pct))}"
    else:
        return f"R{int(pct)}"


class ChannelStripWidget(tk.Frame):
    """Single channel strip widget inside the mixer console."""

    def __init__(
        self,
        master: tk.Misc,
        channel_index: int,
        title: str,
        subtitle: str,
        kind_badge: str,
        pan_label: str,
        has_phantom: bool,
        fonts: dict,
        service: Any = None,
        is_master: bool = False,
        on_select: Optional[Callable[["SelectionTarget"], None]] = None,
        on_phantom_request: Optional[Callable[[int, bool], None]] = None,
        on_feedback: Any = None,
    ) -> None:
        colors = theme.COLORS
        super().__init__(
            master,
            bg=colors["surface"],
            highlightbackground=colors["cyan"] if is_master else colors["border"],
            highlightthickness=1,
            bd=0,
            padx=4,
            pady=4,
        )
        self.channel_index = channel_index
        self.is_master = is_master
        self.active_bus = "main"
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self.has_phantom = has_phantom
        self.is_selected = False
        self._on_select = on_select
        self._on_phantom_request = on_phantom_request
        self._is_updating = False
        self.fader_provenance = ValueProvenance.UNSYNCED_DEFAULT
        self.pan_provenance = ValueProvenance.UNSYNCED_DEFAULT
        self.mute_provenance = ValueProvenance.UNSYNCED_DEFAULT

        # State tracking
        self.fader_val = tk.IntVar(value=101 if is_master else 0)  # default unity for main, 0 for inputs
        self.pan_val = tk.IntVar(value=64)  # center
        self._last_fader_val = self.fader_val.get()
        self._last_pan_val = self.pan_val.get()
        self._pending_fader: Optional[int] = None
        self._pending_pan: Optional[int] = None
        self._fader_after_id: Optional[str] = None
        self._pan_after_id: Optional[str] = None
        self.is_muted = tk.BooleanVar(value=False)
        self.is_phantom = tk.BooleanVar(value=False)

        initial_db = format_db(self.fader_val.get())
        db_text, midi_text = initial_db.split(" · ", 1)
        self.db_label_var = tk.StringVar(value=db_text)
        # Nothing commanded or observed yet: say so on the (short) MIDI line. Kept to
        # 20 characters ("MIDI 101/127 DEFAULT"): longer text is clipped in a strip.
        self.midi_label_var = tk.StringVar(value=f"{midi_text} DEFAULT")
        self.pan_label_var = tk.StringVar(value=format_pan(self.pan_val.get()))

        self._build(title, subtitle, kind_badge, pan_label)

    def _bus_accent_color(self, bus_id: Optional[str] = None) -> str:
        b_key = (bus_id or self.active_bus or "main").lower()
        if b_key == "main" and not self.is_master and self.channel_index == 7:
            return theme.BUS_COLORS["usb"]
        return theme.BUS_COLORS.get(b_key, theme.BUS_COLORS["main"])

    def _fader_param_id(self) -> str:
        if self.is_master:
            return "main.fader" if self.active_bus == "main" else f"{self.active_bus}.fader"
        if self.active_bus == "main":
            return f"ch{self.channel_index}.fader"
        return f"ch{self.channel_index}.send_{self.active_bus}"

    def _default_fader_raw(self) -> int:
        return 101 if (self.is_master and self.active_bus == "main") else 0

    def _build(self, title: str, subtitle: str, kind_badge: str, pan_label: str) -> None:
        colors = theme.COLORS
        bus_accent = self._bus_accent_color("main")

        # 1. Strip Header (the only region that selects the strip)
        hdr = tk.Frame(self, bg=colors["surface"])
        hdr.pack(fill="x", pady=(0, 4))
        self.header_frame = hdr

        # Top Bus / Identity Color Bar (Sends on Fader visual cue)
        self.header_accent_bar = tk.Frame(hdr, bg=bus_accent, height=3)
        self.header_accent_bar.pack(fill="x", pady=(0, 3))

        # Channel Number & Type Badge
        top_row = tk.Frame(hdr, bg=colors["surface"])
        top_row.pack(fill="x")

        ch_num_text = "MAIN" if self.is_master else f"{self.channel_index:02d}"
        # Bolder, larger channel badge for hierarchy
        ch_font = self.fonts["eyebrow"]
        ch_padx = 1 if self.is_master else 3
        self.num_badge_label = tk.Label(
            top_row,
            text=ch_num_text,
            font=ch_font,
            fg=bus_accent if (self.is_master or self.channel_index == 7) else colors["cyan_soft"],
            bg=colors["surface"],
            padx=ch_padx,
            pady=1,
        )
        self.num_badge_label.pack(side="left")

        self.kind_badge_label = tk.Label(
            top_row,
            text=kind_badge,
            font=self.fonts["caption"],
            fg=bus_accent if self.channel_index == 7 else (colors["purple_soft"] if not self.is_master else colors["lime"]),
            bg=colors["surface_alt"],
            padx=1 if self.is_master else 3,
            pady=1,
        )
        self.kind_badge_label.pack(side="right")

        # Name
        self.title_label = tk.Label(
            hdr,
            text=title,
            font=self.fonts["subtitle"] if self.is_master else self.fonts["nav_active"],
            fg=colors["text"],
            bg=colors["surface"],
            anchor="w",
        )
        self.title_label.pack(fill="x", pady=(2, 0))

        self.subtitle_label = tk.Label(
            hdr,
            text=subtitle,
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["surface"],
            anchor="w",
            wraplength=76,
            justify="left",
        )
        self.subtitle_label.pack(fill="x")

        self._bind_header_selection(hdr)

        # Divider
        tk.Frame(self, bg=colors["border"], height=1).pack(fill="x", pady=3)

        # 2. Phantom Power (if supported, e.g. Ch 1 & 2)
        if self.has_phantom:
            self.phantom_btn = tk.Button(
                self,
                text="+48V",
                font=self.fonts["caption"],
                bg=colors["surface_alt"],
                fg=colors["text_muted"],
                activebackground=colors["warning"],
                activeforeground=colors["background"],
                bd=0,
                relief="flat",
                cursor="hand2",
                pady=2,
                command=self._toggle_phantom,
            )
            self.phantom_btn.pack(fill="x", pady=(0, 4))

        # 3. Pan / Balance Control
        pan_frame = tk.Frame(self, bg=colors["surface"])
        pan_frame.pack(fill="x", pady=(0, 4))

        pan_top = tk.Frame(pan_frame, bg=colors["surface"])
        pan_top.pack(fill="x")
        tk.Label(
            pan_top,
            text=pan_label,
            font=self.fonts["caption"],
            fg=colors["text_secondary"],
            bg=colors["surface"],
        ).pack(side="left")

        tk.Label(
            pan_top,
            textvariable=self.pan_label_var,
            font=self.fonts["status_key"],
            fg=colors["cyan_soft"],
            bg=colors["surface"],
        ).pack(side="right")

        self.pan_scale = HorizontalSlider(
            pan_frame,
            variable=self.pan_val,
            command=self._on_pan_drag,
            default=64,
        )
        self.pan_scale.pack(fill="x", pady=(2, 0))
        self.pan_scale.bind("<ButtonPress-1>", self._begin_gesture, add="+")
        self.pan_scale.bind("<ButtonRelease-1>", self._on_pan_release, add="+")

        # 4. Mute Button (Inputs only)
        if not self.is_master:
            self.mute_btn = tk.Button(
                self,
                text="MUTE",
                font=self.fonts["eyebrow"],
                bg=colors["surface_alt"],
                fg=colors["text_secondary"],
                activebackground=colors["danger"],
                activeforeground=colors["text"],
                bd=0,
                relief="flat",
                cursor="hand2",
                pady=4,
                command=self._toggle_mute,
            )
            self.mute_btn.pack(fill="x", pady=(3, 4))
        else:
            # Spacer for alignment
            tk.Frame(self, bg=colors["surface"], height=24).pack(fill="x", pady=(3, 4))

        # 5. Fader readout: approximate dB and raw MIDI are separate visual levels.
        readout = tk.Frame(
            self,
            bg=colors["background_alt"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        readout.pack(fill="x", pady=(0, 4))

        db_label = tk.Label(
            readout,
            textvariable=self.db_label_var,
            font=self.fonts["caption"],
            fg=colors["cyan"] if self.is_master else colors["text"],
            bg=colors["background_alt"],
            justify="center",
            pady=2,
        )
        db_label.pack(fill="x")

        midi_label = tk.Label(
            readout,
            textvariable=self.midi_label_var,
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["background_alt"],
            justify="center",
        )
        midi_label.pack(fill="x", pady=(0, 2))

        # Wrap to the strip width instead of clipping when the inspector narrows it.
        db_label.configure(wraplength=70)
        midi_label.configure(wraplength=70)

        # 6. Vertical Volume Fader
        fader_container = tk.Frame(self, bg=colors["surface"])
        fader_container.pack(fill="both", expand=True, pady=(0, 4))

        self.fader_scale = VerticalFader(
            fader_container,
            variable=self.fader_val,
            command=self._on_fader_drag,
            default=101,
            accent=bus_accent,
        )
        self.fader_scale.pack(fill="both", expand=True)
        self.fader_scale.bind("<ButtonPress-1>", self._begin_gesture, add="+")
        self.fader_scale.bind("<ButtonRelease-1>", self._on_fader_release, add="+")

        # 7. Strip Footer Number
        self.footer_label = tk.Label(
            self,
            text=ch_num_text,
            font=self.fonts["eyebrow"],
            fg=colors["text_muted"],
            bg=colors["surface"],
        )
        self.footer_label.pack(side="bottom", pady=(2, 0))

    # -- User Interactions --------------------------------------------------

    def _on_fader_drag(self, val_str: str) -> None:
        if self._is_updating:
            return
        val = int(val_str)
        self._pending_fader = val
        self._set_fader_labels(val)
        if self._fader_after_id is None:
            self._fader_after_id = self.after(30, self._flush_fader)

    def _set_fader_labels(self, raw: int) -> None:
        db_text, midi_text = format_db(raw).split(" · ", 1)
        self.db_label_var.set(db_text)
        self.midi_label_var.set(midi_text)

    def _begin_gesture(self, _event: Optional[tk.Event] = None) -> None:
        """Mouse down on a fader/pan: everything until release is one undo step."""
        begin = getattr(self.service, "begin_batch", None)
        if callable(begin):
            try:
                begin()
            except Exception:
                logging.getLogger(__name__).exception("Could not start undo batch")

    def _end_gesture(self) -> None:
        end = getattr(self.service, "end_batch", None)
        if callable(end):
            try:
                end()
            except Exception:
                logging.getLogger(__name__).exception("Could not close undo batch")

    def _on_fader_release(self, _event: Optional[tk.Event]) -> None:
        if self._fader_after_id is not None:
            self.after_cancel(self._fader_after_id)
            self._fader_after_id = None
        self._flush_fader()
        self._end_gesture()

    def _flush_fader(self) -> None:
        self._fader_after_id = None
        if self._pending_fader is None:
            return
        val = self._pending_fader
        self._pending_fader = None
        previous = self._last_fader_val
        if not self.service:
            return
        try:
            if self.active_bus == "main":
                self.service.set_fader(self.channel_index, val)
                label = "MAIN: FADER COMMANDED" if self.is_master else f"CH {self.channel_index}: FADER COMMANDED"
            elif self.is_master:
                self.service.set_bus_fader(self.active_bus, val)
                label = f"{self.active_bus.upper()}: MASTER FADER COMMANDED"
            else:
                self.service.set_send(self.channel_index, self.active_bus, val, unit="raw")
                label = f"CH {self.channel_index} -> {self.active_bus.upper()}: SEND COMMANDED"
            self._last_fader_val = val
            self.fader_provenance = ValueProvenance.COMMANDED
            if hasattr(self, "fader_badge"):
                self.fader_badge.set_provenance(self.fader_provenance)
            self._feedback(label)
        except Exception:
            logging.getLogger(__name__).exception("Fader command failed")
            self.fader_val.set(previous)
            self._set_fader_labels(previous)
            self.fader_provenance = ValueProvenance.DISPATCH_FAILED
            if hasattr(self, "fader_badge"):
                self.fader_badge.set_provenance(self.fader_provenance)
            self._feedback(f"CH {self.channel_index}: FADER FAILED")

    def _on_pan_drag(self, val_str: str) -> None:
        if self._is_updating:
            return
        val = int(val_str)
        self._pending_pan = val
        self.pan_label_var.set(format_pan(val))
        if self._pan_after_id is None:
            self._pan_after_id = self.after(30, self._flush_pan)

    def _on_pan_release(self, _event: Optional[tk.Event]) -> None:
        if self._pan_after_id is not None:
            self.after_cancel(self._pan_after_id)
            self._pan_after_id = None
        self._flush_pan()
        self._end_gesture()

    def _flush_pan(self) -> None:
        self._pan_after_id = None
        if self._pending_pan is None:
            return
        val = self._pending_pan
        self._pending_pan = None
        previous = self._last_pan_val
        if not self.service:
            return
        try:
            self.service.set_pan(self.channel_index, val)
            self._last_pan_val = val
            self.pan_provenance = ValueProvenance.COMMANDED
            self._feedback(f"CH {self.channel_index}: PAN COMMANDED")
        except Exception:
            logging.getLogger(__name__).exception("Pan/balance command failed")
            self.pan_val.set(previous)
            self.pan_label_var.set(format_pan(previous))
            self.pan_provenance = ValueProvenance.DISPATCH_FAILED
            self._feedback(f"CH {self.channel_index}: PAN FAILED")

    def _toggle_mute(self) -> None:
        previous = self.is_muted.get()
        new_mute = not self.is_muted.get()
        self.is_muted.set(new_mute)
        self._update_mute_ui(new_mute)
        if self.service:
            try:
                self.service.set_mute(self.channel_index, new_mute)
                self.mute_provenance = ValueProvenance.COMMANDED
                self._feedback(f"CH {self.channel_index}: MUTE COMMANDED")
            except Exception:
                logging.getLogger(__name__).exception("Mute command failed")
                self.is_muted.set(previous)
                self._update_mute_ui(previous)
                self.mute_provenance = ValueProvenance.DISPATCH_FAILED
                self._feedback(f"CH {self.channel_index}: MUTE FAILED")

    def _feedback(self, message: str) -> None:
        if self.on_feedback:
            self.on_feedback(message)

    def _update_mute_ui(self, muted: bool) -> None:
        colors = theme.COLORS
        if hasattr(self, "mute_btn"):
            if muted:
                self.mute_btn.configure(
                    bg=colors["danger"],
                    fg=colors["text"],
                    text="MUTED",
                )
            else:
                self.mute_btn.configure(
                    bg=colors["surface_alt"],
                    fg=colors["text_secondary"],
                    text="MUTE",
                )

    def _toggle_phantom(self) -> None:
        """Route a +48V request to the confirmation workflow.

        The strip never dispatches phantom power itself: turning it ON must pass
        the explicit confirmation dialog, which is owned by the inspector.
        """
        if self._on_phantom_request is None:
            return
        self._on_phantom_request(self.channel_index, not self.is_phantom.get())

    def sync_phantom(self, enabled: bool) -> None:
        """Show the last accepted commanded +48V state (not a hardware reading)."""
        self.is_phantom.set(bool(enabled))
        if not hasattr(self, "phantom_btn"):
            return
        colors = theme.COLORS
        self.phantom_btn.configure(
            bg=colors["warning"] if enabled else colors["surface_alt"],
            fg=colors["background"] if enabled else colors["text_muted"],
        )

    # -- Selection ----------------------------------------------------------

    @property
    def target(self) -> SelectionTarget:
        """Selection identity: Main L/R is its own target, never strip 8."""
        return MAIN_TARGET if self.is_master else SelectionTarget.input(self.channel_index)

    def _bind_header_selection(self, widget: tk.Misc) -> None:
        """Only the header (badge, name, subtitle) selects; controls never do."""
        widget.bind("<Button-1>", self._handle_header_click, add="+")
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._bind_header_selection(child)

    def _handle_header_click(self, _event: tk.Event) -> None:
        if self._on_select is not None:
            self._on_select(self.target)

    def set_selected(self, selected: bool) -> None:
        colors = theme.COLORS
        self.is_selected = bool(selected)
        if self.is_selected:
            self.configure(highlightbackground=colors["cyan"], highlightthickness=2)
        else:
            self.configure(
                highlightbackground=self._bus_accent_color() if self.is_master else colors["border"],
                highlightthickness=1,
            )

    def set_active_bus(self, bus_id: str) -> None:
        """Switch this strip's Sends-on-Fader layer and dynamically retint its header & fader cap."""
        b_key = str(bus_id or "main").lower()
        if b_key not in theme.BUS_SPECS:
            return
        self.active_bus = b_key
        accent = self._bus_accent_color(b_key)
        self.header_accent_bar.configure(bg=accent)
        self.fader_scale.set_accent(accent)

        if self.is_master:
            spec = theme.BUS_SPECS[b_key]
            self.num_badge_label.configure(text=spec["badge"], fg=accent)
            self.title_label.configure(text=spec["title"])
            self.subtitle_label.configure(text=spec["subtitle"])
            self.footer_label.configure(text=spec["badge"])
            if not self.is_selected:
                self.configure(highlightbackground=accent)
        else:
            self.num_badge_label.configure(
                fg=accent if (b_key != "main" or self.channel_index == 7) else theme.COLORS["cyan_soft"]
            )

        self._load_active_bus_fader_state()

    def _load_active_bus_fader_state(self) -> None:
        """Load the current fader/send level for the active bus without dispatching."""
        default_raw = self._default_fader_raw()
        state = None
        if self.service is not None:
            try:
                state = self.service.state_store.get_parameter(self._fader_param_id())
            except Exception:
                state = None
        self._is_updating = True
        try:
            raw = None
            prov = ValueProvenance.UNSYNCED_DEFAULT
            if state is not None:
                if state.commanded_raw_midi is not None:
                    raw = int(state.commanded_raw_midi)
                    prov = ValueProvenance.COMMANDED
                elif getattr(state, "observed_raw_midi", None) is not None:
                    raw = int(state.observed_raw_midi)
                    prov = ValueProvenance.OBSERVED
            if raw is None:
                raw = default_raw
                db_text, midi_text = format_db(raw).split(" · ", 1)
                self.db_label_var.set(db_text)
                self.midi_label_var.set(f"{midi_text} DEFAULT")
            else:
                self._set_fader_labels(raw)
            self.fader_val.set(raw)
            self._last_fader_val = raw
            self.fader_provenance = prov
            if hasattr(self, "fader_badge"):
                self.fader_badge.set_provenance(self.fader_provenance)
        finally:
            self._is_updating = False

    def _restore_commanded_value(self, parameter: str) -> None:
        """Restore the last accepted software command after a failed dispatch."""
        if self.service is None:
            return
        target = "main" if self.is_master else f"ch{self.channel_index}"
        if parameter == "fader":
            param_id = self._fader_param_id()
        elif self.is_master and parameter == "pan":
            param_id = "main.balance"
        else:
            param_id = f"{target}.{parameter}"
        try:
            state = self.service.state_store.get_parameter(param_id)
        except Exception:
            return
        if state is None:
            return

        self._is_updating = True
        try:
            if parameter in ("fader", "pan"):
                raw = state.commanded_raw_midi
                if raw is None:
                    raw = state.raw_midi_value
                if not isinstance(raw, int):
                    return
                commanded = state.commanded_raw_midi is not None
                if parameter == "fader":
                    self.fader_val.set(raw)
                    self._set_fader_labels(raw)
                    self._last_fader_val = raw
                    if commanded:
                        self.fader_provenance = ValueProvenance.COMMANDED
                    if hasattr(self, "fader_badge"):
                        self.fader_badge.set_provenance(self.fader_provenance)
                else:
                    self.pan_val.set(raw)
                    self.pan_label_var.set(format_pan(raw))
                    self._last_pan_val = raw
                    if commanded:
                        self.pan_provenance = ValueProvenance.COMMANDED
            elif parameter == "mute":
                self.is_muted.set(bool(state.commanded_value))
                self._update_mute_ui(bool(state.commanded_value))
                if state.commanded_raw_midi is not None:
                    self.mute_provenance = ValueProvenance.COMMANDED
            elif parameter == "phantom":
                self.sync_phantom(bool(state.commanded_value))
        finally:
            self._is_updating = False

    def refresh_commanded(self) -> None:
        """Show the last accepted software command (after undo/redo).

        Only parameters that were actually commanded are touched; an app default
        is never repainted as if it were a command. Never dispatches.
        """
        if self.service is None:
            return
        target = "main" if self.is_master else f"ch{self.channel_index}"
        for parameter in ("fader", "pan") if self.is_master else ("fader", "pan", "mute"):
            if parameter == "fader":
                param_id = self._fader_param_id()
            elif self.is_master and parameter == "pan":
                param_id = "main.balance"
            else:
                param_id = f"{target}.{parameter}"
            try:
                state = self.service.state_store.get_parameter(param_id)
            except Exception:
                continue
            if state is not None and state.commanded_raw_midi is not None:
                self._restore_commanded_value(parameter)

    # -- External Sync Updates (from Hardware MIDI) ------------------------

    def sync_fader(self, raw_val: int) -> None:
        self._is_updating = True
        try:
            self.fader_val.set(raw_val)
            self._set_fader_labels(raw_val)
            self._last_fader_val = raw_val
            self.fader_provenance = ValueProvenance.OBSERVED
            if hasattr(self, "fader_badge"):
                self.fader_badge.set_provenance(self.fader_provenance)
        finally:
            self._is_updating = False

    def sync_pan(self, raw_val: int) -> None:
        self._is_updating = True
        try:
            self.pan_val.set(raw_val)
            self.pan_label_var.set(format_pan(raw_val))
            self._last_pan_val = raw_val
            self.pan_provenance = ValueProvenance.OBSERVED
        finally:
            self._is_updating = False

    def sync_mute(self, is_muted: bool) -> None:
        self._is_updating = True
        try:
            self.is_muted.set(is_muted)
            self._update_mute_ui(is_muted)
            self.mute_provenance = ValueProvenance.OBSERVED
        finally:
            self._is_updating = False

    def reset_unsynced(self) -> None:
        """Show app defaults as UNSYNCED after a connect/disconnect; never dispatches.

        Previous commanded or observed values belong to a past hardware session and
        must not stay on screen as if they were current.
        """
        self._is_updating = True
        try:
            fader = self._default_fader_raw()
            self.fader_val.set(fader)
            self._last_fader_val = fader
            db_text, midi_text = format_db(fader).split(" · ", 1)
            self.db_label_var.set(db_text)
            self.midi_label_var.set(f"{midi_text} DEFAULT")
            self.pan_val.set(64)
            self._last_pan_val = 64
            self.pan_label_var.set(format_pan(64))
            self.is_muted.set(False)
            self._update_mute_ui(False)
            if self.has_phantom:
                self.sync_phantom(False)
            self.fader_provenance = ValueProvenance.UNSYNCED_DEFAULT
            self.pan_provenance = ValueProvenance.UNSYNCED_DEFAULT
            self.mute_provenance = ValueProvenance.UNSYNCED_DEFAULT
            if hasattr(self, "fader_badge"):
                self.fader_badge.set_provenance(self.fader_provenance)
        finally:
            self._is_updating = False

    def destroy(self) -> None:
        for timer_id in (self._fader_after_id, self._pan_after_id):
            if timer_id is not None:
                try:
                    self.after_cancel(timer_id)
                except tk.TclError:
                    pass
        super().destroy()


class BusMasterStripWidget(tk.Frame):
    """Master output/FX bus strip (MON 1, MON 2, FX 1, FX 2)."""

    def __init__(
        self,
        master: tk.Misc,
        bus_id: str,
        title: str,
        subtitle: str,
        accent_key: str,
        fonts: dict,
        service: Any = None,
        on_feedback: Any = None,
    ) -> None:
        colors = theme.COLORS
        super().__init__(
            master,
            bg=colors["surface"],
            highlightbackground=colors[accent_key],
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=10,
        )
        self.bus_id = bus_id
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self._is_updating = False
        self.fader_val = tk.IntVar(value=0)
        self._last_fader_val = 0
        self._pending_fader: Optional[int] = None
        self._fader_after_id: Optional[str] = None
        self.fader_provenance = ValueProvenance.UNSYNCED_DEFAULT

        db_text, midi_text = format_db(0).split(" · ", 1)
        self.db_label_var = tk.StringVar(value=db_text)
        self.midi_label_var = tk.StringVar(value=f"{midi_text} DEFAULT")

        hdr = tk.Frame(self, bg=colors["surface"])
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(
            hdr, text=title, font=self.fonts["subtitle"],
            fg=colors[accent_key], bg=colors["surface"], anchor="w",
        ).pack(side="left")
        self.badge = ProvenanceBadge(hdr, font=self.fonts["caption"], provenance="UNSYNCED")
        self.badge.pack(side="right")

        tk.Label(
            self, text=subtitle, font=self.fonts["caption"],
            fg=colors["text_muted"], bg=colors["surface"], anchor="w",
        ).pack(fill="x", pady=(0, 6))

        readout = tk.Frame(
            self, bg=colors["background_alt"],
            highlightbackground=colors["border"], highlightthickness=1,
        )
        readout.pack(fill="x", pady=(0, 6))
        tk.Label(
            readout, textvariable=self.db_label_var, font=self.fonts["caption"],
            fg=colors["text"], bg=colors["background_alt"], pady=2,
        ).pack(fill="x")
        tk.Label(
            readout, textvariable=self.midi_label_var, font=self.fonts["caption"],
            fg=colors["text_muted"], bg=colors["background_alt"], pady=2,
        ).pack(fill="x")

        self.fader_scale = VerticalFader(
            self,
            variable=self.fader_val,
            command=self._on_fader_drag,
            default=101,
            accent=colors[accent_key],
        )
        self.fader_scale.pack(fill="both", expand=True)
        self.fader_scale.bind("<ButtonPress-1>", self._begin_gesture, add="+")
        self.fader_scale.bind("<ButtonRelease-1>", self._on_fader_release, add="+")

    def _begin_gesture(self, _event: Optional[tk.Event] = None) -> None:
        begin = getattr(self.service, "begin_batch", None)
        if callable(begin):
            try:
                begin()
            except Exception:
                pass

    def _end_gesture(self) -> None:
        end = getattr(self.service, "end_batch", None)
        if callable(end):
            try:
                end()
            except Exception:
                pass

    def _set_labels(self, raw: int) -> None:
        db_text, midi_text = format_db(raw).split(" · ", 1)
        self.db_label_var.set(db_text)
        self.midi_label_var.set(midi_text)

    def _on_fader_drag(self, val_str: str) -> None:
        if self._is_updating:
            return
        val = int(val_str)
        self._pending_fader = val
        self._set_labels(val)
        if self._fader_after_id is None:
            self._fader_after_id = self.after(30, self._flush_fader)

    def _on_fader_release(self, _event: Optional[tk.Event]) -> None:
        if self._fader_after_id is not None:
            self.after_cancel(self._fader_after_id)
            self._fader_after_id = None
        self._flush_fader()
        self._end_gesture()

    def _flush_fader(self) -> None:
        self._fader_after_id = None
        if self._pending_fader is None:
            return
        val = self._pending_fader
        self._pending_fader = None
        previous = self._last_fader_val
        if not self.service:
            return
        try:
            self.service.set_bus_fader(self.bus_id, val)
            self._last_fader_val = val
            self.fader_provenance = ValueProvenance.COMMANDED
            self.badge.set_provenance(self.fader_provenance)
            if self.on_feedback:
                self.on_feedback(f"{self.bus_id.upper()}: MASTER FADER COMMANDED")
        except Exception:
            self.fader_val.set(previous)
            self._set_labels(previous)
            self.fader_provenance = ValueProvenance.DISPATCH_FAILED
            self.badge.set_provenance(self.fader_provenance)

    def sync_fader(self, raw_val: int) -> None:
        self._is_updating = True
        try:
            self.fader_val.set(raw_val)
            self._set_labels(raw_val)
            self._last_fader_val = raw_val
            self.fader_provenance = ValueProvenance.OBSERVED
            self.badge.set_provenance(self.fader_provenance)
        finally:
            self._is_updating = False

    def refresh_commanded(self) -> None:
        if self.service is None:
            return
        try:
            state = self.service.state_store.get_parameter(f"{self.bus_id}.fader")
        except Exception:
            return
        if state is not None and state.commanded_raw_midi is not None:
            raw = int(state.commanded_raw_midi)
            self._is_updating = True
            try:
                self.fader_val.set(raw)
                self._set_labels(raw)
                self._last_fader_val = raw
                self.fader_provenance = ValueProvenance.COMMANDED
                self.badge.set_provenance(self.fader_provenance)
            finally:
                self._is_updating = False

    def reset_unsynced(self) -> None:
        self._is_updating = True
        try:
            self.fader_val.set(0)
            self._last_fader_val = 0
            db_text, midi_text = format_db(0).split(" · ", 1)
            self.db_label_var.set(db_text)
            self.midi_label_var.set(f"{midi_text} DEFAULT")
            self.fader_provenance = ValueProvenance.UNSYNCED_DEFAULT
            self.badge.set_provenance(self.fader_provenance)
        finally:
            self._is_updating = False

    def destroy(self) -> None:
        if self._fader_after_id is not None:
            try:
                self.after_cancel(self._fader_after_id)
            except tk.TclError:
                pass
        super().destroy()


STAGE_STRIP_TAGS = {
    1: "MIC 1",
    2: "MIC 2",
    3: "COMBO 3",
    4: "COMBO 4",
    5: "LINE 5/6",
    6: "LINE 7/8",
    7: "BT/USB",
}


class StageChannelCard(tk.Frame):
    """Single channel rotary card in the live-performance STAGE view."""

    def __init__(
        self,
        master: tk.Misc,
        channel_index: int,
        title: str,
        subtitle: str,
        fonts: dict,
        service: Any = None,
        on_select: Optional[Callable[[SelectionTarget], None]] = None,
        on_feedback: Any = None,
    ) -> None:
        colors = theme.COLORS
        super().__init__(
            master,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
            bd=0,
            padx=8,
            pady=6,
        )
        self.channel_index = channel_index
        self.tag = STAGE_STRIP_TAGS.get(channel_index, f"CH {channel_index}")
        self.title = title
        self.subtitle = subtitle
        self.fonts = fonts
        self.service = service
        self._on_select = on_select
        self.on_feedback = on_feedback
        self.active_bus = "main"
        self.is_selected = False
        self._is_updating = False

        self.level_val = tk.IntVar(value=0)
        self._last_level_val = 0
        self._pending_level: Optional[int] = None
        self._level_after_id: Optional[str] = None
        self.is_muted = tk.BooleanVar(value=False)
        self.level_label_var = tk.StringVar(value="Approx. -inf dB · DEFAULT")
        self.bus_route_var = tk.StringVar(value="LEVEL · MAIN")

        self._build()

    def _bus_accent_color(self, bus_id: Optional[str] = None) -> str:
        b_key = (bus_id or self.active_bus or "main").lower()
        if b_key == "main" and self.channel_index == 7:
            return theme.BUS_COLORS["usb"]
        return theme.BUS_COLORS.get(b_key, theme.BUS_COLORS["main"])

    def _param_id(self) -> str:
        if self.active_bus == "main":
            return f"ch{self.channel_index}.fader"
        return f"ch{self.channel_index}.send_{self.active_bus}"

    def _build(self) -> None:
        colors = theme.COLORS
        accent = self._bus_accent_color("main")

        self.header_accent_bar = tk.Frame(self, bg=accent, height=3)
        self.header_accent_bar.pack(fill="x", pady=(0, 4))

        hdr = tk.Frame(self, bg=colors["surface_alt"], padx=6, pady=3)
        hdr.pack(fill="x")
        self.header_frame = hdr

        top = tk.Frame(hdr, bg=colors["surface_alt"])
        top.pack(fill="x")
        self.tag_label = tk.Label(
            top, text=self.tag, font=self.fonts["eyebrow"],
            fg=accent, bg=colors["surface_alt"], anchor="w",
        )
        self.tag_label.pack(side="left")

        self.route_label = tk.Label(
            top, textvariable=self.bus_route_var, font=self.fonts["status_key"],
            fg=colors["text_secondary"], bg=colors["surface_alt"], anchor="e",
        )
        self.route_label.pack(side="right")

        self.name_label = tk.Label(
            hdr, text=f"{self.title} · {self.subtitle}", font=self.fonts["caption"],
            fg=colors["text"], bg=colors["surface_alt"], anchor="w",
        )
        self.name_label.pack(fill="x")
        self._bind_click(hdr)

        self.dial = RotaryDial(
            self,
            variable=self.level_val,
            command=self._on_dial_drag,
            default=101,
            accent=accent,
            width=108,
            height=108,
        )
        self.dial.pack(expand=True, pady=2)
        self.dial.bind("<ButtonPress-1>", self._begin_gesture, add="+")
        self.dial.bind("<ButtonRelease-1>", self._on_dial_release, add="+")

        tk.Label(
            self, textvariable=self.level_label_var, font=self.fonts["caption"],
            fg=colors["text_secondary"], bg=colors["surface"],
        ).pack(fill="x", pady=(0, 3))

        self.mute_btn = tk.Button(
            self,
            text="MUTE",
            font=self.fonts["eyebrow"],
            bg=colors["surface_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["danger"],
            activeforeground=colors["text"],
            bd=0,
            relief="flat",
            cursor="hand2",
            pady=3,
            command=self._toggle_mute,
        )
        self.mute_btn.pack(fill="x", side="bottom")

    def _bind_click(self, widget: tk.Misc) -> None:
        widget.bind("<Button-1>", self._on_header_click, add="+")
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._bind_click(child)

    def _on_header_click(self, _event: tk.Event) -> None:
        if self._on_select is not None:
            self._on_select(SelectionTarget.input(self.channel_index))

    def set_selected(self, selected: bool) -> None:
        colors = theme.COLORS
        self.is_selected = bool(selected)
        self.configure(
            highlightbackground=colors["cyan"] if self.is_selected else colors["border"],
            highlightthickness=2 if self.is_selected else 1,
        )

    def set_active_bus(self, bus_id: str) -> None:
        b_key = str(bus_id or "main").lower()
        if b_key not in theme.BUS_SPECS:
            return
        self.active_bus = b_key
        accent = self._bus_accent_color(b_key)
        self.header_accent_bar.configure(bg=accent)
        self.tag_label.configure(fg=accent)
        self.dial.set_accent(accent)
        badge = theme.BUS_SPECS[b_key]["badge"]
        self.bus_route_var.set("LEVEL · MAIN" if b_key == "main" else f"SEND → {badge}")
        self.refresh_commanded()

    def set_meter_level(self, rms_db: Optional[float], peak_db: Optional[float], live: bool = True) -> None:
        if self.channel_index <= 6:
            self.dial.set_meter_level(rms_db, peak_db, live=live)
        else:
            self.dial.clear_meter()

    def clear_meter(self) -> None:
        self.dial.clear_meter()

    def _begin_gesture(self, _event: Optional[tk.Event] = None) -> None:
        begin = getattr(self.service, "begin_batch", None)
        if callable(begin):
            try:
                begin()
            except Exception:
                pass

    def _end_gesture(self) -> None:
        end = getattr(self.service, "end_batch", None)
        if callable(end):
            try:
                end()
            except Exception:
                pass

    def _set_readout(self, raw: int, default_tag: bool = False) -> None:
        db_text, midi_text = format_db(raw).split(" · ", 1)
        suffix = " DEFAULT" if default_tag else f" · {midi_text}"
        self.level_label_var.set(f"{db_text}{suffix}")

    def _on_dial_drag(self, val_str: str) -> None:
        if self._is_updating:
            return
        val = int(val_str)
        self._pending_level = val
        self._set_readout(val)
        if self._level_after_id is None:
            self._level_after_id = self.after(30, self._flush_level)

    def _on_dial_release(self, _event: Optional[tk.Event]) -> None:
        if self._level_after_id is not None:
            self.after_cancel(self._level_after_id)
            self._level_after_id = None
        self._flush_level()
        self._end_gesture()

    def _flush_level(self) -> None:
        self._level_after_id = None
        if self._pending_level is None:
            return
        val = self._pending_level
        self._pending_level = None
        prev = self._last_level_val
        if not self.service:
            return
        try:
            if self.active_bus == "main":
                self.service.set_fader(self.channel_index, val)
            else:
                self.service.set_send(self.channel_index, self.active_bus, val, unit="raw")
            self._last_level_val = val
            if self.on_feedback:
                self.on_feedback(f"STAGE {self.tag}: LEVEL COMMANDED")
        except Exception:
            self._is_updating = True
            try:
                self.level_val.set(prev)
                self._set_readout(prev)
            finally:
                self._is_updating = False

    def _toggle_mute(self) -> None:
        prev = self.is_muted.get()
        new_mute = not prev
        self.is_muted.set(new_mute)
        self._update_mute_ui(new_mute)
        if self.service:
            try:
                self.service.set_mute(self.channel_index, new_mute)
            except Exception:
                self.is_muted.set(prev)
                self._update_mute_ui(prev)

    def _update_mute_ui(self, muted: bool) -> None:
        colors = theme.COLORS
        self.mute_btn.configure(
            bg=colors["danger"] if muted else colors["surface_alt"],
            fg=colors["text"] if muted else colors["text_secondary"],
            text="MUTED" if muted else "MUTE",
        )

    def refresh_commanded(self) -> None:
        if self.service is None:
            return
        self._is_updating = True
        try:
            st = self.service.state_store.get_parameter(self._param_id())
            raw = None
            if st is not None:
                raw = st.commanded_raw_midi if st.commanded_raw_midi is not None else getattr(st, "observed_raw_midi", None)
            if isinstance(raw, int):
                self.level_val.set(raw)
                self._last_level_val = raw
                self._set_readout(raw, default_tag=False)
            else:
                self.level_val.set(0)
                self._last_level_val = 0
                self._set_readout(0, default_tag=True)

            m_st = self.service.state_store.get_parameter(f"ch{self.channel_index}.mute")
            if m_st is not None and (m_st.commanded_raw_midi is not None or getattr(m_st, "observed_raw_midi", None) is not None):
                muted = bool(m_st.commanded_value if m_st.commanded_raw_midi is not None else m_st.observed_value)
                self.is_muted.set(muted)
                self._update_mute_ui(muted)
            else:
                self.is_muted.set(False)
                self._update_mute_ui(False)
        finally:
            self._is_updating = False

    def reset_unsynced(self) -> None:
        self._is_updating = True
        try:
            self.level_val.set(0)
            self._last_level_val = 0
            self._set_readout(0, default_tag=True)
            self.is_muted.set(False)
            self._update_mute_ui(False)
            self.clear_meter()
        finally:
            self._is_updating = False

    def destroy(self) -> None:
        if self._level_after_id is not None:
            try:
                self.after_cancel(self._level_after_id)
            except tk.TclError:
                pass
        super().destroy()


class MixerConsole(tk.Frame):
    """Container holding the 7 logical input channel strips + 1 Master strip."""

    def __init__(
        self,
        master: tk.Misc,
        fonts: dict,
        service: Any = None,
        on_feedback: Any = None,
        on_view_changed: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self._on_view_changed = on_view_changed
        self.strips: Dict[int, ChannelStripWidget] = {}
        self.stage_cards: Dict[int, StageChannelCard] = {}
        self.bus_strips: Dict[str, "BusMasterStripWidget"] = {}
        self.bus_buttons: Dict[str, tk.Button] = {}
        self.view_buttons: Dict[str, tk.Button] = {}
        self.active_bus: str = "main"
        self.active_view: str = "mixer"
        self._bus_view_active = False
        self._tap_times: list[float] = []
        self.tap_bpm: Optional[int] = None
        self._last_meter_ts: float = 0.0
        self.selected_target: Optional[SelectionTarget] = None
        # Service listeners may run on the MIDI thread: they only enqueue; the Tk
        # main thread drains the queue (never touch a widget from another thread).
        self._ui_queue: "queue.SimpleQueue[tuple[str, Any]]" = queue.SimpleQueue()
        self._poll_after_id: Optional[str] = None
        self._build()

        self.inspector = ChannelDetailPanel(
            self._middle,
            self.fonts,
            service=self.service,
            on_close=self.clear_selection,
            on_phantom_changed=self._on_phantom_changed,
        )
        self.bind("<Configure>", self._on_console_resize, add="+")
        self._key_bindings: list[tuple[str, str]] = []
        self._bind_history_keys()
        self.scene_bar.set_enabled(callable(getattr(self.service, "capture_scene", None)))
        self._refresh_scene_slots()

        self.command_log_panel = CommandLogPanel(self, self.fonts)
        self.command_log_panel.pack(
            side="bottom",
            fill="x",
            padx=theme.TOKENS["spacing_large"],
            pady=(0, theme.TOKENS["spacing_medium"]),
        )

        if self.service:
            add_listener = getattr(self.service, "add_command_log_listener", None)
            if callable(add_listener):
                add_listener(self._on_command_log_update)
            boundary = getattr(self.service, "command_boundary", None)
            entries = getattr(boundary, "command_log", [])
            if isinstance(entries, (list, tuple)):
                self.command_log_panel.set_entries(entries)
            add_state = getattr(self.service, "add_listener", None)
            if callable(add_state):
                add_state(self._on_state_event)
            add_meter = getattr(self.service, "add_meter_listener", None)
            if callable(add_meter):
                add_meter(self._on_meter_event)
        self._refresh_history_buttons()
        self._poll_ui_queue()

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        # Console Header Banner
        banner = tk.Frame(self, bg=colors["background"])
        banner.pack(fill="x", padx=spacing["spacing_large"], pady=(4, 2))

        tk.Label(
            banner,
            text="FLOW 8 MIXER CONSOLE",
            font=self.fonts["subtitle"],
            fg=colors["cyan"],
            bg=colors["background"],
        ).pack(side="left")

        tk.Label(
            banner,
            text="7 LOGICAL STRIPS + MAIN L/R MASTER",
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["background"],
        ).pack(side="left", padx=(spacing["spacing_medium"], 0))

        tk.Label(
            banner,
            text="UNSYNCED · COMMAND VALUES ONLY",
            font=self.fonts["status_key"],
            fg=colors["warning"],
            bg=colors["background"],
        ).pack(side="right")

        # Scene slots live in this row, so they cost no vertical space at 1366x768.
        self.scene_bar = SceneBar(
            banner, self.fonts, on_capture=self.capture_scene, on_recall=self.recall_scene
        )
        self.scene_bar.pack(side="right", padx=(0, spacing["spacing_large"]))

        # History (Undo / Redo) buttons
        hist_frame = tk.Frame(banner, bg=colors["background"])
        hist_frame.pack(side="right", padx=(0, spacing["spacing_medium"]))

        self.undo_btn = tk.Button(
            hist_frame,
            text="↶ UNDO",
            font=self.fonts["caption"],
            bg=colors["surface_alt"],
            fg=colors["cyan_soft"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["cyan"],
            disabledforeground=colors["text_muted"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=2,
            command=self.undo,
        )
        self.undo_btn.pack(side="left", padx=1)

        self.redo_btn = tk.Button(
            hist_frame,
            text="↷ REDO",
            font=self.fonts["caption"],
            bg=colors["surface_alt"],
            fg=colors["cyan_soft"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["cyan"],
            disabledforeground=colors["text_muted"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=2,
            command=self.redo,
        )
        self.redo_btn.pack(side="left", padx=1)

        self.bus_view_btn = tk.Button(
            hist_frame,
            text="BUS MASTERS",
            font=self.fonts["caption"],
            bg=colors["surface_alt"],
            fg=colors["lime"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["cyan"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=2,
            command=self.toggle_bus_masters,
        )
        self.bus_view_btn.pack(side="left", padx=(4, 0))

        self.mute_all_btn = tk.Button(
            hist_frame,
            text="MUTE ALL",
            font=self.fonts["caption"],
            bg=colors["safety_bg"],
            fg=colors["danger"],
            activebackground=colors["danger"],
            activeforeground=colors["text"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=2,
            command=self.mute_all,
        )
        self.mute_all_btn.pack(side="left", padx=(4, 0))

        # Sends-on-Fader Bus Selector Bar (Official FLOW 8 workflow parity)
        bus_bar = tk.Frame(self, bg=colors["background"])
        bus_bar.pack(fill="x", padx=spacing["spacing_large"], pady=(0, 3))
        self.bus_bar = bus_bar

        tk.Label(
            bus_bar,
            text="SENDS ON FADER:",
            font=self.fonts["eyebrow"],
            fg=colors["text_muted"],
            bg=colors["background"],
        ).pack(side="left", padx=(0, 6))

        for bus_id in theme.BUS_ORDER:
            spec = theme.BUS_SPECS[bus_id]
            btn = tk.Button(
                bus_bar,
                text=spec["badge"],
                font=self.fonts["eyebrow"],
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=1,
                command=lambda b=bus_id: self.select_bus(b),
            )
            btn.pack(side="left", padx=2)
            self.bus_buttons[bus_id] = btn

        self.active_bus_label_var = tk.StringVar(value="ACTIVE MIX: MAIN L/R")
        tk.Label(
            bus_bar,
            textvariable=self.active_bus_label_var,
            font=self.fonts["status_key"],
            fg=theme.BUS_COLORS["main"],
            bg=colors["background"],
        ).pack(side="left", padx=(10, 0))
        self._active_bus_indicator = bus_bar.winfo_children()[-1]

        # Segmented MIXER | STAGE View Toggle on the right of bus_bar
        view_seg = tk.Frame(bus_bar, bg=colors["surface"], highlightbackground=colors["border"], highlightthickness=1)
        view_seg.pack(side="right")
        for v_key, v_label in (("mixer", "MIXER"), ("stage", "STAGE")):
            vbtn = tk.Button(
                view_seg,
                text=v_label,
                font=self.fonts["eyebrow"],
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=1,
                command=lambda v=v_key: self.set_view_mode(v),
            )
            vbtn.pack(side="left")
            self.view_buttons[v_key] = vbtn

        # Middle band: strips on the left, the Channel Detail Inspector docks on
        # the right while a target is selected.
        self._middle = tk.Frame(self, bg=colors["background"])
        self._middle.pack(fill="both", expand=True)

        # Strips Container
        strips_container = tk.Frame(self._middle, bg=colors["background"])
        self._strips_container = strips_container
        strips_container.pack(
            side="left", fill="both", expand=True,
            padx=spacing["spacing_medium"], pady=(0, 4),
        )

        # Grid configuration: 8 columns (1-7 strips + 8 main)
        for col in range(8):
            strips_container.grid_columnconfigure(col, weight=1, uniform="strip")
        strips_container.grid_rowconfigure(0, weight=1)

        # Strip Metadata definitions according to FLOW 8 Domain Model
        specs = [
            (1, "Mic 1", "Midas Preamp", "XLR", "PAN", True),
            (2, "Mic 2", "Midas Preamp", "XLR", "PAN", True),
            (3, "Line 3", "Mic / Line", "COMBO", "PAN", False),
            (4, "Line 4", "Mic / Line", "COMBO", "PAN", False),
            (5, "Ch 5/6", "Stereo Line / Hi-Z", "TRS", "BAL", False),
            (6, "Ch 7/8", "Stereo Line / Hi-Z", "TRS", "BAL", False),
            (7, "USB / BT", "Audio Return", "USB", "BAL", False),
        ]

        for idx, title, subtitle, kind_badge, pan_label, has_phantom in specs:
            strip = ChannelStripWidget(
                master=strips_container,
                channel_index=idx,
                title=title,
                subtitle=subtitle,
                kind_badge=kind_badge,
                pan_label=pan_label,
                has_phantom=has_phantom,
                fonts=self.fonts,
                service=self.service,
                is_master=False,
                on_select=self.select_target,
                on_phantom_request=self._on_phantom_request,
                on_feedback=self.on_feedback,
            )
            strip.grid(row=0, column=idx - 1, sticky="nsew", padx=3, pady=2)
            self.strips[idx] = strip

        # Master Strip (Main L/R, channel_index=8)
        master_strip = ChannelStripWidget(
            master=strips_container,
            channel_index=8,
            title="Main L/R",
            subtitle="Master Output",
            kind_badge="MASTER",
            pan_label="BAL",
            has_phantom=False,
            fonts=self.fonts,
            service=self.service,
            is_master=True,
            on_select=self.select_target,
            on_feedback=self.on_feedback,
        )
        master_strip.grid(row=0, column=7, sticky="nsew", padx=(8, 3), pady=2)
        self.strips[8] = master_strip

        # Bus Masters Container (MON 1, MON 2, FX 1, FX 2 — toggled from banner)
        self._bus_container = tk.Frame(self._middle, bg=colors["background"])
        for col in range(4):
            self._bus_container.grid_columnconfigure(col, weight=1, uniform="bus")
        self._bus_container.grid_rowconfigure(0, weight=1)

        bus_specs = [
            ("mon1", "MON 1", "Stage Monitor 1 · MIDI Ch 9", "warning"),
            ("mon2", "MON 2", "Stage Monitor 2 · MIDI Ch 10", "warning"),
            ("fx1", "FX 1", "Reverb Return · MIDI Ch 11", "purple_soft"),
            ("fx2", "FX 2", "Delay / Mod Return · MIDI Ch 12", "purple_soft"),
        ]
        for col, (bus_id, title, subtitle, accent_key) in enumerate(bus_specs):
            bstrip = BusMasterStripWidget(
                master=self._bus_container,
                bus_id=bus_id,
                title=title,
                subtitle=subtitle,
                accent_key=accent_key,
                fonts=self.fonts,
                service=self.service,
                on_feedback=self.on_feedback,
            )
            bstrip.grid(row=0, column=col, sticky="nsew", padx=8, pady=4)
            self.bus_strips[bus_id] = bstrip

        # Stage View Container (7 rotary dial cards + FX 2 TAP TEMPO pad in 4x2 grid)
        self._stage_container = tk.Frame(self._middle, bg=colors["background"])
        for col in range(4):
            self._stage_container.grid_columnconfigure(col, weight=1, uniform="stage_col")
        for row in range(2):
            self._stage_container.grid_rowconfigure(row, weight=1, uniform="stage_row")

        for idx, title, subtitle, _kind_badge, _pan_label, _has_phantom in specs:
            scard = StageChannelCard(
                master=self._stage_container,
                channel_index=idx,
                title=title,
                subtitle=subtitle,
                fonts=self.fonts,
                service=self.service,
                on_select=self.select_target,
                on_feedback=self.on_feedback,
            )
            r, c = divmod(idx - 1, 4)
            scard.grid(row=r, column=c, sticky="nsew", padx=4, pady=3)
            self.stage_cards[idx] = scard

        # 8th Stage Card: FX 2 TAP TEMPO (BPM) Pad
        tap_card = tk.Frame(
            self._stage_container,
            bg=colors["surface"],
            highlightbackground=theme.BUS_COLORS["fx2"],
            highlightthickness=1,
            bd=0,
            padx=8,
            pady=6,
        )
        tap_card.grid(row=1, column=3, sticky="nsew", padx=4, pady=3)
        self.tap_card = tap_card
        tk.Frame(tap_card, bg=theme.BUS_COLORS["fx2"], height=3).pack(fill="x", pady=(0, 4))
        tk.Label(
            tap_card, text="FX 2 · TAP TEMPO", font=self.fonts["eyebrow"],
            fg=theme.BUS_COLORS["fx2"], bg=colors["surface"], anchor="w",
        ).pack(fill="x")
        self.tap_bpm_var = tk.StringVar(value="TAP TEMPO · — BPM")
        self.tap_tempo_btn = tk.Button(
            tap_card,
            textvariable=self.tap_bpm_var,
            font=self.fonts["subtitle"],
            bg=colors["surface_alt"],
            fg=theme.BUS_COLORS["fx2"],
            activebackground=theme.BUS_COLORS["fx2"],
            activeforeground=colors["background"],
            highlightbackground=theme.BUS_COLORS["fx2"],
            highlightthickness=1,
            bd=0,
            relief="flat",
            cursor="hand2",
            pady=14,
            command=self.tap_tempo,
        )
        self.tap_tempo_btn.pack(fill="both", expand=True, pady=6)
        tk.Label(
            tap_card,
            text="LOCKED · MIDI Ch 16 blocked by safety policy",
            font=self.fonts["caption"],
            fg=colors["warning"],
            bg=colors["surface"],
            wraplength=200,
            justify="left",
        ).pack(fill="x", side="bottom")

        initial_bus = getattr(self.service, "active_bus", "main") if self.service else "main"
        self.select_bus(initial_bus, notify_service=False)
        initial_view = getattr(self.service, "active_view", "mixer") if self.service else "mixer"
        self.set_view_mode(initial_view, notify_service=False)

    def select_bus(self, bus_id: str, notify_service: bool = True) -> bool:
        """Select the active Sends-on-Fader bus ('main', 'mon1', 'mon2', 'fx1', 'fx2')."""
        b_key = str(bus_id or "main").lower()
        if b_key not in theme.BUS_SPECS:
            return False
        self.active_bus = b_key
        colors = theme.COLORS
        for key, btn in self.bus_buttons.items():
            accent = theme.BUS_COLORS[key]
            if key == b_key:
                btn.configure(bg=accent, fg=colors["background"], activebackground=accent, activeforeground=colors["background"])
            else:
                btn.configure(bg=colors["surface_alt"], fg=accent, activebackground=colors["surface_hover"], activeforeground=accent)
        spec = theme.BUS_SPECS[b_key]
        self.active_bus_label_var.set(f"ACTIVE MIX: {spec['title'].upper()}")
        if hasattr(self, "_active_bus_indicator"):
            self._active_bus_indicator.configure(fg=spec["color"])
        for strip in self.strips.values():
            strip.set_active_bus(b_key)
        for scard in self.stage_cards.values():
            scard.set_active_bus(b_key)
        if notify_service and self.service is not None:
            setter = getattr(self.service, "set_active_bus", None)
            if callable(setter):
                try:
                    setter(b_key)
                except Exception:
                    pass
        return True

    def set_view_mode(self, view: str, notify_service: bool = True) -> bool:
        """Switch between MIXER (vertical fader bank) and STAGE (7 rotary dials + tap tempo)."""
        v_key = str(view or "mixer").lower()
        if v_key not in ("mixer", "stage"):
            return False
        self.active_view = v_key
        colors = theme.COLORS
        for key, btn in self.view_buttons.items():
            if key == v_key:
                btn.configure(bg=colors["cyan"], fg=colors["background"], activebackground=colors["cyan"], activeforeground=colors["background"])
            else:
                btn.configure(bg=colors["surface_alt"], fg=colors["text_secondary"], activebackground=colors["surface_hover"], activeforeground=colors["text"])

        if v_key == "stage":
            self._bus_view_active = False
            self.bus_view_btn.configure(bg=colors["surface_alt"], fg=colors["lime"])
            if self._strips_container.winfo_manager():
                self._strips_container.pack_forget()
            if self._bus_container.winfo_manager():
                self._bus_container.pack_forget()
            for scard in self.stage_cards.values():
                scard.refresh_commanded()
            if not self._stage_container.winfo_manager():
                self._stage_container.pack(
                    side="left", fill="both", expand=True,
                    padx=theme.TOKENS["spacing_medium"], pady=(0, 4),
                )
        else:
            if self._stage_container.winfo_manager():
                self._stage_container.pack_forget()
            if self._bus_container.winfo_manager():
                self._bus_container.pack_forget()
            self._bus_view_active = False
            self.bus_view_btn.configure(bg=colors["surface_alt"], fg=colors["lime"])
            if not self._strips_container.winfo_manager():
                self._strips_container.pack(
                    side="left", fill="both", expand=True,
                    padx=theme.TOKENS["spacing_medium"], pady=(0, 4),
                )

        if self._on_view_changed is not None:
            try:
                self._on_view_changed(v_key)
            except Exception:
                pass
        if notify_service and self.service is not None:
            setter = getattr(self.service, "set_active_view", None)
            if callable(setter):
                try:
                    setter(v_key)
                except Exception:
                    pass
        return True

    def tap_tempo(self, now: Optional[float] = None) -> Optional[int]:
        """Calculate rolling BPM from consecutive taps while keeping MIDI Ch 16 safety-locked."""
        ts = time.monotonic() if now is None else float(now)
        if self._tap_times and (ts - self._tap_times[-1]) > 2.0:
            self._tap_times.clear()
        self._tap_times.append(ts)
        if len(self._tap_times) > 5:
            self._tap_times = self._tap_times[-5:]
        if len(self._tap_times) >= 2:
            intervals = [
                b - a for a, b in zip(self._tap_times[:-1], self._tap_times[1:])
                if 0.2 <= (b - a) <= 2.0
            ]
            if intervals:
                avg = sum(intervals) / len(intervals)
                bpm = max(40, min(240, round(60.0 / avg)))
                self.tap_bpm = bpm
                self.tap_bpm_var.set(f"TAP TEMPO · {bpm} BPM")
                self._feedback(f"TAP TEMPO: {bpm} BPM (LOCAL) — MIDI CH 16 LOCKED BY SAFETY POLICY")
                return bpm
        self._feedback("TAP TEMPO: TAP AGAIN FOR BPM — MIDI CH 16 LOCKED BY SAFETY POLICY")
        return self.tap_bpm

    def ingest_meter_levels(self, levels: Mapping[str, Mapping[str, float]], live: bool = True) -> None:
        """Update STAGE view pre-fader USB meter arcs. Renders arcs only when live=True."""
        if not live or not levels:
            self._last_meter_ts = 0.0
            for scard in self.stage_cards.values():
                scard.clear_meter()
            return
        self._last_meter_ts = time.monotonic()
        for idx, scard in self.stage_cards.items():
            entry = levels.get(f"ch{idx}")
            if entry is not None and idx <= 6:
                scard.set_meter_level(entry.get("rms", -120.0), entry.get("peak", -120.0), live=True)
            else:
                scard.clear_meter()

    def toggle_bus_masters(self) -> None:
        """Toggle between the 7+1 input/main view and the 4 Bus Master faders."""
        colors = theme.COLORS
        if self._bus_view_active:
            self._bus_container.pack_forget()
            self._strips_container.pack(
                side="left", fill="both", expand=True,
                padx=theme.TOKENS["spacing_medium"], pady=(0, 4),
            )
            self._bus_view_active = False
            self.bus_view_btn.configure(bg=colors["surface_alt"], fg=colors["lime"])
        else:
            if self.inspector_visible:
                self.clear_selection()
            self._strips_container.pack_forget()
            self._bus_container.pack(
                side="left", fill="both", expand=True,
                padx=theme.TOKENS["spacing_medium"], pady=(0, 4),
            )
            self._bus_view_active = True
            self.bus_view_btn.configure(bg=colors["cyan"], fg=colors["background"])

    # -- selection and inspector -------------------------------------------

    def _strip_for(self, target: SelectionTarget) -> Optional[ChannelStripWidget]:
        # Legacy widget key: the Main L/R strip is stored under 8. That is only
        # a dictionary key; the selection identity is MAIN_TARGET, not strip 8.
        key = 8 if target.kind == "main" else target.index
        return self.strips.get(key)

    @property
    def inspector_visible(self) -> bool:
        return bool(self.inspector.winfo_manager())

    def select_target(self, target: SelectionTarget) -> None:
        """Select exactly one target and show it in the inspector.

        Selection is presentation state only; it never dispatches a command.
        """
        if not isinstance(target, SelectionTarget):
            raise TypeError("select_target requires a SelectionTarget")
        strip = self._strip_for(target)
        if strip is None:
            return
        for other in self.strips.values():
            if other is not strip and other.is_selected:
                other.set_selected(False)
        strip.set_selected(True)
        for idx, scard in self.stage_cards.items():
            scard.set_selected(target.kind == "input" and target.index == idx)
        self.selected_target = target
        self._show_inspector()
        self.inspector.show_target(target)

    def clear_selection(self) -> None:
        """Close the inspector and clear every selection highlight."""
        for strip in self.strips.values():
            if strip.is_selected:
                strip.set_selected(False)
        for scard in self.stage_cards.values():
            if scard.is_selected:
                scard.set_selected(False)
        self.selected_target = None
        self.inspector.clear()
        if self.inspector.winfo_manager():
            self.inspector.pack_forget()

    def _inspector_width(self) -> int:
        available = self.winfo_width() - 2 * theme.TOKENS["spacing_large"]
        if available <= 2 * theme.TOKENS["spacing_large"]:
            return INSPECTOR_MAX_WIDTH  # not laid out yet
        room = available - len(self.strips) * MIN_STRIP_SLOT
        return max(INSPECTOR_MIN_WIDTH, min(INSPECTOR_MAX_WIDTH, room))

    def _show_inspector(self) -> None:
        spacing = theme.TOKENS
        self.inspector.configure(width=self._inspector_width())
        if not self.inspector.winfo_manager():
            # Packed before the active left container so the strips/stage yield space, not the inspector.
            anchor_widget = None
            for candidate in (self._strips_container, self._stage_container, self._bus_container):
                if candidate.winfo_manager():
                    anchor_widget = candidate
                    break
            pack_kw = {
                "side": "right",
                "fill": "y",
                "padx": (0, spacing["spacing_large"]),
                "pady": (0, spacing["spacing_large"]),
            }
            if anchor_widget is not None:
                pack_kw["before"] = anchor_widget
            self.inspector.pack(**pack_kw)

    def _on_console_resize(self, _event: tk.Event) -> None:
        if self.inspector_visible:
            width = self._inspector_width()
            if int(self.inspector.cget("width")) != width:
                self.inspector.configure(width=width)

    def _on_phantom_request(self, channel_index: int, enabled: bool) -> None:
        """A strip's +48V button: open the inspector and run the confirmation flow."""
        try:
            self.select_target(SelectionTarget.input(channel_index))
        except ValueError:
            return
        self.inspector.request_phantom(channel_index, enabled)

    # -- undo / redo ---------------------------------------------------------

    # Windows virtual-key codes. Layouts without Latin letters (e.g. Thai) report
    # no "z"/"y" keysym for Ctrl+Z / Ctrl+Y, but the key code stays the same.
    _VK_KEYS = {0x5A: "z", 0x59: "y"}

    def _bind_history_keys(self) -> None:
        """Ctrl+Z undo; Ctrl+Y or Ctrl+Shift+Z redo. Bound on the window, so a
        modal dialog (e.g. the +48V confirmation) keeps them from firing."""
        top = self.winfo_toplevel()
        funcid = top.bind("<Control-KeyPress>", self._on_history_key, add="+")
        self._key_bindings.append(("<Control-KeyPress>", funcid))

    def _on_history_key(self, event: tk.Event) -> Optional[str]:
        key = str(getattr(event, "keysym", "")).lower()
        if key not in ("z", "y") and sys.platform == "win32":
            key = self._VK_KEYS.get(getattr(event, "keycode", None), key)
        if key == "y":
            self.redo()
        elif key == "z":
            # Ctrl+Shift+Z: the Shift bit is set.
            if getattr(event, "state", 0) & 0x1:
                self.redo()
            else:
                self.undo()
        else:
            return None  # not ours: let other Ctrl shortcuts through
        return "break"

    def mute_all(self) -> bool:
        """Mute all 7 input channels in one atomic undoable batch (Figma 2:94 MUTE ALL)."""
        if self.service is None:
            self._feedback("MUTE ALL UNAVAILABLE — NO COMMAND SERVICE")
            return False
        begin = getattr(self.service, "begin_batch", None)
        end = getattr(self.service, "end_batch", None)
        if callable(begin):
            begin()
        try:
            for ch in range(1, 8):
                self.service.set_mute(ch, True)
        finally:
            if callable(end):
                end()
        self._refresh_strips()
        self._refresh_history_buttons()
        self._feedback("MUTE ALL COMMANDED — CH 1–7 MUTED")
        return True

    def undo(self) -> bool:
        """Undo the newest step. True only when commands were accepted."""
        return self._run_history("UNDO", "undo")

    def redo(self) -> bool:
        return self._run_history("REDO", "redo")

    def _feedback(self, message: str) -> None:
        if self.on_feedback:
            self.on_feedback(message)

    def _run_history(self, label: str, method: str) -> bool:
        action = getattr(self.service, method, None)
        if not callable(action):
            self._feedback(f"{label} UNAVAILABLE — NO COMMAND SERVICE")
            return False
        try:
            records = action()
        except Exception as error:
            logging.getLogger(__name__).exception("%s failed", label)
            self._refresh_strips()
            self._feedback(f"{label} FAILED — NOT SENT: {error}")
            return False
        if not records:
            self._feedback(f"NOTHING TO {label}")
            self._refresh_history_buttons()
            return False
        self._refresh_strips()
        self._refresh_history_buttons()
        self._feedback(f"{label} COMMANDED — {self._describe(records, method)}")
        return True

    def _refresh_history_buttons(self) -> None:
        if not hasattr(self, "undo_btn") or not hasattr(self, "redo_btn"):
            return
        colors = theme.COLORS
        can_undo = False
        can_redo = False
        if self.service is not None:
            ledger = getattr(self.service, "ledger", None)
            if ledger is not None:
                can_undo = getattr(ledger, "can_undo", False)
                can_redo = getattr(ledger, "can_redo", False)
        try:
            self.undo_btn.configure(
                state="normal" if can_undo else "disabled",
                fg=colors["cyan"] if can_undo else colors["text_muted"],
            )
            self.redo_btn.configure(
                state="normal" if can_redo else "disabled",
                fg=colors["cyan"] if can_redo else colors["text_muted"],
            )
        except tk.TclError:
            pass

    @staticmethod
    def _describe(records, method: str) -> str:
        if len(records) > 1:
            return f"{len(records)} CHANGES"
        record = records[0]
        value = record.previous_value if method == "undo" else record.new_value
        who = "MAIN" if record.channel_index == 8 else f"CH {record.channel_index}"
        shown = ("ON" if value else "OFF") if record.parameter_type == "mute" else f"MIDI {value}"
        return f"{who} {record.parameter_type.upper()} {shown}"

    def _refresh_strips(self) -> None:
        for strip in self.strips.values():
            strip.refresh_commanded()
        for scard in self.stage_cards.values():
            scard.refresh_commanded()
        for bstrip in self.bus_strips.values():
            bstrip.refresh_commanded()
        self._refresh_inspector()

    def _refresh_inspector(self) -> None:
        inspector = getattr(self, "inspector", None)
        if inspector is not None:
            inspector._refresh_if_attached()

    # -- inbound hardware state (MIDI IN -> service listener -> strips) ----------

    POLL_MS = 25

    def _on_state_event(self, param_id: str, value: Any) -> None:
        """Service listener; any thread. Enqueue only."""
        self._ui_queue.put((param_id, value))

    def _on_meter_event(self, levels: dict[str, dict[str, float]]) -> None:
        """Meter listener; any thread. Enqueue only."""
        self._ui_queue.put(("__meters__", levels))

    def _poll_ui_queue(self) -> None:
        self._poll_after_id = None
        try:
            self._drain_ui_queue()
            if self._last_meter_ts > 0.0 and (time.monotonic() - self._last_meter_ts) > 2.0:
                self.ingest_meter_levels({}, live=False)
            self._poll_after_id = self.after(self.POLL_MS, self._poll_ui_queue)
        except tk.TclError:
            return

    def _drain_ui_queue(self) -> None:
        """Apply queued service events on the Tk thread; newest value per parameter wins."""
        latest: Dict[str, Any] = {}
        while True:
            try:
                param_id, value = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            if param_id == RECONCILE_EVENT:
                latest.clear()  # earlier events describe the discarded session
            latest[param_id] = value
        if not latest:
            return
        if "__meters__" in latest:
            self.ingest_meter_levels(latest.pop("__meters__"), live=True)
        if not latest:
            return
        if RECONCILE_EVENT in latest:
            del latest[RECONCILE_EVENT]
            for strip in self.strips.values():
                strip.reset_unsynced()
            for scard in self.stage_cards.values():
                scard.reset_unsynced()
            for bstrip in self.bus_strips.values():
                bstrip.reset_unsynced()
            self._refresh_history_buttons()
        if STATE_CHANGED_EVENT in latest:
            del latest[STATE_CHANGED_EVENT]
            svc_bus = getattr(self.service, "active_bus", None)
            if isinstance(svc_bus, str) and svc_bus != self.active_bus and svc_bus in theme.BUS_SPECS:
                self.select_bus(svc_bus, notify_service=False)
            svc_view = getattr(self.service, "active_view", None)
            if isinstance(svc_view, str) and svc_view != self.active_view and svc_view in ("mixer", "stage"):
                self.set_view_mode(svc_view, notify_service=False)
            for strip in self.strips.values():
                strip.refresh_commanded()
            for scard in self.stage_cards.values():
                scard.refresh_commanded()
            for bstrip in self.bus_strips.values():
                bstrip.refresh_commanded()
            self._refresh_scene_slots()
            self._refresh_history_buttons()
        if "__command_log__" in latest:
            self._handle_log_update(latest.pop("__command_log__"))
        # Observed values only repaint the strip; they are never sent back to hardware.
        for param_id, value in latest.items():
            self._apply_observed(param_id, value)
        self._refresh_inspector()

    def _apply_observed(self, param_id: str, value: Any) -> None:
        head, _, name = param_id.partition(".")
        if head in self.bus_strips and name == "fader" and value is not None:
            self.bus_strips[head].sync_fader(int(value))
            if head == self.active_bus and 8 in self.strips:
                self.strips[8].sync_fader(int(value))
            return
        if head == "main":
            strip = self.strips.get(8)
            name = "pan" if name == "balance" else name
            if name == "fader" and self.active_bus != "main":
                return
        elif head.startswith("ch") and head[2:].isdigit():
            strip = self.strips.get(int(head[2:]))
        else:
            return
        if strip is None or value is None:
            return
        if name == "fader":
            if not strip.is_master and self.active_bus != "main":
                return
            strip.sync_fader(int(value))
        elif name == f"send_{self.active_bus}" and not strip.is_master:
            strip.sync_fader(int(value))
        elif name == "pan":
            strip.sync_pan(int(value))
        elif name == "mute" and not strip.is_master:
            strip.sync_mute(bool(value))

    # -- scenes ----------------------------------------------------------------

    def _saved_slots(self) -> set[int]:
        try:
            names = set(self.service.scenes.names())
        except Exception:
            return set()
        return {slot for slot in range(1, 9) if slot_name(slot) in names}

    def _refresh_scene_slots(self) -> None:
        self.scene_bar.set_populated(self._saved_slots())

    def capture_scene(self, slot: int) -> bool:
        """Store the known fader, pan and mute values in *slot* (never +48V)."""
        name = slot_name(slot)
        capture = getattr(self.service, "capture_scene", None)
        if not callable(capture):
            self._feedback("SCENE CAPTURE UNAVAILABLE — NO COMMAND SERVICE")
            return False
        replacing = slot in self._saved_slots()
        try:
            snapshot = capture(name)
        except ValueError:
            # Nothing has been commanded or observed yet: only app defaults exist.
            self._feedback("SCENE CAPTURE REJECTED — NO KNOWN PARAMETERS")
            return False
        except Exception as error:
            logging.getLogger(__name__).exception("Scene capture failed")
            self._feedback(f"SCENE CAPTURE FAILED — {error}")
            return False
        self._refresh_scene_slots()
        values = sum(len(entry) for entry in snapshot.parameters.values())
        verb = "OVERWRITTEN" if replacing else "CAPTURED"
        self._feedback(f"SCENE {verb} — {name} · {values} VALUES")
        return True

    def recall_scene(self, slot: int) -> bool:
        """Send a saved scene through the command boundary as one undoable step."""
        name = slot_name(slot)
        recall = getattr(self.service, "recall_scene", None)
        if not callable(recall):
            self._feedback("SCENE RECALL UNAVAILABLE — NO COMMAND SERVICE")
            return False
        try:
            result = recall(name)
        except KeyError:
            self._refresh_scene_slots()
            self._feedback(f"SCENE RECALL REJECTED — {name} IS EMPTY")
            return False
        except Exception as error:
            logging.getLogger(__name__).exception("Scene recall failed")
            self._refresh_strips()
            self._feedback(f"SCENE RECALL FAILED — NOT SENT: {error}")
            return False
        self._refresh_strips()
        failed = len(result.failed)
        if failed and not result.applied:
            self._feedback(f"SCENE RECALL FAILED — NOT SENT ({failed} REJECTED)")
            return False
        if failed:
            self._feedback(
                f"SCENE RECALLED — {name} · {result.applied} SENT · {failed} NOT SENT"
            )
        else:
            self._feedback(f"SCENE RECALLED — {name}")
        return True

    def _on_phantom_changed(self, channel_index: int, commanded: bool) -> None:
        strip = self.strips.get(channel_index)
        if strip is not None and not strip.is_master:
            strip.sync_phantom(commanded)

    def _on_command_log_update(self, entries: list) -> None:
        """Schedule command-log rendering on the Tk main thread."""
        snapshot = list(entries)
        try:
            self.after_idle(lambda: self._handle_log_update(snapshot))
        except (tk.TclError, RuntimeError):
            # Called from a worker thread while Tk mainloop is not active, or closing.
            self._ui_queue.put(("__command_log__", snapshot))

    def _handle_log_update(self, snapshot: list) -> None:
        try:
            self.command_log_panel.set_entries(snapshot)
            self._refresh_history_buttons()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        try:
            top = self.winfo_toplevel()
            for sequence, funcid in self._key_bindings:
                top.unbind(sequence, funcid)
        except tk.TclError:
            pass
        self._key_bindings.clear()
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None
        if self.service:
            remove_state = getattr(self.service, "remove_listener", None)
            if callable(remove_state):
                remove_state(self._on_state_event)
            remove_meter = getattr(self.service, "remove_meter_listener", None)
            if callable(remove_meter):
                remove_meter(self._on_meter_event)
        try:
            self.inspector.detach()
        except Exception:
            logging.getLogger(__name__).exception("Could not detach inspector")
        if self.service:
            remove_listener = getattr(self.service, "remove_command_log_listener", None)
            if callable(remove_listener):
                try:
                    remove_listener(self._on_command_log_update)
                except Exception:
                    logging.getLogger(__name__).exception("Could not remove command-log listener")
        super().destroy()
