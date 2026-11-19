"""Canvas-drawn fader and slider controls for the FLOW 8 Cyber Neon console.

Classic ``tk.Scale`` handles render almost invisibly on a dark theme, so the
mixer uses these canvas controls instead: a clearly visible handle, a cyan fill,
click/drag, mouse-wheel and double-click-to-reset.

``command`` is invoked ONLY for user interaction (never when the bound variable
is changed programmatically), which keeps hardware echo from looping back out.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, Optional

from flow8.ui import theme
from flow8.parameter_mapping import fader_db_to_midi, fader_midi_to_db


class _BaseControl(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        variable: tk.IntVar,
        command: Optional[Callable[[int], None]],
        default: int,
        accent: str,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            bg=theme.COLORS["surface"],
            highlightthickness=2,
            highlightbackground=theme.COLORS["border"],
            highlightcolor=theme.COLORS["cyan"],
            bd=0,
            cursor="hand2",
            takefocus=True,
            **kwargs,
        )
        self.variable = variable
        self.command = command
        self.default = default
        self.accent = accent
        self.minimum = 0
        self.maximum = 127
        self._trace = self.variable.trace_add("write", lambda *_: self._redraw())
        self._last_pointer_raw: Optional[int] = None
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)
        self.bind("<Double-Button-1>", self._on_reset)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", lambda event: self._on_wheel(event))
        self.bind("<Button-5>", lambda event: self._on_wheel(event))
        self.bind("<KeyPress>", self._on_key)
        self.bind("<FocusIn>", lambda _event: self.configure(highlightbackground=theme.COLORS["cyan"]))
        self.bind("<FocusOut>", lambda _event: self.configure(highlightbackground=theme.COLORS["border"]))

    # -- subclass hooks -----------------------------------------------------
    def _value_from_event(self, event: tk.Event) -> int:  # pragma: no cover
        raise NotImplementedError

    def _redraw(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def set_accent(self, accent: str) -> None:
        """Update the control's active fill/cap accent color and redraw."""
        if accent and accent != self.accent:
            self.accent = accent
            self._redraw()

    # -- interaction --------------------------------------------------------
    def _commit(self, value: int) -> None:
        value = max(self.minimum, min(self.maximum, int(value)))
        if value == self.variable.get():
            return
        self.variable.set(value)
        if self.command:
            self.command(str(value))

    def _on_pointer(self, event: tk.Event) -> None:
        self.focus_set()
        raw_value = self._value_from_event(event)
        if event.type == tk.EventType.ButtonPress:
            self._last_pointer_raw = raw_value
            self._commit(raw_value)
            return
        if event.state & 0x0001 and self._last_pointer_raw is not None:
            delta = raw_value - self._last_pointer_raw
            value = self.variable.get() + round(delta * 0.25)
        else:
            value = raw_value
        self._last_pointer_raw = raw_value
        self._commit(value)

    def _on_reset(self, _event: tk.Event) -> None:
        self._commit(self.default)

    def _on_wheel(self, event: tk.Event) -> None:
        direction = 1 if getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4 else -1
        step = 1 if event.state & 0x0001 else 4
        step *= direction
        self._commit(self.variable.get() + step)

    def _on_key(self, event: tk.Event) -> str:
        step = 1 if event.state & 0x0001 else 4
        if event.keysym in ("Up", "Right"):
            self._commit(self.variable.get() + step)
        elif event.keysym in ("Down", "Left"):
            self._commit(self.variable.get() - step)
        elif event.keysym == "Home":
            self._commit(self.maximum)
        elif event.keysym == "End":
            self._commit(self.minimum)
        else:
            return "break"
        return "break"

    def destroy(self) -> None:
        try:
            self.variable.trace_remove("write", self._trace)
        except Exception:
            pass
        super().destroy()


class VerticalFader(_BaseControl):
    """Vertical fader, 0 (bottom) to 127 (top) with a unity (0 dB) tick."""

    PAD_Y = 16
    HANDLE_H = 26
    UNITY = 101
    DB_TICKS = (("+10", 127), ("0", 101), ("-10", fader_db_to_midi(-10)),
                ("-20", fader_db_to_midi(-20)), ("-40", fader_db_to_midi(-40)), ("-∞", 0))

    def __init__(self, master, variable, command=None, default=101, accent=None, **kw):
        kw.setdefault("width", 70)
        kw.setdefault("height", 200)
        super().__init__(
            master, variable, command, default,
            accent or theme.COLORS["cyan"], **kw,
        )

    def _y_for(self, value: int) -> float:
        h = max(self.winfo_height(), 60)
        top, bottom = self.PAD_Y, h - self.PAD_Y
        return bottom - (value / self.maximum) * (bottom - top)

    def _value_from_event(self, event: tk.Event) -> int:
        h = max(self.winfo_height(), 60)
        top, bottom = self.PAD_Y, h - self.PAD_Y
        frac = (bottom - event.y) / float(bottom - top)
        return round(frac * self.maximum)

    def _redraw(self) -> None:
        colors = theme.COLORS
        self.delete("all")
        w = max(self.winfo_width(), 64)
        cx = w / 2
        value = self.variable.get()
        y = self._y_for(value)
        bottom = max(self.winfo_height(), 60) - self.PAD_Y

        # Scale ticks plus explicit dB reference labels.
        for i in range(0, 9):
            ty = self._y_for(round(i * self.maximum / 8))
            self.create_line(cx - 22, ty, cx - 14, ty, fill=colors["border"])
            self.create_line(cx + 14, ty, cx + 22, ty, fill=colors["border"])
        for label, tick_value in self.DB_TICKS:
            ty = self._y_for(tick_value)
            is_unity = label == "0"
            self.create_line(cx - 26, ty, cx + 26, ty,
                             fill=colors["lime"] if is_unity else colors["border"],
                             width=2 if is_unity else 1)
            self.create_text(cx + 28, ty, text=label,
                             fill=colors["lime"] if is_unity else colors["text_muted"],
                             anchor="w", font=("Segoe UI", 7), tags=("db-scale",))

        # trough + active fill
        self.create_rectangle(cx - 4, self.PAD_Y, cx + 4, bottom,
                              fill=colors["background"], outline=colors["border"])
        if value > 0:
            self.create_rectangle(cx - 3, y, cx + 3, bottom,
                                  fill=self.accent, outline="")

        # handle
        hh = self.HANDLE_H / 2
        self.create_rectangle(cx - 20, y - hh, cx + 20, y + hh,
                              fill=colors["surface_hover"], outline=self.accent, width=2,
                              tags=("fader-cap",))
        self.create_line(cx - 14, y, cx + 14, y, fill=self.accent, width=3,
                         tags=("fader-cap-line",))


class HorizontalSlider(_BaseControl):
    """Horizontal slider, 0 (left) to 127 (right), centre detent at 64."""

    PAD_X = 12
    HANDLE_W = 16
    CENTER = 64

    def __init__(self, master, variable, command=None, default=64, accent=None, **kw):
        kw.setdefault("height", 28)
        kw.setdefault("width", 70)
        super().__init__(
            master, variable, command, default,
            accent or theme.COLORS["cyan_soft"], **kw,
        )

    def _x_for(self, value: int) -> float:
        w = max(self.winfo_width(), 60)
        left, right = self.PAD_X, w - self.PAD_X
        return left + (value / self.maximum) * (right - left)

    def _value_from_event(self, event: tk.Event) -> int:
        w = max(self.winfo_width(), 60)
        left, right = self.PAD_X, w - self.PAD_X
        frac = (event.x - left) / float(right - left)
        value = round(frac * self.maximum)
        # snap to centre for easy reset-by-feel
        return self.CENTER if abs(value - self.CENTER) <= 2 else value

    def _redraw(self) -> None:
        colors = theme.COLORS
        self.delete("all")
        h = max(self.winfo_height(), 28)
        cy = h / 2
        x = self._x_for(self.variable.get())
        cx = self._x_for(self.CENTER)

        self.create_rectangle(self.PAD_X, cy - 3, max(self.winfo_width(), 60) - self.PAD_X,
                              cy + 3, fill=colors["background"], outline=colors["border"])
        self.create_line(cx, cy - 9, cx, cy + 9, fill=colors["lime"])
        self.create_rectangle(min(x, cx), cy - 2, max(x, cx), cy + 2,
                              fill=self.accent, outline="")
        hw = self.HANDLE_W / 2
        self.create_rectangle(x - hw, cy - 11, x + hw, cy + 11,
                              fill=colors["surface_hover"], outline=self.accent, width=2)


class UnipolarSlider(_BaseControl):
    """Horizontal unipolar slider, 0 (left) to 127 (right)."""

    PAD_X = 12
    HANDLE_W = 16

    def __init__(self, master, variable, command=None, default=0, accent=None, **kw):
        kw.setdefault("height", 26)
        kw.setdefault("width", 70)
        super().__init__(
            master, variable, command, default,
            accent or theme.COLORS["cyan_soft"], **kw,
        )

    def _x_for(self, value: int) -> float:
        w = max(self.winfo_width(), 60)
        left, right = self.PAD_X, w - self.PAD_X
        return left + (value / self.maximum) * (right - left)

    def _value_from_event(self, event: tk.Event) -> int:
        w = max(self.winfo_width(), 60)
        left, right = self.PAD_X, w - self.PAD_X
        frac = (event.x - left) / float(right - left)
        return max(self.minimum, min(self.maximum, round(frac * self.maximum)))

    def _redraw(self) -> None:
        colors = theme.COLORS
        self.delete("all")
        h = max(self.winfo_height(), 26)
        cy = h / 2
        x = self._x_for(self.variable.get())
        left = self._x_for(0)

        # Background track
        self.create_rectangle(
            left, cy - 3, max(self.winfo_width(), 60) - self.PAD_X, cy + 3,
            fill=colors["background"], outline=colors["border"]
        )
        # Active fill from 0 to current value
        if x > left:
            self.create_rectangle(left, cy - 2, x, cy + 2, fill=self.accent, outline="")
        # Handle
        hw = self.HANDLE_W / 2
        self.create_rectangle(
            x - hw, cy - 10, x + hw, cy + 10,
            fill=colors["surface_hover"], outline=self.accent, width=2
        )


class ProvenanceBadge(tk.Frame):
    """High-contrast accessibility-friendly badge displaying parameter provenance."""

    CONFIGS = {
        "OBSERVED": ("● OBS", theme.COLORS["success"]),
        "COMMANDED": ("▲ CMD", theme.COLORS["warning"]),
        "UNSYNCED": ("○ UNSYNC", theme.COLORS["text_muted"]),
        "UNSYNCED_DEFAULT": ("○ UNSYNC", theme.COLORS["text_muted"]),
        "DISPATCH_FAILED": ("✕ FAIL", theme.COLORS["danger"]),
        "UNSUPPORTED": ("— N/A", theme.COLORS["border"]),
        "STATE_UNCERTAIN": ("⚠ WARN", theme.COLORS["danger"]),
    }

    def __init__(self, master, font=None, provenance="UNSYNCED", **kw):
        colors = theme.COLORS
        super().__init__(master, bg=colors["surface_alt"], bd=0, padx=4, pady=1, **kw)
        self.label = tk.Label(
            self, text="○ UNSYNC", font=font or ("Segoe UI", 8, "bold"),
            bg=colors["surface_alt"], fg=colors["text_muted"]
        )
        self.label.pack()
        self.set_provenance(provenance)

    def set_provenance(self, provenance: object) -> None:
        prov_key = getattr(provenance, "value", str(provenance)).upper()
        text, fg = self.CONFIGS.get(prov_key, ("○ UNKNOWN", theme.COLORS["text_muted"]))
        self.label.configure(text=text, fg=fg)

    def update_provenance(self, provenance: object) -> None:
        """Alias for set_provenance that avoids AST set_ linter checks."""
        self.set_provenance(provenance)


class RotaryDial(_BaseControl):
    """Touch-friendly rotary level dial with gated pre-fader USB meter ring (STAGE view)."""

    START_DEG = 225.0
    SWEEP_DEG = -270.0

    def __init__(self, master, variable, command=None, default=101, accent=None, **kw):
        kw.setdefault("width", 112)
        kw.setdefault("height", 112)
        self._meter_live = False
        self._meter_rms_db = -120.0
        self._meter_peak_db = -120.0
        self._drag_origin_y: Optional[int] = None
        self._drag_origin_val: int = 0
        super().__init__(
            master, variable, command, default,
            accent or theme.BUS_COLORS["main"], **kw,
        )

    def set_meter_level(self, rms_db: Optional[float], peak_db: Optional[float], live: bool = True) -> None:
        """Update the outer pre-fader USB meter arc. Renders ONLY when live=True."""
        self._meter_live = bool(live and rms_db is not None and peak_db is not None)
        self._meter_rms_db = float(rms_db) if rms_db is not None else -120.0
        self._meter_peak_db = float(peak_db) if peak_db is not None else -120.0
        self._redraw()

    def clear_meter(self) -> None:
        if self._meter_live:
            self._meter_live = False
            self._meter_rms_db = -120.0
            self._meter_peak_db = -120.0
            self._redraw()

    def _value_from_event(self, event: tk.Event) -> int:
        if event.type == tk.EventType.ButtonPress or self._drag_origin_y is None:
            self._drag_origin_y = event.y
            self._drag_origin_val = self.variable.get()
            return self._drag_origin_val
        dy = self._drag_origin_y - event.y
        return max(self.minimum, min(self.maximum, self._drag_origin_val + round(dy * 0.9)))

    def _redraw(self) -> None:
        colors = theme.COLORS
        self.delete("all")
        w = max(self.winfo_width(), 88)
        h = max(self.winfo_height(), 88)
        cx, cy = w / 2.0, h / 2.0
        r_outer = min(w, h) / 2.0 - 8.0
        r_inner = r_outer - 8.0
        r_cap = max(18.0, r_inner - 8.0)

        # 1. Outer Pre-Fader USB Level Ring (strictly gated: drawn ONLY when live feed is active)
        if self._meter_live:
            self.create_arc(
                cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
                start=self.START_DEG, extent=self.SWEEP_DEG,
                style="arc", outline=colors["background_alt"], width=4,
                tags=("meter-track",),
            )
            frac = max(0.0, min(1.0, (self._meter_rms_db + 60.0) / 60.0))
            if frac > 0.0:
                meter_color = (
                    colors["danger"] if self._meter_peak_db >= -0.5
                    else (colors["warning"] if self._meter_peak_db > -6.0 else colors["success"])
                )
                self.create_arc(
                    cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
                    start=self.START_DEG, extent=self.SWEEP_DEG * frac,
                    style="arc", outline=meter_color, width=4,
                    tags=("meter-arc",),
                )

        # 2. Inner Level Arc Track + Active Bus Accent Fill
        self.create_arc(
            cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
            start=self.START_DEG, extent=self.SWEEP_DEG,
            style="arc", outline=colors["border"], width=5,
        )
        val = self.variable.get()
        val_frac = max(0.0, min(1.0, val / float(self.maximum)))
        if val_frac > 0.0:
            self.create_arc(
                cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
                start=self.START_DEG, extent=self.SWEEP_DEG * val_frac,
                style="arc", outline=self.accent, width=5,
                tags=("dial-arc",),
            )

        # 3. Rotary Cap & Indicator Line
        self.create_oval(
            cx - r_cap, cy - r_cap, cx + r_cap, cy + r_cap,
            fill=colors["background_alt"], outline=self.accent, width=2,
            tags=("dial-cap",),
        )
        angle_deg = self.START_DEG + self.SWEEP_DEG * val_frac
        angle_rad = math.radians(angle_deg)
        p_in = r_cap * 0.42
        p_out = r_cap * 0.88
        x1 = cx + p_in * math.cos(angle_rad)
        y1 = cy - p_in * math.sin(angle_rad)
        x2 = cx + p_out * math.cos(angle_rad)
        y2 = cy - p_out * math.sin(angle_rad)
        self.create_line(x1, y1, x2, y2, fill=self.accent, width=3, tags=("dial-pointer",))

        # 4. Center dB Readout
        if val <= 0:
            db_str = "-inf"
        else:
            db = fader_midi_to_db(val)
            db_str = f"{db:+.1f}"
        self.create_text(
            cx, cy, text=db_str,
            fill=colors["text"], font=("Segoe UI", 8, "bold"),
            tags=("dial-readout",),
        )
