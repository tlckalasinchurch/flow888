"""Channel Detail Inspector for the FLOW 8 Cyber Neon console.

Full Stage 2 Professional Mixer Workstation Implementation:
* Selection target: logical input strips 1..7 or Main L/R master bus;
* Channel Overview & CueAir acoustic preset launcher;
* Tabbed pro-console navigation:
    - [PREAMP & +48V]: Phantom power (MIC 1 & 2), Gain preview slider;
    - [4-BAND EQ]: 4-Band Parametric EQ with Reset Flat (0 dB);
    - [HPF & COMP]: Low Cut filter (20-600 Hz) & 1-Knob Dynamics Compressor;
    - [AUX SENDS]: 4 Aux Sends (Mon 1, Mon 2, FX 1, FX 2);
* Visual parameter provenance badges (OBS, CMD, UNSYNC, FAIL, N/A);
* Strict adherence to zero-clipping at 1366x768 and 1600x900 viewport layouts.

Architecture: this module is presentation only. Every command routes
UI -> Flow8Service and through the verified parameter engine and command
boundary.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from flow8.domain_model import LOGICAL_CHANNELS
from flow8.parameter_mapping import (
    compressor_midi_to_percent,
    eq_midi_to_db,
    fader_midi_to_db,
    gain_midi_to_db,
    low_cut_midi_to_hz,
)
from flow8.state_model import ParameterProvenance
from flow8.ui import theme
from flow8.ui.components.controls import (
    HorizontalSlider,
    ProvenanceBadge,
    UnipolarSlider,
)
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


def _dispatch_service(service: Any, method_name: str, *args, **kwargs) -> Any:
    """Invoke a service method safely via dynamic lookup to enforce architectural separation."""
    if service is None:
        return None
    method = getattr(service, method_name, None)
    if callable(method):
        return method(*args, **kwargs)
    return None


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

    EQ_BANDS = [
        ("low", "LOW (80 Hz)", "cyan_soft"),
        ("low_mid", "LOW-MID (400 Hz)", "cyan_soft"),
        ("hi_mid", "HI-MID (2.5 kHz)", "cyan_soft"),
        ("hi", "HIGH (10 kHz)", "cyan_soft"),
    ]

    AUX_SENDS = [
        ("mon1", "MON 1 (STAGE)", "lime"),
        ("mon2", "MON 2 (IEM)", "lime"),
        ("fx1", "FX 1 (REVERB)", "purple_soft"),
        ("fx2", "FX 2 (DELAY)", "purple_soft"),
    ]

    TAB_PREAMP = "preamp"
    TAB_EQ = "eq"
    TAB_DYNAMICS = "dynamics"
    TAB_SENDS = "sends"

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
        self._is_updating_controls = False
        self.current_tab = self.TAB_PREAMP

        # phantom state
        self.phantom_available = False
        self._phantom_dialog: Optional[PhantomPowerConfirmationDialog] = None
        self._phantom_token: Optional[object] = None
        self._phantom_busy = False

        # gain preview state
        self.gain_available = False
        self.gain_gate: Optional[AnalogGainSafetyGate] = None
        self._gain_baseline = 0

        # Debounce and timer trackers
        self._pending_eq: Dict[str, int] = {}
        self._eq_after_ids: Dict[str, Optional[str]] = {}
        self._pending_low_cut: Optional[int] = None
        self._low_cut_after_id: Optional[str] = None
        self._pending_comp: Optional[int] = None
        self._comp_after_id: Optional[str] = None
        self._pending_sends: Dict[str, int] = {}
        self._send_after_ids: Dict[str, Optional[str]] = {}

        # StringVars
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

        # EQ Variables
        self.eq_vars: Dict[str, tk.IntVar] = {
            band: tk.IntVar(value=64) for band, _, _ in self.EQ_BANDS
        }
        self.eq_readouts: Dict[str, tk.StringVar] = {
            band: tk.StringVar(value="0.0 dB · raw 64") for band, _, _ in self.EQ_BANDS
        }

        # Low Cut Variables
        self.low_cut_var = tk.IntVar(value=0)
        self.low_cut_readout = tk.StringVar(value="20 Hz (BYPASS) · raw 0")

        # Compressor Variables
        self.comp_var = tk.IntVar(value=0)
        self.comp_readout = tk.StringVar(value="0% (BYPASS) · raw 0")

        # Aux Sends Variables
        self.send_vars: Dict[str, tk.IntVar] = {
            target: tk.IntVar(value=0) for target, _, _ in self.AUX_SENDS
        }
        self.send_readouts: Dict[str, tk.StringVar] = {
            target: tk.StringVar(value="-inf dB · raw 0") for target, _, _ in self.AUX_SENDS
        }

        # Text wrapping
        self._wrap_labels: list[tk.Label] = []
        self.bind("<Configure>", self._rewrap)

        self._build()

    def _rewrap(self, _event: Optional[tk.Event] = None) -> None:
        wrap = max(120, self.winfo_width() - 28)
        for label in self._wrap_labels:
            try:
                label.configure(wraplength=wrap, justify="left")
            except tk.TclError:
                pass

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

        # 1. Header row
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
                    fg="text", fill="x", pady=(4, 0))
        self._label(self.body, textvariable=self.subtitle_var, font="caption",
                    fg="text_muted", fill="x")

        # Preset Launcher Button (CueAir integration)
        self.preset_button = tk.Button(
            self.body,
            text="★ ACOUSTIC PRESETS (CueAir)",
            font=self.fonts["eyebrow"],
            bg=colors["purple_soft"],
            fg=colors["background"],
            activebackground=colors["purple"],
            activeforeground=colors["text"],
            disabledforeground=colors["text_muted"],
            bd=0,
            relief="flat",
            cursor="hand2",
            pady=3,
            state="disabled",
            command=self._on_open_presets,
        )
        self.preset_button.pack(fill="x", pady=(4, 4))

        # Tab Navigation Bar
        self._build_tab_bar()
        self._divider()

        # Tab Content Area
        self.tab_container = tk.Frame(self.body, bg=colors["surface"])
        self.tab_container.pack(fill="both", expand=True)

        # Preamp Tab Frame
        self.preamp_tab = tk.Frame(self.tab_container, bg=colors["surface"])
        self._build_preamp_tab()

        # EQ Tab Frame
        self.eq_tab = tk.Frame(self.tab_container, bg=colors["surface"])
        self._build_eq_tab()

        # Dynamics Tab Frame
        self.dyn_tab = tk.Frame(self.tab_container, bg=colors["surface"])
        self._build_dyn_tab()

        # Sends Tab Frame
        self.sends_tab = tk.Frame(self.tab_container, bg=colors["surface"])
        self._build_sends_tab()

        # Initial Tab Display
        self.show_tab(self.TAB_PREAMP)

        self._divider()

        # Footer & Status
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
        self.error_label.pack(fill="x", pady=(2, 0))
        self._wrap_labels.append(self.error_label)

    def _build_tab_bar(self) -> None:
        colors = theme.COLORS
        self.tab_bar = tk.Frame(self.body, bg=colors["surface"])
        self.tab_bar.pack(fill="x", pady=(0, 2))

        self.tab_buttons: Dict[str, tk.Button] = {}
        tab_defs = [
            (self.TAB_PREAMP, "PREAMP", "warning"),
            (self.TAB_EQ, "EQ", "cyan_soft"),
            (self.TAB_DYNAMICS, "DYN", "purple_soft"),
            (self.TAB_SENDS, "SENDS", "lime"),
        ]
        for key, label, accent in tab_defs:
            btn = tk.Button(
                self.tab_bar,
                text=label,
                font=self.fonts["caption"],
                bg=colors["surface_alt"],
                fg=colors["text_muted"],
                activebackground=colors["surface_hover"],
                activeforeground=colors[accent],
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=4,
                pady=2,
                command=lambda k=key: self.show_tab(k),
            )
            btn.pack(side="left", expand=True, fill="x", padx=1)
            self.tab_buttons[key] = btn

    def show_tab(self, tab_key: str) -> None:
        """Switch the visible inspector subsection tab."""
        self.current_tab = tab_key
        colors = theme.COLORS
        tab_frames = {
            self.TAB_PREAMP: self.preamp_tab,
            self.TAB_EQ: self.eq_tab,
            self.TAB_DYNAMICS: self.dyn_tab,
            self.TAB_SENDS: self.sends_tab,
        }
        for k, frame in tab_frames.items():
            if k == tab_key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        for k, btn in self.tab_buttons.items():
            if k == tab_key:
                btn.configure(
                    bg=colors["surface_hover"],
                    fg=colors["cyan"] if k != self.TAB_PREAMP else colors["warning"],
                )
            else:
                btn.configure(bg=colors["surface_alt"], fg=colors["text_muted"])

    def _build_preamp_tab(self) -> None:
        colors = theme.COLORS
        # +48V phantom power
        self._label(self.preamp_tab, text="+48V PHANTOM POWER", font="eyebrow",
                    fg="warning", fill="x")
        status = tk.Frame(self.preamp_tab, bg=colors["surface"])
        status.pack(fill="x", pady=(2, 0))
        self._status_cell(status, "CMD", self.phantom_cmd_var, "cyan_soft")
        self._status_cell(status, "OBS", self.phantom_obs_var, "purple_soft")
        tk.Label(
            status, textvariable=self.phantom_sync_var, font=self.fonts["caption"],
            fg=colors["warning"], bg=colors["surface_alt"], padx=5, pady=1,
        ).pack(side="right")

        self.phantom_button = tk.Button(
            self.preamp_tab,
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
            pady=4,
            command=self._on_phantom_button,
        )
        self.phantom_button.pack(fill="x", pady=(4, 0))
        self._label(self.preamp_tab, textvariable=self.phantom_note_var, font="caption",
                    fg="text_muted", fill="x", pady=(2, 0))

        tk.Frame(self.preamp_tab, bg=colors["border"], height=1).pack(fill="x", pady=4)

        # Preamp gain preview
        self._label(self.preamp_tab, text="ANALOG GAIN · PREVIEW ONLY", font="eyebrow",
                    fg="warning", fill="x")
        self._gain_cmd_label = self._label(
            self.preamp_tab, textvariable=self.gain_cmd_var, font="caption",
            fg="text_secondary", fill="x", pady=(2, 0),
        )

        self._gain_controls = tk.Frame(self.preamp_tab, bg=colors["surface"])
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
                    font="caption", fg="text_muted", fill="x", pady=(2, 0)
                    ).configure(wraplength=280, justify="left")
        self._label(self.preamp_tab, textvariable=self.gain_note_var, font="caption",
                    fg="text_muted", fill="x")

    def _build_eq_tab(self) -> None:
        colors = theme.COLORS
        hdr_row = tk.Frame(self.eq_tab, bg=colors["surface"])
        hdr_row.pack(fill="x")
        self._label(hdr_row, text="4-BAND PARAMETRIC EQ", font="eyebrow", fg="cyan_soft", side="left")
        self.eq_badge = ProvenanceBadge(hdr_row, font=self.fonts["caption"], provenance="UNSYNCED")
        self.eq_badge.pack(side="right")

        self.eq_note_var = tk.StringVar(value="")
        self._eq_note_label = self._label(
            self.eq_tab, textvariable=self.eq_note_var, font="caption", fg="text_muted",
            fill="x", pady=(2, 0),
        )

        self._eq_controls = tk.Frame(self.eq_tab, bg=colors["surface"])
        self.eq_reset_btn = tk.Button(
            self._eq_controls,
            text="RESET FLAT (0 dB)",
            font=self.fonts["eyebrow"],
            bg=colors["surface_alt"],
            fg=colors["cyan_soft"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["cyan"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=2,
            command=self.reset_eq_flat,
        )
        self.eq_reset_btn.pack(fill="x", pady=(2, 4))

        self.eq_sliders: Dict[str, HorizontalSlider] = {}
        for band_key, band_title, accent in self.EQ_BANDS:
            band_frame = tk.Frame(self._eq_controls, bg=colors["surface"])
            band_frame.pack(fill="x", pady=1)

            top_row = tk.Frame(band_frame, bg=colors["surface"])
            top_row.pack(fill="x")
            tk.Label(
                top_row, text=band_title, font=self.fonts["caption"],
                fg=colors["text_secondary"], bg=colors["surface"],
            ).pack(side="left")
            tk.Label(
                top_row, textvariable=self.eq_readouts[band_key], font=self.fonts["status_key"],
                fg=colors[accent], bg=colors["surface"],
            ).pack(side="right")

            slider = HorizontalSlider(
                band_frame,
                variable=self.eq_vars[band_key],
                command=lambda val, b=band_key: self._on_eq_drag(b, val),
                default=64,
                accent=colors[accent],
            )
            slider.pack(fill="x", pady=(1, 1))
            self.eq_sliders[band_key] = slider

    def _build_dyn_tab(self) -> None:
        colors = theme.COLORS
        # Low Cut section
        hdr_lc = tk.Frame(self.dyn_tab, bg=colors["surface"])
        hdr_lc.pack(fill="x")
        self._label(hdr_lc, text="LOW CUT / HPF (20–600 Hz)", font="eyebrow", fg="warning", side="left")
        self.low_cut_badge = ProvenanceBadge(hdr_lc, font=self.fonts["caption"], provenance="UNSYNCED")
        self.low_cut_badge.pack(side="right")

        self.low_cut_note_var = tk.StringVar(value="")
        self._low_cut_note_label = self._label(
            self.dyn_tab, textvariable=self.low_cut_note_var, font="caption", fg="text_muted",
            fill="x", pady=(1, 0),
        )

        self._low_cut_controls = tk.Frame(self.dyn_tab, bg=colors["surface"])
        top_row_lc = tk.Frame(self._low_cut_controls, bg=colors["surface"])
        top_row_lc.pack(fill="x", pady=(2, 0))
        tk.Label(
            top_row_lc, textvariable=self.low_cut_readout, font=self.fonts["status_key"],
            fg=colors["warning"], bg=colors["surface"],
        ).pack(side="left")
        self.low_cut_bypass_btn = tk.Button(
            top_row_lc,
            text="BYPASS (20 Hz)",
            font=self.fonts["caption"],
            bg=colors["surface_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["text"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.bypass_low_cut,
        )
        self.low_cut_bypass_btn.pack(side="right")

        self.low_cut_slider = UnipolarSlider(
            self._low_cut_controls,
            variable=self.low_cut_var,
            command=self._on_low_cut_drag,
            default=0,
            accent=colors["warning"],
        )
        self.low_cut_slider.pack(fill="x", pady=(2, 4))
        self._low_cut_controls.pack(fill="x")

        tk.Frame(self.dyn_tab, bg=colors["border"], height=1).pack(fill="x", pady=6)

        # Compressor section
        hdr_cp = tk.Frame(self.dyn_tab, bg=colors["surface"])
        hdr_cp.pack(fill="x")
        self._label(hdr_cp, text="1-KNOB COMPRESSOR (0–100%)", font="eyebrow", fg="purple_soft", side="left")
        self.comp_badge = ProvenanceBadge(hdr_cp, font=self.fonts["caption"], provenance="UNSYNCED")
        self.comp_badge.pack(side="right")

        self.comp_note_var = tk.StringVar(value="")
        self._comp_note_label = self._label(
            self.dyn_tab, textvariable=self.comp_note_var, font="caption", fg="text_muted",
            fill="x", pady=(1, 0),
        )

        self._comp_controls = tk.Frame(self.dyn_tab, bg=colors["surface"])
        top_row_cp = tk.Frame(self._comp_controls, bg=colors["surface"])
        top_row_cp.pack(fill="x", pady=(2, 0))
        tk.Label(
            top_row_cp, textvariable=self.comp_readout, font=self.fonts["status_key"],
            fg=colors["purple_soft"], bg=colors["surface"],
        ).pack(side="left")
        self.comp_bypass_btn = tk.Button(
            top_row_cp,
            text="BYPASS (0%)",
            font=self.fonts["caption"],
            bg=colors["surface_alt"],
            fg=colors["text_secondary"],
            activebackground=colors["surface_hover"],
            activeforeground=colors["text"],
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.bypass_comp,
        )
        self.comp_bypass_btn.pack(side="right")

        self.comp_slider = UnipolarSlider(
            self._comp_controls,
            variable=self.comp_var,
            command=self._on_comp_drag,
            default=0,
            accent=colors["purple_soft"],
        )
        self.comp_slider.pack(fill="x", pady=(2, 2))
        self._comp_controls.pack(fill="x")

    def _build_sends_tab(self) -> None:
        colors = theme.COLORS
        hdr_row = tk.Frame(self.sends_tab, bg=colors["surface"])
        hdr_row.pack(fill="x")
        self._label(hdr_row, text="AUX SENDS (MON & FX)", font="eyebrow", fg="lime", side="left")
        self.send_badge = ProvenanceBadge(hdr_row, font=self.fonts["caption"], provenance="UNSYNCED")
        self.send_badge.pack(side="right")

        self.send_note_var = tk.StringVar(value="")
        self._send_note_label = self._label(
            self.sends_tab, textvariable=self.send_note_var, font="caption", fg="text_muted",
            fill="x", pady=(2, 0),
        )

        self._send_controls = tk.Frame(self.sends_tab, bg=colors["surface"])
        self.send_sliders: Dict[str, UnipolarSlider] = {}
        for target_key, target_title, accent in self.AUX_SENDS:
            send_frame = tk.Frame(self._send_controls, bg=colors["surface"])
            send_frame.pack(fill="x", pady=2)

            top_row = tk.Frame(send_frame, bg=colors["surface"])
            top_row.pack(fill="x")
            tk.Label(
                top_row, text=target_title, font=self.fonts["caption"],
                fg=colors["text_secondary"], bg=colors["surface"],
            ).pack(side="left")
            tk.Label(
                top_row, textvariable=self.send_readouts[target_key], font=self.fonts["status_key"],
                fg=colors[accent], bg=colors["surface"],
            ).pack(side="right")

            slider = UnipolarSlider(
                send_frame,
                variable=self.send_vars[target_key],
                command=lambda val, t=target_key: self._on_send_drag(t, val),
                default=0,
                accent=colors[accent],
            )
            slider.pack(fill="x", pady=(1, 2))
            self.send_sliders[target_key] = slider
        self._send_controls.pack(fill="x")

    def _divider(self) -> None:
        tk.Frame(self.body, bg=theme.COLORS["border"], height=1).pack(fill="x", pady=4)

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
        self.target = target
        self.error_var.set("")
        self._attach()

        if target.kind == "main":
            self.title_var.set("MAIN L/R")
            self.subtitle_var.set("Master output bus · separate from the 7 input strips")
            self.preset_button.configure(state="disabled")
            index = None
        else:
            index = target.index
            spec = LOGICAL_CHANNELS[index]
            self.title_var.set(f"CHANNEL {index:02d}")
            self.subtitle_var.set(f"{spec.name} · MIDI CH {spec.midi_channel}")
            self.preset_button.configure(state="normal")

        self._configure_phantom(index)
        self._configure_gain(index)
        self._configure_eq(index)
        self._configure_low_cut(index)
        self._configure_comp(index)
        self._configure_sends(index)
        self._refresh_provenance_badges()

    def _on_open_presets(self) -> None:
        if self.target is None or self.target.kind != "input" or self.target.index is None:
            return
        from flow8.ui.components.preset_picker import PresetPickerDialog
        spec = LOGICAL_CHANNELS[self.target.index]
        PresetPickerDialog(
            master=self.winfo_toplevel(),
            fonts=self.fonts,
            channel_index=self.target.index,
            channel_name=spec.name,
            service=self._service,
            on_applied=lambda _preset_id: self._refresh_if_attached(),
        )

    def clear(self) -> None:
        """Forget the target, cancel any pending dialog, release subscriptions."""
        self._dismiss_dialog()
        self.detach()
        self.target = None
        self.preset_button.configure(state="disabled")
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
            self._refresh_eq_command()
            self._refresh_low_cut_command()
            self._refresh_comp_command()
            self._refresh_sends_command()
            self._refresh_provenance_badges()
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
        """Request a +48V change for *channel_index* (explicit, never inferred)."""
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
        if self.gain_gate is None:
            return
        raw = max(0, min(127, int(value)))
        self.gain_gate.stage_preview(gain_midi_to_db(raw))
        self._update_gain_text(raw)

    def cancel_gain_preview(self) -> None:
        if self.gain_gate is None:
            return
        self.gain_gate.cancel_staged()
        self.gain_preview_var.set(self._gain_baseline)
        self._update_gain_text(self._gain_baseline)

    # -- 4-Band Parametric EQ -------------------------------------------------

    def _configure_eq(self, index: Optional[int]) -> None:
        if index is None or not (1 <= index <= 7):
            self._eq_controls.pack_forget()
            self.eq_note_var.set("N/A — 4-BAND EQ NOT SUPPORTED ON MAIN L/R")
            self.eq_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            return

        self.eq_note_var.set("")
        self._refresh_eq_command()
        self._eq_controls.pack(fill="x", after=self._eq_note_label, pady=(2, 0))

    def _refresh_eq_command(self) -> None:
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 7):
            return

        self._is_updating_controls = True
        try:
            for band_key, _, _ in self.EQ_BANDS:
                state = self._state(f"ch{target.index}.eq_{band_key}")
                raw = getattr(state, "commanded_raw_midi", None) if state else None
                if raw is None and state is not None:
                    raw = getattr(state, "raw_midi_value", None)
                val = 64 if raw is None else int(raw)
                self.eq_vars[band_key].set(val)
                db = eq_midi_to_db(val)
                self.eq_readouts[band_key].set(f"{db:+.1f} dB · raw {val}")
        finally:
            self._is_updating_controls = False

    def _on_eq_drag(self, band: str, val_str: str) -> None:
        if self._is_updating_controls or self.target is None or self.target.kind != "input":
            return
        raw = max(0, min(127, int(val_str)))
        db = eq_midi_to_db(raw)
        self.eq_readouts[band].set(f"{db:+.1f} dB · raw {raw}")
        self._pending_eq[band] = raw
        if self._eq_after_ids.get(band) is None:
            self._eq_after_ids[band] = self.after(30, lambda b=band: self._flush_eq(b))

    def _flush_eq(self, band: str) -> None:
        self._eq_after_ids[band] = None
        if band not in self._pending_eq or self.target is None or self.target.kind != "input":
            return
        val = self._pending_eq.pop(band)
        if self._service is None:
            return
        try:
            _dispatch_service(self._service, "set_eq_band", self.target.index, band, val, unit="raw")
            self._refresh_provenance_badges()
        except Exception as error:
            logger.exception("EQ %s command failed: %s", band, error)
            self.error_var.set(f"EQ {band.upper()} FAILED — {error}")

    def reset_eq_flat(self) -> None:
        """Reset all 4 EQ bands to 0 dB flat (raw 64)."""
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 7):
            return
        for band_key, _, _ in self.EQ_BANDS:
            if self._service is not None:
                try:
                    _dispatch_service(self._service, "set_eq_band", target.index, band_key, 64, unit="raw")
                except Exception as error:
                    logger.exception("Reset EQ flat failed on %s: %s", band_key, error)
            self.eq_vars[band_key].set(64)
            self.eq_readouts[band_key].set("0.0 dB · raw 64")
        self._refresh_provenance_badges()

    # -- Low Cut / HPF --------------------------------------------------------

    def _configure_low_cut(self, index: Optional[int]) -> None:
        if index is None or not (1 <= index <= 4):
            self._low_cut_controls.pack_forget()
            self.low_cut_note_var.set("N/A — LOW CUT AVAILABLE ON CH 1–4 ONLY")
            self.low_cut_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            return

        self.low_cut_note_var.set("")
        self._refresh_low_cut_command()
        self._low_cut_controls.pack(fill="x")

    def _refresh_low_cut_command(self) -> None:
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 4):
            return

        self._is_updating_controls = True
        try:
            state = self._state(f"ch{target.index}.low_cut")
            raw = getattr(state, "commanded_raw_midi", None) if state else None
            if raw is None and state is not None:
                raw = getattr(state, "raw_midi_value", None)
            val = 0 if raw is None else int(raw)
            self.low_cut_var.set(val)
            hz = low_cut_midi_to_hz(val)
            bypass_text = " (BYPASS)" if val == 0 else ""
            self.low_cut_readout.set(f"{hz:.0f} Hz{bypass_text} · raw {val}")
        finally:
            self._is_updating_controls = False

    def _on_low_cut_drag(self, val_str: str) -> None:
        if self._is_updating_controls or self.target is None or self.target.kind != "input":
            return
        raw = max(0, min(127, int(val_str)))
        hz = low_cut_midi_to_hz(raw)
        bypass_text = " (BYPASS)" if raw == 0 else ""
        self.low_cut_readout.set(f"{hz:.0f} Hz{bypass_text} · raw {raw}")
        self._pending_low_cut = raw
        if self._low_cut_after_id is None:
            self._low_cut_after_id = self.after(30, self._flush_low_cut)

    def _flush_low_cut(self) -> None:
        self._low_cut_after_id = None
        if self._pending_low_cut is None or self.target is None or self.target.kind != "input":
            return
        val = self._pending_low_cut
        self._pending_low_cut = None
        if self._service is None:
            return
        try:
            _dispatch_service(self._service, "set_low_cut", self.target.index, val, unit="raw")
            self._refresh_provenance_badges()
        except Exception as error:
            logger.exception("Low Cut command failed: %s", error)
            self.error_var.set(f"LOW CUT FAILED — {error}")

    def bypass_low_cut(self) -> None:
        """Bypass Low Cut filter (set to 20 Hz minimum, raw 0)."""
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 4):
            return
        if self._service is not None:
            try:
                _dispatch_service(self._service, "set_low_cut", target.index, 0, unit="raw")
            except Exception as error:
                logger.exception("Bypass Low Cut failed: %s", error)
        self.low_cut_var.set(0)
        self.low_cut_readout.set("20 Hz (BYPASS) · raw 0")
        self._refresh_provenance_badges()

    # -- 1-Knob Dynamics Compressor -------------------------------------------

    def _configure_comp(self, index: Optional[int]) -> None:
        if index is None or not (1 <= index <= 4):
            self._comp_controls.pack_forget()
            self.comp_note_var.set("N/A — COMPRESSOR AVAILABLE ON CH 1–4 ONLY")
            self.comp_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            return

        self.comp_note_var.set("")
        self._refresh_comp_command()
        self._comp_controls.pack(fill="x")

    def _refresh_comp_command(self) -> None:
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 4):
            return

        self._is_updating_controls = True
        try:
            state = self._state(f"ch{target.index}.compressor")
            raw = getattr(state, "commanded_raw_midi", None) if state else None
            if raw is None and state is not None:
                raw = getattr(state, "raw_midi_value", None)
            val = 0 if raw is None else int(raw)
            self.comp_var.set(val)
            pct = compressor_midi_to_percent(val)
            bypass_text = " (BYPASS)" if val == 0 else ""
            self.comp_readout.set(f"{pct:.0f}%{bypass_text} · raw {val}")
        finally:
            self._is_updating_controls = False

    def _on_comp_drag(self, val_str: str) -> None:
        if self._is_updating_controls or self.target is None or self.target.kind != "input":
            return
        raw = max(0, min(100, int(val_str)))
        pct = compressor_midi_to_percent(raw)
        bypass_text = " (BYPASS)" if raw == 0 else ""
        self.comp_readout.set(f"{pct:.0f}%{bypass_text} · raw {raw}")
        self._pending_comp = raw
        if self._comp_after_id is None:
            self._comp_after_id = self.after(30, self._flush_comp)

    def _flush_comp(self) -> None:
        self._comp_after_id = None
        if self._pending_comp is None or self.target is None or self.target.kind != "input":
            return
        val = self._pending_comp
        self._pending_comp = None
        if self._service is None:
            return
        try:
            _dispatch_service(self._service, "set_compressor", self.target.index, val, unit="raw")
            self._refresh_provenance_badges()
        except Exception as error:
            logger.exception("Compressor command failed: %s", error)
            self.error_var.set(f"COMPRESSOR FAILED — {error}")

    def bypass_comp(self) -> None:
        """Bypass Dynamics Compressor (set to 0%, raw 0)."""
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 4):
            return
        if self._service is not None:
            try:
                _dispatch_service(self._service, "set_compressor", target.index, 0, unit="raw")
            except Exception as error:
                logger.exception("Bypass Compressor failed: %s", error)
        self.comp_var.set(0)
        self.comp_readout.set("0% (BYPASS) · raw 0")
        self._refresh_provenance_badges()

    # -- Aux Sends (Mon 1, Mon 2, FX 1, FX 2) --------------------------------

    def _configure_sends(self, index: Optional[int]) -> None:
        if index is None or not (1 <= index <= 7):
            self._send_controls.pack_forget()
            self.send_note_var.set("N/A — AUX SENDS NOT SUPPORTED ON MAIN L/R")
            self.send_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            return

        self.send_note_var.set("")
        self._refresh_sends_command()
        self._send_controls.pack(fill="x")

    def _refresh_sends_command(self) -> None:
        target = self.target
        if target is None or target.kind != "input" or not (1 <= target.index <= 7):
            return

        self._is_updating_controls = True
        try:
            for target_key, _, _ in self.AUX_SENDS:
                state = self._state(f"ch{target.index}.send_{target_key}")
                raw = getattr(state, "commanded_raw_midi", None) if state else None
                if raw is None and state is not None:
                    raw = getattr(state, "raw_midi_value", None)
                val = 0 if raw is None else int(raw)
                self.send_vars[target_key].set(val)
                db_str = "-inf dB" if val == 0 else f"{fader_midi_to_db(val):+.1f} dB"
                self.send_readouts[target_key].set(f"{db_str} · raw {val}")
        finally:
            self._is_updating_controls = False

    def _on_send_drag(self, target_name: str, val_str: str) -> None:
        if self._is_updating_controls or self.target is None or self.target.kind != "input":
            return
        raw = max(0, min(127, int(val_str)))
        db_str = "-inf dB" if raw == 0 else f"{fader_midi_to_db(raw):+.1f} dB"
        self.send_readouts[target_name].set(f"{db_str} · raw {raw}")
        self._pending_sends[target_name] = raw
        if self._send_after_ids.get(target_name) is None:
            self._send_after_ids[target_name] = self.after(
                30, lambda t=target_name: self._flush_send(t)
            )

    def _flush_send(self, target_name: str) -> None:
        self._send_after_ids[target_name] = None
        if target_name not in self._pending_sends or self.target is None or self.target.kind != "input":
            return
        val = self._pending_sends.pop(target_name)
        if self._service is None:
            return
        try:
            _dispatch_service(self._service, "set_send", self.target.index, target_name, val, unit="raw")
            self._refresh_provenance_badges()
        except Exception as error:
            logger.exception("Send %s command failed: %s", target_name, error)
            self.error_var.set(f"SEND {target_name.upper()} FAILED — {error}")

    # -- Provenance Badges ----------------------------------------------------

    def _refresh_provenance_badges(self) -> None:
        target = self.target
        if target is None or target.kind != "input":
            self.eq_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            self.low_cut_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            self.comp_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            self.send_badge.update_provenance(ParameterProvenance.UNSUPPORTED)
            return

        ch = target.index
        # EQ
        eq_states = [self._state(f"ch{ch}.eq_{b}") for b, _, _ in self.EQ_BANDS]
        eq_prov = self._aggregate_provenance(eq_states)
        self.eq_badge.update_provenance(eq_prov)

        # Low Cut
        if 1 <= ch <= 4:
            lc_state = self._state(f"ch{ch}.low_cut")
            self.low_cut_badge.update_provenance(
                getattr(lc_state, "provenance", ParameterProvenance.UNSYNCED)
            )
        else:
            self.low_cut_badge.update_provenance(ParameterProvenance.UNSUPPORTED)

        # Compressor
        if 1 <= ch <= 4:
            comp_state = self._state(f"ch{ch}.compressor")
            self.comp_badge.update_provenance(
                getattr(comp_state, "provenance", ParameterProvenance.UNSYNCED)
            )
        else:
            self.comp_badge.update_provenance(ParameterProvenance.UNSUPPORTED)

        # Sends
        send_states = [self._state(f"ch{ch}.send_{t}") for t, _, _ in self.AUX_SENDS]
        send_prov = self._aggregate_provenance(send_states)
        self.send_badge.update_provenance(send_prov)

    @staticmethod
    def _aggregate_provenance(states: list) -> ParameterProvenance:
        valid_states = [s for s in states if s is not None]
        if not valid_states:
            return ParameterProvenance.UNSYNCED
        provs = [getattr(s, "provenance", ParameterProvenance.UNSYNCED) for s in valid_states]
        if ParameterProvenance.DISPATCH_FAILED in provs:
            return ParameterProvenance.DISPATCH_FAILED
        if ParameterProvenance.OBSERVED in provs:
            return ParameterProvenance.OBSERVED
        if ParameterProvenance.COMMANDED in provs:
            return ParameterProvenance.COMMANDED
        return ParameterProvenance.UNSYNCED

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
        for aid in list(self._eq_after_ids.values()) + [self._low_cut_after_id, self._comp_after_id] + list(self._send_after_ids.values()):
            if aid is not None:
                try:
                    self.after_cancel(aid)
                except tk.TclError:
                    pass
        super().destroy()
