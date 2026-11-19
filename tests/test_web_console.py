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

    def __init__(self, service, host="0.0.0.0", port=0, library_path=None, show_modes_path=None):
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
        self.assertFalse(parsed.no_meters)
        self.assertFalse(parsed.no_browser)
        self.assertEqual(parsed.port, web_console.DEFAULT_LAN_PORT)

    def test_parser_options(self):
        parsed = web_console.build_parser().parse_args(
            ["--port", "9000", "--no-meters", "--no-app-window"])
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
            reuse_existing=False,
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

    def test_existing_console_is_reused_instead_of_failing_to_bind(self):
        opened = []
        with mock.patch.object(web_console, "existing_console", return_value=True):
            with redirect_stdout(self.out):
                code = web_console.run(
                    args(), service_factory=FakeService, hub_factory=FakeHub,
                    meter_factory=FakeMeter, browser_finder=lambda: None,
                    opener=opened.append,
                )
        self.assertEqual(code, 0)
        self.assertEqual(FakeHub.instances, [], "no second hub may be started")
        self.assertEqual(opened, ["http://127.0.0.1:8123"])
        self.assertIn("already running", self.out.getvalue())

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
        self.assertIn("python main.py", studio)
        self.assertNotIn("--legacy-tk", studio)


class ShowModeAssetsTests(unittest.TestCase):
    """Static guard: the Show Mode controls and their hold time are in the shipped UI."""

    UI = Path(web_console.__file__).parent / "web_ui"

    def test_top_bar_has_show_mode_controls(self):
        html = (self.UI / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="show-modes"', html)
        self.assertIn('id="show-mode-undo"', html)
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("['showmodes', 'Show modes']", js)  # Setup list entry where the editor lives

    def test_show_mode_uses_a_450ms_hold_and_the_run_action(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("SHOW_MODE_HOLD_MS = 450", js)
        self.assertIn("attachHold(btn, SHOW_MODE_HOLD_MS", js)
        self.assertIn("action: 'runShowMode'", js)
        self.assertIn("action: 'saveShowMode'", js)

    def test_undo_chip_is_hidden_when_anything_else_changes_the_mix(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("function hideShowModeUndo", js)
        self.assertIn("ev.action !== 'runShowMode'", js)

    def test_editor_keeps_unsaved_edits_across_reloads(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("showModeDrafts", js)
        self.assertIn("showModeBusy", js)


if __name__ == "__main__":
    unittest.main()


class LinkStatusAssetsTests(unittest.TestCase):
    """Static guard: the status pill states why the mixer is not usable."""

    UI = Path(web_console.__file__).parent / "web_ui"

    def test_link_summary_names_every_usb_diagnosis(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("function linkSummary(", js)
        for key in ("no_midi_devices", "flow8_not_listed", "open_failed", "devicesSeen"):
            self.assertIn(key, js)

    def test_connection_state_is_driven_by_the_link_summary(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("linkSummary(session)", js)
        self.assertIn("openRoutingFromPill", js)

    def test_routing_page_lists_the_midi_devices_windows_sees(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("MIDI OUT SEEN", js)

    def test_pill_is_a_44px_touch_target(self):
        import re
        css = (self.UI / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(css, re.compile(r"\.status-pill\s*\{[^}]*min-height:\s*44px", re.S))


class LiveConsoleLayoutAssetsTests(unittest.TestCase):
    """Static guard: four control classes keep their homes; one fader bank; Setup is full screen."""

    UI = Path(web_console.__file__).parent / "web_ui"

    def _html(self):
        return (self.UI / "index.html").read_text(encoding="utf-8")

    def _block(self, html, open_marker, close_marker):
        start = html.index(open_marker)
        return html[start:html.index(close_marker, start)]

    def test_safety_controls_live_in_the_header_safety_cluster(self):
        header = self._block(self._html(), '<header class="app-header"', "</header>")
        cluster = self._block(header, 'class="safety-cluster"', "</div>")
        self.assertIn('id="btn-lock"', cluster)
        self.assertIn('id="btn-mute-all"', cluster)
        self.assertIn('data-hold="arm"', cluster)  # MUTE ALL keeps its hold-to-arm

    def test_show_control_is_not_part_of_navigation_or_safety(self):
        html = self._html()
        nav = self._block(html, 'id="cue-groups"', "</nav>")
        self.assertNotIn("show-modes", nav)
        control = self._block(html, 'id="control-bar"', "<!-- Views inside")
        self.assertIn('id="show-modes"', control)
        self.assertNotIn("btn-mute-all", control)
        self.assertNotIn("btn-lock", control)

    def test_redo_has_a_text_label_like_undo(self):
        html = self._html()
        self.assertIn("Undo</span>", html)
        self.assertIn("Redo</span>", html)

    def test_setup_has_no_separate_nested_view(self):
        html = self._html()
        self.assertNotIn('id="setup-view"', html)
        self.assertNotIn('id="setup-page"', html)
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("renderMixerOverview", js)  # one fader bank, no duplicate strips
        self.assertIn("setup-layout", js)

    def test_snapshots_and_library_share_one_setup_page(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("['snapshots', 'Snapshots']", js)
        self.assertNotIn("['library',", js)
        self.assertIn("renderLibraryPage(lib)", js)

    def test_bank_size_follows_the_section(self):
        css = (self.UI / "styles.css").read_text(encoding="utf-8")
        self.assertIn('body[data-section="setup"] .console-bank', css)
        self.assertIn('body[data-tab="mixer"] .top-pane { display: none; }', css)
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        self.assertIn("document.body.dataset.section", js)

    def test_active_view_sync_only_sends_values_the_hub_accepts(self):
        js = (self.UI / "app.js").read_text(encoding="utf-8")
        # Flow8Service.set_active_view accepts only 'mixer' or 'stage'.
        self.assertIn("if (tab === 'mixer' || tab === 'stage')", js)
        self.assertIn("view = 'mixer';", js)

    def test_device_fit_safe_areas_large_and_short_screens(self):
        html = self._html()
        css = (self.UI / "styles.css").read_text(encoding="utf-8")
        self.assertIn("viewport-fit=cover", html)
        self.assertIn("apple-mobile-web-app-capable", html)
        self.assertIn("env(safe-area-inset-top", css)  # Safari notch and home indicator
        self.assertIn("env(safe-area-inset-bottom", css)
        self.assertIn("--ui-zoom: 1.5", css)  # large screens scale the whole UI
        self.assertIn("@media (max-height: 520px)", css)  # phone in landscape
        self.assertIn('body[data-section="sound"] .console-bank, body[data-tab="stage"] .console-bank { display: none; }', css)
        self.assertIn('class="toolbars"', html)

    def test_touch_targets_are_44px_on_coarse_pointers(self):
        css = (self.UI / "styles.css").read_text(encoding="utf-8")
        self.assertIn("@media (pointer: coarse)", css)
        self.assertIn("input[type=\"range\"] { min-height: 44px; }", css)
