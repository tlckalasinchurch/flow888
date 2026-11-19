"""FLOW 8 Cyber Neon application workstation (UI.2).

Main application window, identity header, navigation rail, 7-strip mixer console,
and real-time hardware status management.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import tkinter as tk
from typing import Optional

from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.components import widget_texts
from flow8.ui.components.device_view import DeviceView
from flow8.ui.components.fx_view import FxView
from flow8.ui.components.header import Header
from flow8.ui.components.mixer_console import MixerConsole
from flow8.ui.components.navigation import Navigation
from flow8.ui.components.routing_view import RoutingView
from flow8.ui.components.scenes_view import ScenesView
from flow8.ui.components.status_bar import StatusBar
from flow8.ui.status import SessionStatus

logger = logging.getLogger(__name__)


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
        self.connect_hardware = connect_hardware
        self.show_placeholder = show_placeholder
        self._service_error: Optional[str] = None

        # Connection attempts run on a worker thread. The worker never touches Tk: it
        # only puts a result on this queue, which the Tk thread drains with after().
        self._connection_events: queue.Queue = queue.Queue()
        self._connection_busy = False
        self._auto_connect = connect_hardware
        self._last_connection_failed = False
        self._last_reported_error: Optional[str] = None
        self._queue_poll_id: Optional[str] = None
        self._state_poll_id: Optional[str] = None
        self._lan_hub = None

        # Hardware Service initialization
        if service is not None:
            self.service = service
        elif connect_hardware:
            try:
                # Ports are opened off the UI thread below, so a slow or hung MIDI
                # driver can never stop the window from appearing.
                self.service = Flow8Service(auto_connect=False)
            except Exception as error:
                self.service = None
                self._service_error = str(error)
                logger.exception("FLOW 8 service initialization failed")
        else:
            self.service = None

        theme.apply_base_theme(self.root)
        self.fonts = theme.build_fonts(self.root)
        self._configure_window()
        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Report each MIDI endpoint independently; an open port is not hardware confirmation.
        self._refresh_hardware_status()

        self._queue_poll_id = self.root.after(50, self._poll_connection_events)
        if self.connect_hardware:
            self._start_connection("connect", user_initiated=False)
            self._state_poll_id = self.root.after(2500, self._poll_hardware_state)

    # -- window -------------------------------------------------------------

    def _configure_window(self) -> None:
        width, height = theme.WINDOW_DEFAULT_SIZE
        self.root.title(theme.WINDOW_TITLE)
        self.root.minsize(*theme.WINDOW_MIN_SIZE)
        self.root.resizable(True, True)

        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            # Never open larger than the display (the taskbar allowance keeps the
            # status bar and docked inspector on screen), but never below the
            # supported minimum size.
            usable_height = screen_height - theme.TASKBAR_ALLOWANCE
            # The supported minimum cannot exceed a small display (e.g. 720 high);
            # otherwise the status bar would sit below the screen edge.
            min_width = min(theme.WINDOW_MIN_SIZE[0], screen_width)
            min_height = min(theme.WINDOW_MIN_SIZE[1], usable_height)
            self.root.minsize(min_width, min_height)
            width = max(min_width, min(width, screen_width))
            height = max(min_height, min(height, usable_height))
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
            on_toggle_lan=self.toggle_lan_hub,
            on_select_view=self.select_workstation_view,
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

        self._pages: dict[str, tk.Frame] = {}
        self._active_page: str = "mixer"
        if self.show_placeholder:
            self._build_placeholder()
        else:
            self.navigation.enable_workstation_pages()
            self.mixer_console = MixerConsole(
                self.workspace,
                self.fonts,
                service=self.service,
                on_feedback=self.status_bar.show_feedback,
                on_view_changed=self.header.set_active_view,
            )
            self.routing_view = RoutingView(
                self.workspace,
                self.fonts,
                service=self.service,
                on_feedback=self.status_bar.show_feedback,
                on_phantom_request=self._request_phantom_via_inspector,
            )
            self.fx_view = FxView(
                self.workspace,
                self.fonts,
                service=self.service,
                on_feedback=self.status_bar.show_feedback,
            )
            self.scenes_view = ScenesView(
                self.workspace,
                self.fonts,
                service=self.service,
                on_feedback=self.status_bar.show_feedback,
                on_recalled=self.mixer_console._refresh_strips,
            )
            self.device_view = DeviceView(
                self.workspace,
                self.fonts,
                service=self.service,
                on_connect=self.connect_hardware_async,
                on_disconnect=self.disconnect_hardware,
                on_toggle_lan=self.toggle_lan_hub,
            )
            self._pages = {
                "mixer": self.mixer_console,
                "routing": self.routing_view,
                "fx": self.fx_view,
                "scenes": self.scenes_view,
                "device": self.device_view,
            }
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

    def _refresh_hardware_status(self) -> None:
        """Refresh independent MIDI port states and surface the latest connection error."""
        if self.service is None:
            midi_out_open = False
            midi_in_open = False
            midi_in_listening = False
            error = self._service_error
        else:
            midi_out_open = self.service.midi_out_open
            midi_in_open = self.service.midi_in_open
            midi_in_listening = self.service.midi_in_listening
            error = self.service.connection_error

        self.header.set_midi_port_status(
            midi_out_open, midi_in_open, error, midi_in_listening,
        )
        self.status_bar.set_midi_port_status(
            midi_out_open, midi_in_open, error, midi_in_listening,
        )
        dev_view = getattr(self, "device_view", None)
        if dev_view is not None:
            dev_view.refresh()
        self._update_connection_controls()

    # -- connection (worker thread + queue) ---------------------------------

    def connect_hardware_async(self) -> bool:
        """CONNECT / RETRY: open the MIDI ports without blocking the UI."""
        self._auto_connect = True
        return self._start_connection("connect", user_initiated=True)

    def disconnect_hardware(self) -> bool:
        """DISCONNECT: close the ports and stop automatic reconnecting."""
        self._auto_connect = False
        return self._start_connection("disconnect", user_initiated=True)

    def _start_connection(self, action: str, user_initiated: bool) -> bool:
        if self._closed or self._connection_busy:
            return False
        if self.service is None:
            if user_initiated:
                self._report(
                    f"{action.upper()} UNAVAILABLE — "
                    f"{self._service_error or 'NO COMMAND SERVICE (OFFLINE MODE)'}",
                    problem=True,
                )
            return False
        self._connection_busy = True
        self.header.set_connection_busy(
            "CONNECTING…" if action == "connect" else "DISCONNECTING…"
        )
        self._update_connection_controls()
        threading.Thread(
            target=self._connection_worker,
            args=(action, user_initiated),
            name=f"flow8-{action}",
            daemon=True,
        ).start()
        return True

    def _connection_worker(self, action: str, user_initiated: bool) -> None:
        """Runs off the Tk thread. Touches no widget; reports through the queue."""
        service = self.service
        try:
            if action == "connect":
                ok = bool(service.connect())
                error = None if ok else (
                    service.connection_error or "connection failed; no reason was reported"
                )
            else:
                service.disconnect()
                ok, error = True, None
        except Exception as exc:
            logger.exception("FLOW 8 %s failed", action)
            ok, error = False, str(exc) or exc.__class__.__name__
        self._connection_events.put((action, ok, error, user_initiated))

    def _poll_connection_events(self) -> None:
        """Tk thread: apply finished connection attempts to the UI."""
        self._queue_poll_id = None
        if self._closed:
            return
        try:
            while True:
                action, ok, error, user_initiated = self._connection_events.get_nowait()
                self._on_connection_result(action, ok, error, user_initiated)
        except queue.Empty:
            pass
        if not self._closed:
            self._queue_poll_id = self.root.after(50, self._poll_connection_events)

    def _on_connection_result(
        self, action: str, ok: bool, error: Optional[str], user_initiated: bool
    ) -> None:
        self._connection_busy = False
        if action == "connect":
            self._last_connection_failed = not ok
        self._refresh_hardware_status()

        if action == "disconnect":
            self._report("DISCONNECTED — MIDI PORTS CLOSED")
        elif ok:
            self._last_reported_error = None
            # Open ports are not proof that a FLOW 8 is answering.
            self._report("MIDI PORTS OPEN — HARDWARE NOT CONFIRMED")
        elif user_initiated or error != self._last_reported_error:
            # Automatic retries repeat the same failure; only report it when it changes.
            self._last_reported_error = error
            self._report(f"CONNECT FAILED — {error}", problem=True)

    def _report(self, message: str, problem: bool = False) -> None:
        """Surface a connection event in the status bar and the command log panel."""
        self.status_bar.show_feedback(message)
        console = getattr(self, "mixer_console", None)
        if console is not None:
            console.command_log_panel.set_notice(message, problem=problem)

    def _update_connection_controls(self) -> None:
        service = self.service
        if service is None:
            self.header.set_connection_controls(False, False, False)
            return
        if self._connection_busy:
            # The worker holds the MIDI locks while ports open; reading service state
            # here would block the UI thread behind it.
            self.header.set_connection_controls(False, False, False)
            return
        connected = service.is_connected
        any_open = service.midi_out_open or service.midi_in_open
        self.header.set_connection_controls(
            connect=not connected,
            disconnect=any_open,
            retry=not connected and self._last_connection_failed,
        )

    def _poll_hardware_state(self) -> None:
        """Refresh port state; retry an incomplete connection off the UI thread."""
        self._state_poll_id = None
        if self._closed:
            return
        if self.service is not None and not self._connection_busy:
            if self._auto_connect and not self.service.is_connected:
                self._start_connection("connect", user_initiated=False)
            elif self.service.is_connected and not self.service.check_connection_health():
                self._refresh_hardware_status()
                self._report("DISCONNECTED — FLOW 8 USB REMOVED", problem=True)
            else:
                self._refresh_hardware_status()
        self._state_poll_id = self.root.after(2500, self._poll_hardware_state)

    def toggle_lan_hub(self) -> bool:
        """Start or stop the Wi-Fi / LAN Remote Hub (HTTP + SSE)."""
        if self.service is None:
            self._report("LAN HUB UNAVAILABLE — NO COMMAND SERVICE", problem=True)
            return False
        if self._lan_hub is not None and self._lan_hub.is_running:
            self._lan_hub.stop()
            self._lan_hub = None
            self.header.set_lan_active(False)
            self._report("LAN REMOTE HUB STOPPED")
            return False
        from flow8.lan_hub import Flow8LanHub
        hub = Flow8LanHub(self.service)
        sv = getattr(self, "scenes_view", None)
        if sv is not None and hasattr(sv, "library"):
            hub.library = sv.library
        try:
            hub.start()
        except Exception as exc:
            self._report(f"LAN HUB FAILED — {exc}", problem=True)
            return False
        self._lan_hub = hub
        self.header.set_lan_active(True)
        urls = ", ".join(hub.lan_urls())
        self._report(f"LAN REMOTE ACTIVE — {urls}")
        return True

    # -- navigation ---------------------------------------------------------

    def _request_phantom_via_inspector(self, channel_index: int, enabled: bool) -> None:
        """+48V from the I/O page: show the mixer and run the Inspector's confirmation flow."""
        self.show_page("mixer")
        self.mixer_console._on_phantom_request(channel_index, enabled)

    def select_workstation_view(self, view: str) -> bool:
        """Switch the main console between MIXER and STAGE views from the top header."""
        v_key = str(view or "mixer").lower()
        if v_key not in ("mixer", "stage"):
            return False
        if not self.show_placeholder and self._active_page != "mixer":
            self.show_page("mixer")
        console = getattr(self, "mixer_console", None)
        if console is not None:
            return console.set_view_mode(v_key)
        return False

    def show_page(self, key: str) -> bool:
        """Select *key* destination and swap the active workspace frame."""
        if not self.navigation.select(key):
            return False
        if key in self._pages:
            for page_key, frame in self._pages.items():
                if page_key == key:
                    refresh = getattr(frame, "refresh", None)
                    if callable(refresh):
                        refresh()
                    if not frame.winfo_manager():
                        frame.pack(fill="both", expand=True)
                elif frame.winfo_manager():
                    frame.pack_forget()
            self._active_page = key
        return True

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

        for timer_id in (self._queue_poll_id, self._state_poll_id):
            if timer_id is not None:
                try:
                    self.root.after_cancel(timer_id)
                except tk.TclError:
                    pass
        self._queue_poll_id = self._state_poll_id = None

        if self._lan_hub is not None:
            try:
                self._lan_hub.stop()
            except Exception:
                logger.exception("FLOW 8 LAN hub stop on close failed")
            self._lan_hub = None

        if self.service:
            if self._connection_busy:
                # An attempt still holds the service lock; do not wait for it on the UI thread.
                threading.Thread(target=self._safe_disconnect, daemon=True).start()
            else:
                self._safe_disconnect()

        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _safe_disconnect(self) -> None:
        try:
            self.service.disconnect()
        except Exception:
            logger.exception("FLOW 8 disconnect on close failed")

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
