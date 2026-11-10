"""Header CONNECT / DISCONNECT / RETRY: off-thread attempts, main-thread UI, honest errors.

A fake service stands in for the MIDI ports, so no port is ever opened. Its
``connect`` blocks on an event the test controls, which proves the Tk thread is
not blocked while an attempt is in flight.
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from flow8.service import Flow8Service
from flow8.ui.app import Flow8App


class FakeLink(Flow8Service):
    """Flow8Service whose port state and connect/disconnect are test-controlled."""

    def __init__(self) -> None:
        super().__init__(auto_connect=False)
        self.gate = threading.Event()
        self.gate.set()
        self.started = threading.Event()
        self.open = False
        self.error: str | None = None
        self.fail_with: str | None = None
        self.raise_with: Exception | None = None
        self.connect_threads: list[threading.Thread] = []
        self.disconnect_threads: list[threading.Thread] = []

    midi_out_open = property(lambda self: self.open)
    midi_in_open = property(lambda self: self.open)
    midi_in_listening = property(lambda self: self.open)
    is_connected = property(lambda self: self.open)
    connection_error = property(lambda self: self.error)

    def connect(self) -> bool:
        self.connect_threads.append(threading.current_thread())
        self.started.set()
        self.gate.wait(5)
        if self.raise_with is not None:
            raise self.raise_with
        if self.fail_with is not None:
            # "" models a driver that fails without saying why.
            self.open, self.error = False, self.fail_with or None
            return False
        self.open, self.error = True, None
        return True

    def disconnect(self) -> None:
        self.disconnect_threads.append(threading.current_thread())
        self.open, self.error = False, None


def pump(app: Flow8App, until, timeout: float = 3.0) -> bool:
    """Run the Tk event loop until *until()* holds (no fixed sleeps)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.root.update()
        if until():
            return True
        time.sleep(0.01)
    return False


class _Case(unittest.TestCase):
    connect_hardware = False

    def setUp(self):
        self.link = FakeLink()
        self.app = Flow8App(
            service=self.link, connect_hardware=self.connect_hardware, show_placeholder=False
        )
        self.addCleanup(self.app.close)
        self.header = self.app.header
        self.buttons = self.header.connection_buttons

    def states(self):
        return {name: str(button.cget("state")) for name, button in self.buttons.items()}

    def feedback(self):
        return self.app.status_bar.last_feedback_full

    def idle(self):
        return not self.app._connection_busy


class ConnectionFlowTests(_Case):
    def test_initial_state_offers_connect_only(self):
        self.assertEqual(
            self.states(), {"CONNECT": "normal", "DISCONNECT": "disabled", "RETRY": "disabled"}
        )
        self.assertEqual(self.header.device_status_var.get(), "MIDI PORTS CLOSED")

    def test_connect_returns_at_once_and_runs_off_the_tk_thread(self):
        self.link.gate.clear()
        started = time.monotonic()
        self.assertTrue(self.app.connect_hardware_async())
        self.assertLess(time.monotonic() - started, 0.5)  # did not wait for the port
        self.assertTrue(self.link.started.wait(2))
        self.app.root.update()  # the UI keeps servicing events meanwhile

        self.assertEqual(self.header.device_status_var.get(), "CONNECTING…")
        self.assertEqual(set(self.states().values()), {"disabled"})
        self.assertFalse(self.app.connect_hardware_async(), "second attempt must be refused")

        self.link.gate.set()
        self.assertTrue(pump(self.app, self.idle))
        self.assertIsNot(self.link.connect_threads[0], threading.main_thread())
        self.assertEqual(len(self.link.connect_threads), 1)
        self.assertEqual(self.header.device_status_var.get(), "MIDI PORTS OPEN")
        self.assertEqual(self.app.status_bar.values["midi_out"].get(), "OPEN")
        self.assertEqual(
            self.states(), {"CONNECT": "disabled", "DISCONNECT": "normal", "RETRY": "disabled"}
        )
        # Open ports are not proof that a FLOW 8 answered.
        self.assertEqual(self.feedback(), "MIDI PORTS OPEN — HARDWARE NOT CONFIRMED")

    def test_widgets_are_only_touched_on_the_main_thread(self):
        seen: dict[str, set] = {}

        def spy(owner, name):
            original = getattr(owner, name)

            def wrapper(*args, **kwargs):
                seen.setdefault(name, set()).add(threading.current_thread())
                return original(*args, **kwargs)

            return mock.patch.object(owner, name, side_effect=wrapper)

        with spy(self.header, "set_midi_port_status"), spy(self.header, "set_connection_busy"), \
                spy(self.header, "set_connection_controls"), spy(self.app.status_bar, "show_feedback"):
            self.app.connect_hardware_async()
            self.assertTrue(pump(self.app, self.idle))
            self.app.disconnect_hardware()
            self.assertTrue(pump(self.app, self.idle))

        self.assertTrue(seen, "no UI update observed")
        for name, threads in seen.items():
            self.assertEqual(threads, {threading.main_thread()}, name)

    def test_disconnect_closes_ports_and_stops_automatic_reconnecting(self):
        self.app.connect_hardware_async()
        self.assertTrue(pump(self.app, self.idle))

        self.buttons["DISCONNECT"].invoke()
        self.assertTrue(pump(self.app, self.idle))
        self.assertIsNot(self.link.disconnect_threads[0], threading.main_thread())
        self.assertEqual(self.header.device_status_var.get(), "MIDI PORTS CLOSED")
        self.assertEqual(self.feedback(), "DISCONNECTED — MIDI PORTS CLOSED")
        self.assertEqual(
            self.states(), {"CONNECT": "normal", "DISCONNECT": "disabled", "RETRY": "disabled"}
        )
        with mock.patch.object(self.app, "_start_connection") as start:
            self.app._poll_hardware_state()
        start.assert_not_called()  # the operator's disconnect is not undone behind their back


class ConnectionFailureTests(_Case):
    def test_failure_surfaces_the_real_reason_and_the_app_stays_usable(self):
        self.link.fail_with = "No FLOW 8 MIDI output port found"
        self.buttons["CONNECT"].invoke()
        self.assertTrue(pump(self.app, self.idle))

        reason = "No FLOW 8 MIDI output port found"
        self.assertEqual(self.feedback(), f"CONNECT FAILED — {reason}")
        self.assertIn(reason, self.app.status_bar.values["midi_error"].get())
        self.assertIn(reason, self.app.mixer_console.command_log_panel.notice_var.get())
        self.assertEqual(self.header.device_status_var.get(), "MIDI PORTS ERROR")
        self.assertEqual(
            self.states(), {"CONNECT": "normal", "DISCONNECT": "disabled", "RETRY": "normal"}
        )

        # Offline mode keeps working: commands are accepted, nothing is sent.
        self.link.set_fader(1, 60)
        entry = self.link.command_boundary.command_log[-1]
        self.assertEqual(str(entry.dispatch_status), "ACCEPTED_OFFLINE")

    def test_an_exception_is_reported_and_logged_not_swallowed(self):
        self.link.raise_with = RuntimeError("driver exploded")
        with self.assertLogs("flow8.ui.app", level="ERROR"):
            self.app.connect_hardware_async()
            self.assertTrue(pump(self.app, self.idle))
        self.assertEqual(self.feedback(), "CONNECT FAILED — driver exploded")

    def test_a_failure_without_a_reason_says_so(self):
        self.link.fail_with = ""
        self.link.error = None
        self.app.connect_hardware_async()
        self.assertTrue(pump(self.app, self.idle))
        self.assertIn("no reason was reported", self.feedback())

    def test_retry_after_failure_connects(self):
        self.link.fail_with = "port busy"
        self.app.connect_hardware_async()
        self.assertTrue(pump(self.app, self.idle))
        self.assertEqual(str(self.buttons["RETRY"].cget("state")), "normal")

        self.link.fail_with = None
        self.buttons["RETRY"].invoke()
        self.assertTrue(pump(self.app, self.idle))
        self.assertEqual(self.header.device_status_var.get(), "MIDI PORTS OPEN")
        self.assertEqual(str(self.buttons["RETRY"].cget("state")), "disabled")
        self.assertEqual(len(self.link.connect_threads), 2)

    def test_repeated_automatic_failures_are_reported_once(self):
        self.link.fail_with = "port busy"
        self.app._start_connection("connect", user_initiated=False)
        self.assertTrue(pump(self.app, self.idle))
        self.assertEqual(self.feedback(), "CONNECT FAILED — port busy")
        self.app.status_bar.show_feedback("")
        self.app._start_connection("connect", user_initiated=False)
        self.assertTrue(pump(self.app, self.idle))
        self.assertEqual(self.feedback(), "")  # same error again: no repeat message


class NoServiceTests(unittest.TestCase):
    def test_without_a_service_every_control_is_disabled(self):
        app = Flow8App(show_placeholder=False)
        self.addCleanup(app.close)
        for button in app.header.connection_buttons.values():
            self.assertEqual(str(button.cget("state")), "disabled")
        self.assertFalse(app.connect_hardware_async())
        self.assertIn("UNAVAILABLE", app.status_bar.last_feedback_full)


class TimerTests(_Case):
    connect_hardware = True

    def test_startup_connects_off_the_ui_thread_and_close_cancels_timers(self):
        self.assertTrue(pump(self.app, lambda: self.link.open and self.idle()))
        self.assertIsNot(self.link.connect_threads[0], threading.main_thread())
        self.assertIsNotNone(self.app._queue_poll_id)
        self.assertIsNotNone(self.app._state_poll_id)

        cancelled = []
        real_cancel = self.app.root.after_cancel
        self.app.root.after_cancel = lambda ident: (cancelled.append(ident), real_cancel(ident))
        ids = {self.app._queue_poll_id, self.app._state_poll_id}
        self.app.close()
        self.assertTrue(ids <= set(cancelled))
        self.assertIsNone(self.app._queue_poll_id)
        self.assertIsNone(self.app._state_poll_id)
        self.assertTrue(self.app.closed)

    def test_close_during_an_attempt_does_not_wait_for_it(self):
        self.link.gate.clear()
        self.link.open = False
        self.app._poll_hardware_state()  # automatic retry begins and blocks in the worker
        self.assertTrue(self.link.started.wait(2))
        started = time.monotonic()
        self.app.close()
        self.assertLess(time.monotonic() - started, 1.0)
        self.link.gate.set()
        deadline = time.monotonic() + 2
        while not self.link.disconnect_threads and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNot(self.link.disconnect_threads[0], threading.main_thread())


if __name__ == "__main__":
    unittest.main()
