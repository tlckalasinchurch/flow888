"""7-Strip Mixer Console Component for FLOW 8 Cyber Neon Workstation.

Renders exactly 7 logical channel strips plus 1 Main L/R master strip
according to the Behringer FLOW 8 Hardware Domain Model.
"""

from __future__ import annotations

import logging
import tkinter as tk
from enum import Enum
from typing import Any, Callable, Dict, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.parameter_mapping import fader_midi_to_db, pan_midi_to_percent
from flow8.ui import theme
from flow8.ui.components.controls import HorizontalSlider, VerticalFader
from flow8.ui.components.command_log import CommandLogPanel
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
            padx=8,
            pady=8,
        )
        self.channel_index = channel_index
        self.is_master = is_master
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
        # Nothing commanded or observed yet: say so on the (short) MIDI line. A longer
        # dB line would widen every strip and push the last ones off screen.
        self.midi_label_var = tk.StringVar(value=f"{midi_text} · DEFAULT")
        self.pan_label_var = tk.StringVar(value=format_pan(self.pan_val.get()))

        self._build(title, subtitle, kind_badge, pan_label)

    def _build(self, title: str, subtitle: str, kind_badge: str, pan_label: str) -> None:
        colors = theme.COLORS

        # 1. Strip Header (the only region that selects the strip)
        hdr = tk.Frame(self, bg=colors["surface"])
        hdr.pack(fill="x", pady=(0, 6))
        self.header_frame = hdr

        # Channel Number & Type Badge
        top_row = tk.Frame(hdr, bg=colors["surface"])
        top_row.pack(fill="x")

        ch_num_text = "MAIN" if self.is_master else f"{self.channel_index:02d}"
        # Bolder, larger channel badge for hierarchy
        ch_font = self.fonts["subtitle"] if self.is_master else self.fonts["eyebrow"]
        ch_padx = 6 if self.is_master else 4
        tk.Label(
            top_row,
            text=ch_num_text,
            font=ch_font,
            fg=colors["cyan"] if self.is_master else colors["cyan_soft"],
            bg=colors["surface"],
            padx=ch_padx,
            pady=2,
        ).pack(side="left")

        tk.Label(
            top_row,
            text=kind_badge,
            font=self.fonts["caption"],
            fg=colors["purple_soft"] if not self.is_master else colors["lime"],
            bg=colors["surface_alt"],
            padx=4,
            pady=1,
        ).pack(side="right")

        # Name
        tk.Label(
            hdr,
            text=title,
            font=self.fonts["subtitle"] if self.is_master else self.fonts["nav_active"],
            fg=colors["text"],
            bg=colors["surface"],
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        tk.Label(
            hdr,
            text=subtitle,
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["surface"],
            anchor="w",
        ).pack(fill="x")

        self._bind_header_selection(hdr)

        # Divider
        tk.Frame(self, bg=colors["border"], height=1).pack(fill="x", pady=6)

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
            self.phantom_btn.pack(fill="x", pady=(0, 6))

        # 3. Pan / Balance Control
        pan_frame = tk.Frame(self, bg=colors["surface"])
        pan_frame.pack(fill="x", pady=(0, 6))

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
                pady=6,
                command=self._toggle_mute,
            )
            self.mute_btn.pack(fill="x", pady=(4, 8))
        else:
            # Spacer for alignment
            tk.Frame(self, bg=colors["surface"], height=32).pack(fill="x", pady=(4, 8))

        # 5. Fader readout: approximate dB and raw MIDI are separate visual levels.
        readout = tk.Frame(
            self,
            bg=colors["background_alt"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        readout.pack(fill="x", pady=(0, 6))

        tk.Label(
            readout,
            textvariable=self.db_label_var,
            font=self.fonts["status_value"],
            fg=colors["cyan"] if self.is_master else colors["text"],
            bg=colors["background_alt"],
            pady=3,
        ).pack(fill="x")

        tk.Label(
            readout,
            textvariable=self.midi_label_var,
            font=self.fonts["caption"],
            fg=colors["text_muted"],
            bg=colors["background_alt"],
        ).pack(fill="x", pady=(0, 3))

        # 6. Vertical Volume Fader
        fader_container = tk.Frame(self, bg=colors["surface"])
        fader_container.pack(fill="both", expand=True, pady=(0, 6))

        self.fader_scale = VerticalFader(
            fader_container,
            variable=self.fader_val,
            command=self._on_fader_drag,
            default=101,
            accent=colors["cyan"] if self.is_master else colors["cyan_soft"],
        )
        self.fader_scale.pack(fill="both", expand=True)
        self.fader_scale.bind("<ButtonPress-1>", self._begin_gesture, add="+")
        self.fader_scale.bind("<ButtonRelease-1>", self._on_fader_release, add="+")

        # 7. Strip Footer Number
        tk.Label(
            self,
            text=ch_num_text,
            font=self.fonts["eyebrow"],
            fg=colors["text_muted"],
            bg=colors["surface"],
        ).pack(side="bottom", pady=(4, 0))

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
            self.service.set_fader(self.channel_index, val)
            self._last_fader_val = val
            self.fader_provenance = ValueProvenance.COMMANDED
            self._feedback(f"CH {self.channel_index}: FADER COMMANDED")
        except Exception:
            logging.getLogger(__name__).exception("Fader command failed")
            self.fader_val.set(previous)
            self._set_fader_labels(previous)
            self.fader_provenance = ValueProvenance.DISPATCH_FAILED
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
                highlightbackground=colors["cyan"] if self.is_master else colors["border"],
                highlightthickness=1,
            )

    def _restore_commanded_value(self, parameter: str) -> None:
        """Restore the last accepted software command after a failed dispatch."""
        if self.service is None:
            return
        target = "main" if self.is_master else f"ch{self.channel_index}"
        param_id = "main.balance" if self.is_master and parameter == "pan" else f"{target}.{parameter}"
        try:
            state = self.service.state_store.get_parameter(param_id)
        except Exception:
            return
        if state is None:
            return

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

    def refresh_commanded(self) -> None:
        """Show the last accepted software command (after undo/redo).

        Only parameters that were actually commanded are touched; an app default
        is never repainted as if it were a command. Never dispatches.
        """
        if self.service is None:
            return
        target = "main" if self.is_master else f"ch{self.channel_index}"
        for parameter in ("fader", "pan") if self.is_master else ("fader", "pan", "mute"):
            param_id = (
                "main.balance" if self.is_master and parameter == "pan"
                else f"{target}.{parameter}"
            )
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
        self.is_muted.set(is_muted)
        self._update_mute_ui(is_muted)
        self.mute_provenance = ValueProvenance.OBSERVED

    def destroy(self) -> None:
        for timer_id in (self._fader_after_id, self._pan_after_id):
            if timer_id is not None:
                try:
                    self.after_cancel(timer_id)
                except tk.TclError:
                    pass
        super().destroy()


class MixerConsole(tk.Frame):
    """Container holding the 7 logical input channel strips + 1 Master strip."""

    def __init__(self, master: tk.Misc, fonts: dict, service: Any = None, on_feedback: Any = None) -> None:
        super().__init__(master, bg=theme.COLORS["background"])
        self.fonts = fonts
        self.service = service
        self.on_feedback = on_feedback
        self.strips: Dict[int, ChannelStripWidget] = {}
        self.selected_target: Optional[SelectionTarget] = None
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

        self.command_log_panel = CommandLogPanel(self, self.fonts)
        self.command_log_panel.pack(
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

    def _build(self) -> None:
        colors = theme.COLORS
        spacing = theme.TOKENS

        # Console Header Banner
        banner = tk.Frame(self, bg=colors["background"])
        banner.pack(fill="x", padx=spacing["spacing_large"], pady=(spacing["spacing_medium"], spacing["spacing_small"]))

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

        # Middle band: strips on the left, the Channel Detail Inspector docks on
        # the right while a target is selected.
        self._middle = tk.Frame(self, bg=colors["background"])
        self._middle.pack(fill="both", expand=True)

        # Strips Container
        strips_container = tk.Frame(self._middle, bg=colors["background"])
        self._strips_container = strips_container
        strips_container.pack(
            side="left", fill="both", expand=True,
            padx=spacing["spacing_large"], pady=(0, spacing["spacing_large"]),
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
        self.selected_target = target
        self._show_inspector()
        self.inspector.show_target(target)

    def clear_selection(self) -> None:
        """Close the inspector and clear every selection highlight."""
        for strip in self.strips.values():
            if strip.is_selected:
                strip.set_selected(False)
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
            # Packed before the strips so the strips yield space, not the inspector.
            self.inspector.pack(
                side="right", fill="y", before=self._strips_container,
                padx=(0, spacing["spacing_large"]),
                pady=(0, spacing["spacing_large"]),
            )

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

    _UNDO_KEYS = ("<Control-z>", "<Control-Z>")
    _REDO_KEYS = ("<Control-y>", "<Control-Y>")

    def _bind_history_keys(self) -> None:
        """Ctrl+Z undo; Ctrl+Y or Ctrl+Shift+Z redo. Bound on the window, so a
        modal dialog (e.g. the +48V confirmation) keeps them from firing."""
        top = self.winfo_toplevel()
        for sequence in self._UNDO_KEYS:
            self._bind_key(top, sequence, self._on_undo_key)
        for sequence in self._REDO_KEYS:
            self._bind_key(top, sequence, self._on_redo_key)

    def _bind_key(self, top: tk.Misc, sequence: str, handler) -> None:
        funcid = top.bind(sequence, handler, add="+")
        self._key_bindings.append((sequence, funcid))

    def _on_undo_key(self, event: tk.Event) -> str:
        # Ctrl+Shift+Z arrives as an upper-case "Z" with the Shift bit set.
        if getattr(event, "state", 0) & 0x1:
            self.redo()
        else:
            self.undo()
        return "break"

    def _on_redo_key(self, _event: tk.Event) -> str:
        self.redo()
        return "break"

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
            return False
        self._refresh_strips()
        self._feedback(f"{label} COMMANDED — {self._describe(records, method)}")
        return True

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

    def _on_phantom_changed(self, channel_index: int, commanded: bool) -> None:
        strip = self.strips.get(channel_index)
        if strip is not None and not strip.is_master:
            strip.sync_phantom(commanded)

    def _on_command_log_update(self, entries: list) -> None:
        """Schedule command-log rendering on the Tk main thread."""
        try:
            snapshot = list(entries)
            self.after_idle(lambda: self.command_log_panel.set_entries(snapshot))
        except tk.TclError:
            # The widget may be closing while a worker callback is in flight.
            return

    def destroy(self) -> None:
        try:
            top = self.winfo_toplevel()
            for sequence, funcid in self._key_bindings:
                top.unbind(sequence, funcid)
        except tk.TclError:
            pass
        self._key_bindings.clear()
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
