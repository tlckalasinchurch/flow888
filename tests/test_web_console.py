"""Default launcher: web console, legacy Tk behind --legacy-tk, no port in tests."""

from __future__ import annotations

import argparse
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from flow8 import web_console

ROOT = Path(__file__).resolve().parent.parent


class FakeService:
    def __init__(self, auto_connect=True):
        self.connected = False
        self.connects = 0
        self.disconnects = 0
        self.auto_connect = auto_connect

    @property
    def is_connected(self):
        return self.connected

    def connect(self, quiet=False):
        self.connects += 1
        self.connected = True
        return True

    def check_connection_health(self):
        return True

    def disconnect(self):
        self.disconnects += 1
        self.connected = False


class FakeHub:
    instances = []

    def __init__(self, service, host="0.0.0.0", port=0, library_path=None):
        self.service = service
        self.host = host
        self.port = port
        self.library_path = library_path
        self.started = False
        self.stopped = False
        FakeHub.instances.append(self)

    def start(self):
        self.started = True
        return self.port or 8123

    def stop(self):
        self.stopped = True

    def lan_urls(self):
        return ["http://192.168.1.50:8123"]

    def publish_meters(self, levels):
        pass

    def set_meter_status(self, status):
        self.meter_status = status


class FakeMeter:
    instances = []

    def __init__(self, publish, status):
        self.status = {"state": "no_device", "detail": "test meter"}
        self.started = False
        self.ensured = False
        self.stopped = False
        FakeMeter.instances.append(self)

    def start(self):
        self.started = True
        return False

    def ensure_running(self):
        self.ensured = True
        return False

    def stop(self):
        self.stopped = True


def args(**overrides):
    values = dict(port=8123, host="0.0.0.0", no_browser=False,
                  no_app_window=False, no_meters=False, legacy_tk=False)
    values.update(overrides)
    return argparse.Namespace(**values)


class ParserTests(unittest.TestCase):
    def test_default_is_the_web_console_with_meters(self):
        parsed = web_console.build_parser().parse_args([])
        self.assertFalse(parsed.legacy_tk)
        self.assertFalse(parsed.no_meters)
        self.assertFalse(parsed.no_browser)
        self.assertEqual(parsed.port, web_console.DEFAULT_LAN_PORT)

    def test_legacy_flag_and_options(self):
        parsed = web_console.build_parser().parse_args(
            ["--legacy-tk", "--port", "9000", "--no-meters", "--no-app-window"])
        self.assertTrue(parsed.legacy_tk)
        self.assertEqual(parsed.port, 9000)
        self.assertTrue(parsed.no_meters)
        self.assertTrue(parsed.no_app_window)

    def test_console_url(self):
        self.assertEqual(web_console.console_url(8844), "http://127.0.0.1:8844")


class RunTests(unittest.TestCase):
    def setUp(self):
        FakeHub.instances.clear()
        FakeMeter.instances.clear()
        self.out = io.StringIO()

    def _run(self, parsed, **kwargs):
        defaults = dict(
            service_factory=FakeService,
            hub_factory=FakeHub,
            meter_factory=FakeMeter,
            browser_finder=lambda: None,
            loop_limit=1,
            sleep=lambda _seconds: None,
        )
        defaults.update(kwargs)
        with redirect_stdout(self.out):
            return web_console.run(parsed, **defaults)

    def test_starts_hub_meters_and_opens_the_console(self):
        opened = []
        code = self._run(args(), opener=opened.append)

        self.assertEqual(code, 0)
        hub = FakeHub.instances[-1]
        self.assertTrue(hub.started and hub.stopped)
        self.assertEqual(hub.host, "0.0.0.0")
        meter = FakeMeter.instances[-1]
        self.assertTrue(meter.started and meter.ensured and meter.stopped)
        self.assertEqual(opened, ["http://127.0.0.1:8123"])
        text = self.out.getvalue()
        self.assertIn("http://127.0.0.1:8123", text)
        self.assertIn("http://192.168.1.50:8123", text)

    def test_no_browser_and_no_meters_are_honoured(self):
        opened = []
        code = self._run(args(no_browser=True, no_meters=True), opener=opened.append)
        self.assertEqual(code, 0)
        self.assertEqual(opened, [])
        self.assertEqual(FakeMeter.instances, [])
        self.assertIn("Meters        : off", self.out.getvalue())

    def test_app_window_uses_the_browser_binary(self):
        popen_calls = []

        class Process:
            def poll(self):
                return None

        def fake_popen(argv):
            popen_calls.append(argv)
            return Process()

        code = self._run(args(), browser_finder=lambda: "C:/Edge/msedge.exe", popen=fake_popen)
        self.assertEqual(code, 0)
        self.assertEqual(popen_calls[0][0], "C:/Edge/msedge.exe")
        self.assertEqual(popen_calls[0][1], "--app=http://127.0.0.1:8123")

    def test_legacy_tk_runs_the_desktop_window(self):
        with mock.patch("flow8.ui.app.main", return_value=7) as tk_main:
            with mock.patch.object(web_console, "run", side_effect=AssertionError("web console started")):
                self.assertEqual(web_console.main(["--legacy-tk"]), 7)
        tk_main.assert_called_once_with([])

    def test_main_defaults_to_the_web_console(self):
        with mock.patch.object(web_console, "run", return_value=0) as run:
            self.assertEqual(web_console.main(["--port", "9001", "--no-browser"]), 0)
        parsed = run.call_args[0][0]
        self.assertEqual(parsed.port, 9001)
        self.assertTrue(parsed.no_browser)


class EntryPointTests(unittest.TestCase):
    def test_main_py_is_the_web_console(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from flow8.web_console import main", text)

    def test_old_launcher_is_an_alias(self):
        text = (ROOT / "launch_studio_ui.py").read_text(encoding="utf-8")
        self.assertIn("from flow8.web_console import main", text)

    def test_batch_files_launch_the_right_surface(self):
        studio = (ROOT / "start_studio.bat").read_text(encoding="utf-8")
        legacy = (ROOT / "start_legacy_tk.bat").read_text(encoding="utf-8")
        self.assertIn("python main.py", studio)
        self.assertNotIn("--legacy-tk", studio)
        self.assertIn("--legacy-tk", legacy)


if __name__ == "__main__":
    unittest.main()
