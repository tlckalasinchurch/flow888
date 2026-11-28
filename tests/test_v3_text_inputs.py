"""V3-D01 / V3-D03: text being typed in v3 survives a re-render, with its focus and caret.

v3 rebuilds the page with innerHTML on every session reload (every 5 s, and after any other
client's command), so these tests type into the real page and force those re-renders.
Browser tests use Playwright + Chromium against a real Flow8LanHub whose MIDI OUT is the fake
driver; they skip when Playwright or Chromium is missing. No physical port is opened.
Evidence: docs/audit/FLOW8_DEFECT_REGISTER.md (V3-D01, V3-D03).
"""

from __future__ import annotations

import json
import unittest
from unittest import mock
from ctypes import wintypes
from pathlib import Path

from flow8 import web_console
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service
from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import fake_open_port

V3_JS = Path(web_console.__file__).parent / "web_ui" / "v3" / "v3.js"
GROUPS = [
    {"name": "GROUP A", "members": [1]},
    {"name": "GROUP B", "members": [2]},
    {"name": "GROUP C", "members": []},
    {"name": "GROUP D", "members": []},
]

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _pw:
        _pw.chromium.launch().close()
    BROWSER = True
except Exception:
    BROWSER = False


class TextInputStaticTests(unittest.TestCase):
    def setUp(self):
        self.js = V3_JS.read_text(encoding="utf-8")

    def test_group_name_input_has_a_stable_id(self):
        self.assertIn('id="grp-name"', self.js)

    def test_cue_name_is_rendered_from_ui_state(self):
        self.assertIn('id="cue-name"', self.js)
        self.assertIn("ui.cueDraft", self.js)


@unittest.skipUnless(BROWSER, "Playwright with Chromium is not installed")
class TextInputBrowserTests(NoHardwareMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        super().setUp()
        self.service = Flow8Service(auto_connect=False)
        _, self.driver = fake_open_port(self.service.midi_out)
        mi = self.service.midi_in
        mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
        mi._winmm = mock.MagicMock()  # close()/stop() must never reach the real winmm
        self.service._connected = True
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
        self.base = f"http://127.0.0.1:{self.hub.start()}"
        self.addCleanup(self.hub.stop)
        self.actions = []
        orig = self.hub.dispatch_action

        def record(msg):
            code, res = orig(msg)
            self.actions.append(({k: v for k, v in msg.items() if k != "clientId"}, code))
            return code, res
        self.hub.dispatch_action = record
        self.ctx = self.browser.new_context(viewport={"width": 1366, "height": 768})
        self.addCleanup(self.ctx.close)
        self.ctx.add_init_script(f"localStorage.setItem('flow888.v3.groups', {json.dumps(json.dumps(GROUPS))});")
        self.page = self.ctx.new_page()
        self.page.goto(self.base + "/v3/")
        self.page.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)

    # ---- helpers ----
    def goto(self, name):
        self.page.click(f'#rail button[data-page="{name}"]')
        self.page.wait_for_timeout(200)

    def external_action(self):
        """A real command from another device: POST without this page's clientId."""
        r = self.page.request.post(self.base + "/api/action", data=json.dumps({"action": "setFader", "channel": 3, "value": 40}),
                                   headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 200)
        self.page.wait_for_timeout(500)

    def state_event(self):
        self.hub.broadcast({"type": "state"})
        self.page.wait_for_timeout(500)

    def local_rerender(self):
        """v3 re-renders on resize (150 ms debounce)."""
        self.page.set_viewport_size({"width": 1360, "height": 768})
        self.page.wait_for_timeout(400)

    def focus_info(self):
        return self.page.evaluate(
            "(() => { const e = document.activeElement; return {id: e && e.id, value: e && e.value, "
            "start: e && e.selectionStart, end: e && e.selectionEnd}; })()")

    def cue_name(self):
        return self.page.eval_on_selector("#cue-name", "e => e.value")

    def type_cue(self, text):
        self.goto("show")
        self.page.click("#cue-name")
        self.page.keyboard.type(text, delay=15)

    def open_group_editor(self, i):
        box = self.page.locator(f'.grp[data-g="{i}"]').bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.page.wait_for_timeout(750)
        self.page.mouse.up()
        self.page.wait_for_selector("#grp-name")

    # ---- D01 ----
    def test_cue_name_survives_a_local_rerender(self):
        self.type_cue("Worship set")
        self.local_rerender()
        self.assertEqual(self.cue_name(), "Worship set")

    def test_cue_name_survives_another_devices_command(self):
        self.type_cue("Worship set")
        self.external_action()
        self.assertEqual(self.cue_name(), "Worship set")
        self.assertEqual(self.focus_info()["id"], "cue-name")

    def test_cue_name_survives_the_5_second_reload(self):
        self.type_cue("Sermon")
        self.page.wait_for_timeout(5600)
        self.assertEqual(self.cue_name(), "Sermon")

    def test_cue_name_caret_is_kept(self):
        self.type_cue("Worship set")
        self.page.keyboard.press("Home")
        for _ in range(3):
            self.page.keyboard.press("ArrowRight")
        self.state_event()
        f = self.focus_info()
        self.assertEqual((f["id"], f["start"], f["end"]), ("cue-name", 3, 3))
        self.page.keyboard.type("X")
        self.assertEqual(self.cue_name(), "WorXship set")

    def test_save_sends_the_same_payload_and_clears_on_success(self):
        self.service.set_fader(1, 90)  # the hub saves only known values
        sent_before = len(self.driver.midiOutShortMsg.call_args_list)
        self.type_cue("  Opening  ")
        self.page.click("#cue-add")
        self.page.wait_for_timeout(600)
        saves = [a for a in self.actions if a[0].get("action") == "librarySave"]
        self.assertEqual(saves, [({"action": "librarySave", "name": "Opening"}, 200)])
        self.assertEqual(self.cue_name(), "")
        names = [c.get("name") for c in self.page.evaluate("fetch('/api/session').then(r => r.json()).then(s => s.library)")]
        self.assertIn("Opening", names)
        self.assertEqual(len(self.driver.midiOutShortMsg.call_args_list), sent_before, "saving a cue sends no MIDI")

    def test_refused_save_keeps_the_typed_name(self):
        self.type_cue("Opening")  # fresh hub: no known values, so the hub refuses (400)
        self.page.click("#cue-add")
        self.page.wait_for_timeout(600)
        self.assertEqual([a[1] for a in self.actions if a[0].get("action") == "librarySave"], [400])
        self.assertEqual(self.cue_name(), "Opening")

    def test_empty_name_is_refused_without_a_request(self):
        self.goto("show")
        self.page.click("#cue-add")
        self.page.wait_for_timeout(300)
        self.assertEqual([a for a in self.actions if a[0].get("action") == "librarySave"], [])

    def test_draft_is_not_saved_by_itself(self):
        self.type_cue("Not yet")
        self.page.wait_for_timeout(5600)
        self.assertEqual([a for a in self.actions if a[0].get("action") == "librarySave"], [])

    # ---- D03 ----
    def test_group_name_keeps_focus_and_caret(self):
        self.open_group_editor(0)
        self.page.click("#grp-name")
        self.page.keyboard.press("Home")
        self.page.keyboard.press("ArrowRight")
        self.page.keyboard.press("ArrowRight")
        self.state_event()
        f = self.focus_info()
        self.assertEqual((f["id"], f["start"], f["end"]), ("grp-name", 2, 2))
        self.page.keyboard.press("End")
        self.page.keyboard.type(" ")
        self.local_rerender()
        f = self.focus_info()
        self.assertEqual(f["id"], "grp-name")
        self.assertEqual(f["value"], "GROUP A ", "a trailing space being typed must not be trimmed mid-edit")
        self.assertEqual(f["start"], len("GROUP A "))

    def test_focus_returns_to_the_group_being_edited(self):
        self.open_group_editor(1)
        self.page.fill("#grp-name", "BAND")
        self.page.click("#grp-name")
        self.external_action()
        f = self.focus_info()
        self.assertEqual((f["id"], f["value"]), ("grp-name", "BAND"))
        self.page.click(".grp-done")
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.text_content('.grp[data-g="1"]'), "BAND")
        stored = json.loads(self.page.evaluate("localStorage.getItem('flow888.v3.groups')"))
        self.assertEqual([g["name"] for g in stored], ["GROUP A", "BAND", "GROUP C", "GROUP D"])
        self.assertEqual([a for a in self.actions if a[0].get("action") == "setMute"], [], "editing sends no mute")

    def test_group_name_is_normalised_on_done(self):
        self.open_group_editor(0)
        self.page.fill("#grp-name", "  vox  ")
        self.page.click(".grp-done")
        self.page.wait_for_timeout(300)
        stored = json.loads(self.page.evaluate("localStorage.getItem('flow888.v3.groups')"))
        self.assertEqual(stored[0]["name"], "VOX")


if __name__ == "__main__":
    unittest.main()
