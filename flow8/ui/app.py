"""FLOW 8 Cyber Neon application workstation (UI.2).

Main application window, identity header, navigation rail, 7-strip mixer console,
and real-time hardware status management.
"""

from __future__ import annotations

import sys
import tkinter as tk
import threading
import queue
from typing import Optional

from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.components import widget_texts
from flow8.ui.components.header import Header
from flow8.ui.components.mixer_console import MixerConsole
from flow8.ui.components.navigation import Navigation
from flow8.ui.components.status_bar import StatusBar
from flow8.ui.status import SessionStatus


class Flow8App:
    """Owns the Tk root window, hardware service, and workstation regions."""

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        status: Optional[SessionStatus] = None,
        service: Optional[Flow8Service] = None,
        connect_hardware: bool = False,
        show_placeholder: bool = True,
    ) -> None:
        self._owns_root = root is None
        self.root = root if root is not None else tk.Tk()
        self.status = status if status is not None else SessionStatus()
        self._closed = False
        self._connection_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._connection_poll_id: Optional[str] = None
        self._connection_in_flight = False
        self.connect_hardware = connect_hardware
        self.show_placeholder = show_placeholder

        # Hardware Service initialization
        if service is not None:
            self.service = service
        elif connect_hardware:
            try:
                self.service = Flow8Service(auto_connect=True)
            except Exception:
                self.service = None
        else:
            self.service = None

        theme.apply_base_theme(self.root)
        self.fonts = theme.build_fonts(self.root)
        self._configure_window()
        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._connection_poll_id = self.root.after(25, self._poll_connection_events)

        # Update initial connection state & schedule watcher
        if self.service and self.service.is_connected:
            self.header.set_device_status(True, "MIDI I/O")
            self.status_bar.set_hardware_status(True)

        if self.connect_hardware:
            self.root.after(2500, self._poll_hardware_state)

    # -- window -------------------------------------------------------------

    def _configure_window(self) -> None:
        width, height = theme.WINDOW_DEFAULT_SIZE
        self.root.title(theme.WINDOW_TITLE)
        self.root.minsize(*theme.WINDOW_MIN_SIZE)
        self.root.resizable(True, True)

        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            left = max(0, (screen_width - width) // 2)
            top = max(0, (screen_height - height) // 3)
            self.root.geometry(f"{width}x{height}+{left}+{top}")
        except tk.TclError:
            self.root.geometry(f"{width}x{height}")

    # -- layout -------------------------------------------------------------

    def _build_layout(self) -> None:
        colors = theme.COLORS
        self.root.configure(bg=colors["background"])
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.header = Header(
            self.root,
            self.fonts,
            self.status,
            on_connect=self.connect_hardware_async,
            on_disconnect=self.disconnect_hardware,
            on_retry=self.connect_hardware_async,
        )
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

        if self.show_placeholder:
            self._build_placeholder()
        else:
            self.mixer_console = MixerConsole(
                self.workspace,
                self.fonts,
                service=self.service,
                on_feedback=self.status_bar.show_feedback,
            )
            self.mixer_console.pack(fill="both", expand=True)

        self.navigation.select("mixer")

    def _build_placeholder(self) -> None:
        """The workspace placeholder (UI.2-T1 baseline mode)."""
        colors = theme.COLORS
        spacing = theme.TOKENS

        halo = tk.Frame(self.workspace, bg=colors["halo"])
        halo.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(halo, bg=colors["background_alt"])
        card.pack(padx=1, pady=1)

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

    def _poll_hardware_state(self) -> None:
        """Watchdog: verifies hardware connection and auto-reconnects if needed."""
        if self._closed:
            return

        try:
            if self.service:
                was_connected = self.service.is_connected
                if not was_connected:
                    self.connect_hardware_async()
                else:
                    self.header.set_device_status(True, "MIDI I/O")
                    self.status_bar.set_hardware_status(True)
        except Exception:
            pass

        if not self._closed:
            self.root.after(2500, self._poll_hardware_state)

    def _poll_connection_events(self) -> None:
        """Drain worker results on the Tk main thread only."""
        if self._closed:
            return
        try:
            while True:
                event, payload = self._connection_events.get_nowait()
                self._connection_in_flight = False
                if event == "connect":
                    connected = bool(payload)
                    if connected:
                        self.header.set_device_status(True, "MIDI I/O")
                        self.status_bar.set_hardware_status(True)
                        self.status_bar.show_feedback("CONNECT OK")
                    else:
                        self.header.set_device_status(False)
                        self.status_bar.set_hardware_status(False)
                        detail = self.service.last_connection_error if self.service else "unavailable"
                        self.status_bar.show_feedback(f"CONNECT FAILED: {detail or 'unavailable'}")
                elif event == "disconnect":
                    self._apply_disconnect_result(str(payload))
        except queue.Empty:
            pass
        if not self._closed:
            self._connection_poll_id = self.root.after(25, self._poll_connection_events)

    def connect_hardware_async(self) -> None:
        """Start connection work off the Tk thread and report its result."""
        if self._closed:
            return
        if self._connection_in_flight:
            return
        if self.service is None:
            try:
                self.service = Flow8Service(auto_connect=False)
            except Exception as error:
                self.status_bar.show_feedback(f"CONNECT FAILED: {error}")
                return

        def worker() -> None:
            try:
                connected = self.service.connect()
            except Exception:
                connected = False
            self._connection_events.put(("connect", connected))

        self._connection_in_flight = True
        threading.Thread(target=worker, name="flow8-connect", daemon=True).start()

    def disconnect_hardware(self) -> None:
        """Disconnect without blocking the UI thread."""
        if not self.service:
            self.status_bar.show_feedback("DISCONNECT: NOT CONNECTED")
            return
        if self._connection_in_flight:
            return

        def worker() -> None:
            try:
                self.service.disconnect()
                message = "DISCONNECTED"
            except Exception as error:
                message = f"DISCONNECT FAILED: {error}"
            self._connection_events.put(("disconnect", message))

        self._connection_in_flight = True
        threading.Thread(target=worker, name="flow8-disconnect", daemon=True).start()

    def _apply_disconnect_result(self, message: str) -> None:
        self.header.set_device_status(False)
        self.status_bar.set_hardware_status(False)
        self.status_bar.show_feedback(message)

    # -- navigation ---------------------------------------------------------

    def show_page(self, key: str) -> bool:
        """Select *key* destination."""
        return self.navigation.select(key)

    # -- lifecycle ----------------------------------------------------------

    @property
    def closed(self) -> bool:
        """True once the shell has shut down."""
        return self._closed

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        """Destroy the window and close MIDI hardware connections cleanly."""
        if self._closed:
            return
        self._closed = True

        if self._connection_poll_id is not None:
            try:
                self.root.after_cancel(self._connection_poll_id)
            except tk.TclError:
                pass
            self._connection_poll_id = None

        if self.service:
            try:
                self.service.disconnect()
            except Exception:
                pass

        try:
            self.root.destroy()
        except tk.TclError:
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
        print(f"FLOW 8 workstation takes no arguments: {unexpected}", file=sys.stderr)
        return 2

    # Launch with hardware enabled and live 7-strip mixer console
    try:
        app = Flow8App(connect_hardware=True, show_placeholder=False)
    except tk.TclError as error:
        print(f"FLOW 8 workstation could not start: {error}", file=sys.stderr)
        return 1

    try:
        app.run()
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
