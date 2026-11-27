"""V3-D05 / V3-D06: v3 refuses SAVE CURRENT MIX while LOCKED and strip MUTE while no mixer.

Browser tests use Playwright + Chromium against a real Flow8LanHub. MIDI OUT is the fake
driver from _safety_helpers; MIDI IN is flagged open with a mock winmm, so a disconnect runs
the real service path (_drop_connection -> reconcile -> SSE "link") without touching a driver.
They skip when Playwright or Chromium is missing. No physical port is opened.
Evidence: docs/audit/FLOW8_DEFECT_REGISTER.md (V3-D05, V3-D06).
"""

from __future__ import annotations

import json
import unittest
from ctypes import wintypes
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service
from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import dword, fake_open_port

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _pw:
        _pw.chromium.launch().close()
    BROWSER = True
except Exception:
    BROWSER = False

NOT_CONNECTED = "The FLOW 8 is not connected. Nothing was sent."


@unittest.skipUnless(BROWSER, "Playwright with Chromium is not installed")
class GuardBrowserTests(NoHardwareMixin, unittest.TestCase):
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
        mi._winmm = mock.MagicMock()
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
        self.ctx.add_init_script("localStorage.setItem('flow888.v3.page', '\"mix\"');")
        self.page = self.ctx.new_page()
        self.page.goto(self.base + "/v3/")
        self.wait_link("CONNECTED")

    # ---- helpers ----
    def wait_link(self, text):
        self.page.wait_for_function(f"document.querySelector('#link .tx').textContent === '{text}'", timeout=8000)

    def goto(self, name):
        self.page.click(f'#rail button[data-page="{name}"]')
        self.page.wait_for_timeout(200)

    def hold(self, selector, ms):
        box = self.page.locator(selector).bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.page.wait_for_timeout(ms)
        self.page.mouse.up()
        self.page.wait_for_timeout(300)

    def toggle_lock(self):
        self.hold("#btn-lock", 950)

    def sent(self, action):
        return [a for a in self.actions if a[0].get("action") == action]

    def midi_count(self):
        return len(self.driver.midiOutShortMsg.call_args_list)

    def toast(self):
        return self.page.evaluate("(() => { const t = document.querySelector('#toast'); return {text: t.textContent, bad: t.classList.contains('bad')}; })()")

    def type_cue(self, text):
        self.goto("show")
        self.page.fill("#cue-name", text)

    def first_mute(self):
        return ".bank .strip >> nth=0 >> .s-mute"

    # ---- D05 ----
    def test_locked_save_button_is_disabled(self):
        self.toggle_lock()
        self.type_cue("Locked")
        self.assertTrue(self.page.is_disabled("#cue-add"))
        self.page.click("#cue-add", force=True)
        self.page.wait_for_timeout(300)
        self.assertEqual(self.sent("librarySave"), [])

    def test_locked_handler_refuses_even_if_the_button_is_enabled_by_script(self):
        self.toggle_lock()
        self.type_cue("Locked")
        self.page.evaluate("(() => { const b = document.querySelector('#cue-add'); b.disabled = false; b.click(); })()")
        self.page.wait_for_timeout(400)
        self.assertEqual(self.sent("librarySave"), [])
        self.assertEqual(self.page.eval_on_selector("#cue-name", "e => e.value"), "Locked", "the typed name is kept")

    def test_unlocked_save_works_as_before(self):
        self.service.set_fader(1, 90)  # the hub saves only known values
        self.toggle_lock()
        self.toggle_lock()  # unlock
        self.type_cue("Opening")
        self.assertFalse(self.page.is_disabled("#cue-add"))
        self.page.click("#cue-add")
        self.page.wait_for_timeout(500)
        self.assertEqual(self.sent("librarySave"), [({"action": "librarySave", "name": "Opening"}, 200)])
        self.assertTrue(self.toast()["text"].startswith('Saved "Opening"'))

    def test_refused_save_shows_no_success(self):
        self.type_cue("Opening")  # fresh hub: nothing known -> 400
        self.page.click("#cue-add")
        self.page.wait_for_timeout(500)
        self.assertEqual([a[1] for a in self.sent("librarySave")], [400])
        t = self.toast()
        self.assertTrue(t["bad"], t)
        self.assertNotIn("Saved", t["text"])

    # ---- D06 ----
    def disconnect(self):
        """The real service path: close endpoints, reconcile, notify (SSE 'link')."""
        self.service._drop_connection()
        self.wait_link("NO MIXER")

    def test_disconnected_mute_sends_nothing_and_says_why(self):
        self.disconnect()
        before = self.midi_count()
        # aria-disabled makes Playwright refuse a normal click; a finger still delivers one.
        self.page.click(self.first_mute(), force=True)
        self.page.wait_for_timeout(400)
        self.assertEqual(self.sent("setMute"), [])
        self.assertEqual(self.midi_count(), before)
        t = self.toast()
        self.assertEqual((t["text"], t["bad"]), (NOT_CONNECTED, True))
        self.assertEqual(self.page.get_attribute(self.first_mute(), "aria-disabled"), "true")

    def test_disconnected_mute_handler_refuses_a_scripted_click(self):
        self.disconnect()
        self.page.evaluate("document.querySelector('.bank .strip .s-mute').click()")
        self.page.wait_for_timeout(400)
        self.assertEqual(self.sent("setMute"), [])

    def test_connected_mute_works_as_before(self):
        self.assertEqual(self.page.get_attribute(self.first_mute(), "aria-disabled"), "false")
        self.page.click(self.first_mute())
        self.page.wait_for_timeout(500)
        self.assertEqual(self.sent("setMute"), [({"action": "setMute", "channel": 1, "value": True}, 200)])
        self.assertEqual(self.driver.midiOutShortMsg.call_args_list[-1].args[1], dword(1, 5, 127))

    def test_guard_follows_a_disconnect_after_page_load_and_a_reconnect(self):
        self.page.click(self.first_mute())  # works while connected
        self.page.wait_for_timeout(400)
        self.disconnect()  # after the page loaded: the guard must use the new state
        self.page.click(self.first_mute(), force=True)
        self.page.wait_for_timeout(400)
        self.assertEqual([a[0]["value"] for a in self.sent("setMute")], [True])
        # reconnect through the same service path: MUTE works again
        mi = self.service.midi_in
        mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
        self.service.midi_out._is_open, self.service.midi_out._handle = True, wintypes.HANDLE(0x1234)
        self.service._connected = True
        self.service.reconcile_connection()
        self.wait_link("CONNECTED")
        self.page.click(self.first_mute())
        self.page.wait_for_timeout(500)
        self.assertEqual([a[1] for a in self.sent("setMute")], [200, 200])

    def test_unannounced_drop_is_still_refused_by_the_hub(self):
        """Between an unplug and the next state update the page cannot know; the hub refuses."""
        self.service.midi_out._is_open = False
        self.service._connected = False  # no event sent: the page still shows CONNECTED
        before = self.midi_count()
        self.page.click(self.first_mute())
        self.page.wait_for_timeout(500)
        self.assertEqual([a[1] for a in self.sent("setMute")], [503])
        self.assertEqual(self.midi_count(), before)
        self.assertTrue(self.toast()["bad"])


if __name__ == "__main__":
    unittest.main()
