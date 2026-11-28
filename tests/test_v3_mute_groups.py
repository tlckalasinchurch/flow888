"""V3-D02: a v3 mute-group lamp shows what the hub knows about its channels, never a guess.

Browser tests drive the real v3 page (Playwright, Chromium) against a real Flow8LanHub whose
MIDI OUT is the fake driver from _safety_helpers. They skip when Playwright or its Chromium
is not installed. No physical port is opened: NoHardwareMixin makes any open raise, and
MIDI IN is only flagged open with a fake handle (winmm is never called).
Evidence: docs/audit/FLOW8_DEFECT_REGISTER.md (V3-D02).
"""

from __future__ import annotations

import json
import re
import unittest
from unittest import mock
from ctypes import wintypes
from pathlib import Path

from flow8 import web_console
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service
from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import dword, fake_open_port

V3_JS = Path(web_console.__file__).parent / "web_ui" / "v3" / "v3.js"
GROUPS = [
    {"name": "GROUP A", "members": [1, 2]},
    {"name": "GROUP B", "members": [3]},
    {"name": "GROUP C", "members": []},
    {"name": "GROUP D", "members": []},
]

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _pw:
        _pw.chromium.launch().close()
    BROWSER = True
except Exception:  # not installed, or no Chromium build
    BROWSER = False


class GroupStateSourceTests(unittest.TestCase):
    """Static guards: the lamp is derived, never stored."""

    def setUp(self):
        self.js = V3_JS.read_text(encoding="utf-8")

    def test_no_client_side_on_flag(self):
        self.assertNotRegex(self.js, r"\bg\.on\b", "a group's ON state must not be a browser flag")
        self.assertNotRegex(self.js, r"\bx\.on\b")
        self.assertNotIn("on: false", self.js)

    def test_lamp_is_derived_from_channel_mute_provenance(self):
        body = re.search(r"function groupState\(g\) \{(.*?)\n  \}", self.js, re.S)
        self.assertIsNotNone(body, "groupState(g) must exist")
        self.assertIn("muteProvenance", body.group(1))


@unittest.skipUnless(BROWSER, "Playwright with Chromium is not installed")
class MuteGroupBrowserTests(NoHardwareMixin, unittest.TestCase):
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
        self.responses = []
        orig = self.hub.dispatch_action

        def record(msg):
            code, res = orig(msg)
            self.responses.append((msg.get("action"), msg.get("channel"), msg.get("value"), code))
            return code, res
        self.hub.dispatch_action = record
        self.ctx = self.browser.new_context(viewport={"width": 1366, "height": 768})
        self.addCleanup(self.ctx.close)
        self.ctx.add_init_script(
            f"localStorage.setItem('flow888.v3.groups', {json.dumps(json.dumps(GROUPS))});"
            "localStorage.setItem('flow888.v3.page', '\"mix\"');")
        self.page = self.open_page()

    def open_page(self):
        page = self.ctx.new_page()
        page.goto(self.base + "/v3/")
        page.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
        page.wait_for_selector('.grp[data-g="0"]')
        return page

    def lamp(self, i, page=None):
        return (page or self.page).get_attribute(f'.grp[data-g="{i}"]', "aria-pressed")

    def refresh(self, page=None):
        """Another client's command: a state event, then this client's reload."""
        self.hub.broadcast({"type": "state"})
        (page or self.page).wait_for_timeout(500)

    def set_hub_up(self, up):
        self.service.midi_out._is_open = up
        self.service._connected = up

    def tap(self, i):
        self.page.click(f'.grp[data-g="{i}"]')
        self.page.wait_for_timeout(600)

    # 1. success -> confirmed state
    def test_success_lights_the_lamp_from_confirmed_mutes(self):
        self.service.set_mute(1, False)
        self.service.set_mute(2, False)
        self.refresh()
        self.assertEqual(self.lamp(0), "false")
        self.tap(0)
        self.assertEqual([r for r in self.responses if r[0] == "setMute"], [("setMute", 1, True, 200), ("setMute", 2, True, 200)])
        self.assertEqual(self.lamp(0), "true")
        self.tap(0)
        self.assertEqual(self.lamp(0), "false")
        # 6. bytes on the wire unchanged: mute = CC5 on the channel, 127 / 0
        sent = [c.args[1] for c in self.driver.midiOutShortMsg.call_args_list]
        self.assertEqual(sent[-4:], [dword(1, 5, 127), dword(2, 5, 127), dword(1, 5, 0), dword(2, 5, 0)])

    # 2. hub answers 503 -> no success shown
    def test_503_does_not_light_the_lamp(self):
        self.service.set_mute(3, False)
        self.refresh()
        self.set_hub_up(False)  # the page still shows CONNECTED until its next reload
        before = len(self.driver.midiOutShortMsg.call_args_list)
        self.tap(1)
        self.assertIn(("setMute", 3, True, 503), self.responses)
        self.assertNotEqual(self.lamp(1), "true")
        self.assertEqual(len(self.driver.midiOutShortMsg.call_args_list), before)

    # 3. hub answers an error (dispatch failure) -> no success shown
    def test_dispatch_error_does_not_light_the_lamp(self):
        self.service.set_mute(3, False)
        self.refresh()
        self.driver.midiOutShortMsg.return_value = 6  # MMSYSERR_INVALHANDLE: driver refuses
        self.tap(1)
        codes = [r[3] for r in self.responses if r[0] == "setMute"]
        self.assertTrue(codes and all(c != 200 for c in codes), codes)
        self.assertNotEqual(self.lamp(1), "true")

    # 4. reconnect -> lamp follows the hub's channel data (unknown after a reconcile)
    def test_reconnect_shows_unknown_not_a_remembered_on(self):
        self.tap(0)
        self.assertEqual(self.lamp(0), "true")
        self.service._drop_connection()  # disconnect: every value back to UNSYNCED
        self.set_hub_up(True)
        self.service.reconcile_connection()
        self.refresh()
        self.assertEqual(self.lamp(0), "mixed", "unknown member mutes must read as unknown, not ON")

    # 5. reload / second device -> state from the hub, not from local memory
    def test_reload_and_second_device_read_the_hub(self):
        self.tap(0)
        self.page.reload()
        self.page.wait_for_selector('.grp[data-g="0"]')
        self.page.wait_for_timeout(400)
        self.assertEqual(self.lamp(0), "true")
        other = self.open_page()
        other.wait_for_timeout(400)
        self.assertEqual(self.lamp(0, other), "true")
        # the mixer side changes (another device unmutes ch2): the lamp follows
        self.service.set_mute(2, False)
        self.refresh(other)
        self.assertEqual(self.lamp(0, other), "false")

    def test_unknown_members_read_unknown_and_tap_mutes(self):
        self.assertEqual(self.lamp(0), "mixed")  # fresh hub: ch1/ch2 UNSYNCED
        self.tap(0)
        self.assertEqual([r[:3] for r in self.responses if r[0] == "setMute"], [("setMute", 1, True), ("setMute", 2, True)])
        self.assertEqual(self.lamp(0), "true")

    def test_channel_held_by_another_on_group_stays_muted(self):
        self.ctx.add_init_script(
            "localStorage.setItem('flow888.v3.groups', JSON.stringify([{name:'GROUP A',members:[1,2]},{name:'GROUP B',members:[2]},{name:'GROUP C',members:[]},{name:'GROUP D',members:[]}]))")
        self.page.reload(); self.page.wait_for_selector('.grp[data-g="1"]')
        self.tap(0)
        self.tap(1)  # B (ch2) already all muted -> it reads ON
        self.assertEqual(self.lamp(1), "true")
        self.responses.clear()
        self.tap(0)  # A off: ch1 unmutes, ch2 stays muted for B
        self.assertEqual([r[:3] for r in self.responses if r[0] == "setMute"], [("setMute", 1, False), ("setMute", 2, True)])
        self.assertEqual(self.lamp(0), "false")
        self.assertEqual(self.lamp(1), "true")


if __name__ == "__main__":
    unittest.main()
