"""FLOW 8 Cyber Neon application shell (UI.2-T1).

What this module does: builds the window, the identity header, the navigation
rail, an empty workspace card, and the status bar, then runs the Tk event loop.

What this module deliberately does not do: it never imports the MIDI transport
modules, never opens a port, never dispatches a parameter, and never renders a
meter, a channel value, or a hardware confirmation. Starting and closing the
shell transmits zero MIDI bytes.
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Optional

from flow8.ui import theme
from flow8.ui.components.header import Header
from flow8.ui.components.navigation import Navigation
from flow8.ui.components.status_bar import StatusBar
from flow8.ui.components import widget_texts
from flow8.ui.status import SessionStatus


class Flow8App:
    """Owns the Tk root window and the three shell regions."""

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        status: Optional[SessionStatus] = None,
    ) -> None:
        self._owns_root = root is None
        self.root = root if root is not None else tk.Tk()
        self.status = status if status is not None else SessionStatus()
        self._closed = False

        theme.apply_base_theme(self.root)
        self.fonts = theme.build_fonts(self.root)
        self._configure_window()
        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # -- window -------------------------------------------------------------

    def _configure_window(self) -> None:
        width, height = theme.WINDOW_DEFAULT_SIZE
        self.root.title(theme.WINDOW_TITLE)
        self.root.minsize(*theme.WINDOW_MIN_SIZE)
        self.root.resizable(True, True)

        # Centre on the primary display; harmless if the metrics are unusual.
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            left = max(0, (screen_width - width) // 2)
            top = max(0, (screen_height - height) // 3)
            self.root.geometry(f"{width}x{height}+{left}+{top}")
        except tk.TclError:  # pragma: no cover - defensive
            self.root.geometry(f"{width}x{height}")

    # -- layout -------------------------------------------------------------

    def _build_layout(self) -> None:
        colors = theme.COLORS
        self.root.configure(bg=colors["background"])
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.header = Header(self.root, self.fonts, self.status)
        self.header.grid(row=0, column=0, sticky="ew")

        body = tk.Frame(self.root, bg=colors["background"])
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self.navigation = Navigation(body, self.fonts, on_select=self.show_page)
        self.navigation.grid(row=0, column=0, sticky="nsw")

        self.workspace = tk.Frame(body, bg=colors["background"])
        self.workspace.grid(row=0, column=1, sticky="nsew")

        self.status_bar = StatusBar(self.root, self.fonts, self.status)
        self.status_bar.grid(row=2, column=0, sticky="ew")

        self._build_placeholder()
        self.navigation.select("mixer")

    def _build_placeholder(self) -> None:
        """The workspace is empty by design: no controls exist in UI.2-T1."""
        colors = theme.COLORS
        spacing = theme.TOKENS

        halo = tk.Frame(self.workspace, bg=colors["halo"])
        halo.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(halo, bg=colors["background_alt"])
        card.pack(padx=1, pady=1)

        # Cyan top edge: the one accent that reads as glow on this panel.
        tk.Frame(card, bg=colors["cyan"], height=3).pack(fill="x")

        inner = tk.Frame(card, bg=colors["background_alt"])
        inner.pack(padx=spacing["spacing_xlarge"], pady=spacing["spacing_xlarge"])

        tk.Label(
            inner,
            text="UI.2-T1 · APPLICATION SHELL",
            font=self.fonts["eyebrow"],
            fg=colors["cyan_soft"],
            bg=colors["background_alt"],
        ).pack()

        tk.Label(
            inner,
            text="MIXER CONSOLE",
            font=self.fonts["section"],
            fg=colors["text"],
            bg=colors["background_alt"],
        ).pack(pady=(spacing["spacing_medium"], 0))

        tk.Label(
            inner,
            text="COMING IN UI.2-T2",
            font=self.fonts["subtitle"],
            fg=colors["cyan"],
            bg=colors["background_alt"],
        ).pack(pady=(4, spacing["spacing_large"]))

        tk.Frame(inner, bg=colors["border"], width=64, height=1).pack(
            pady=(0, spacing["spacing_large"])
        )

        notes = (
            "Seven logical strips will be rendered from the existing domain model.",
            "No faders, meters, or channel values are shown in this build.",
            "This shell transmits no MIDI.",
        )
        for note in notes:
            tk.Label(
                inner,
                text=note,
                font=self.fonts["body"],
                fg=colors["text_muted"],
                bg=colors["background_alt"],
            ).pack(pady=1)

        tk.Label(
            inner,
            text="ROUTING · FX · SCENES · RECORDING REMAIN UNAVAILABLE",
            font=self.fonts["caption"],
            fg=colors["purple_soft"],
            bg=colors["background_alt"],
        ).pack(pady=(spacing["spacing_large"], 0))

    # -- navigation ---------------------------------------------------------

    def show_page(self, key: str) -> bool:
        """Select *key* if it is implemented. There is only one page today."""
        return self.navigation.select(key)

    # -- lifecycle ----------------------------------------------------------

    @property
    def closed(self) -> bool:
        """True once the shell has shut down."""
        return self._closed

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        """Destroy the window. No transport, thread, or port is held open."""
        if self._closed:
            return
        self._closed = True
        try:
            self.root.destroy()
        except tk.TclError:  # pragma: no cover - already destroyed
            pass

    # -- inspection ---------------------------------------------------------

    def text_snapshot(self) -> list[str]:
        """Every static string currently rendered anywhere in the shell."""
        return widget_texts(self.root)


def main(argv: Optional[list[str]] = None) -> int:
    """Start the shell. Returns a process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    unexpected = [argument for argument in arguments if not argument.startswith("-")]
    if unexpected:
        print(f"FLOW 8 shell takes no arguments: {unexpected}", file=sys.stderr)
        return 2

    try:
        app = Flow8App()
    except tk.TclError as error:
        print(f"FLOW 8 shell could not start: {error}", file=sys.stderr)
        return 1

    try:
        app.run()
    finally:
        app.close()
    return 0


if __name__ == "__main__":  # pragma: no cover - manual launch
    raise SystemExit(main())
