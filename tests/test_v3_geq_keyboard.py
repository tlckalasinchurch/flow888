"""V3-D04: the v3 OUTPUT graphic EQ is operable from the keyboard, through the same mapping as the mouse.

Range and step come from v3.js: -15..+15 dB, 0.5 dB steps (the mouse snaps to 0.5), raw value from
dbToEqRaw (-15 -> 0, 0 -> 64, +15 -> 127), sent as setBusGeq {bus, band 1-9, value raw}; the hub maps
it to CC 11-19 on MIDI channel 8 (main), 9 (mon1), 10 (mon2).
Browser tests (Playwright + Chromium, real Flow8LanHub, fake MIDI OUT driver) skip when Playwright or
Chromium is missing. No physical port is opened. Evidence: docs/audit/FLOW8_DEFECT_REGISTER.md (V3-D04).
"""

from __future__ import annotations

import math
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


def js_round(x):
    return math.floor(x + 0.5)


def db_to_raw(db):
    """Reference copy of v3.js dbToEqRaw, to check the bytes independently."""
    c = max(-15.0, min(15.0, db))
    if c == 0:
        return 64
    return max(0, js_round(64 + (c / 15) * 64)) if c < 0 else min(127, js_round(64 + (c / 15) * 63))


def raw_to_db(raw):
    """Reference copy of v3.js eqRawToDb: what a raw value means once the page reloads it."""
    return 0.0 if raw == 64 else ((raw - 64) / 64) * 15 if raw < 64 else ((raw - 64) / 63) * 15


def shown(raw):
    """aria-valuenow after reload: the raw value's dB, to the 0.1 dB the band label shows."""
    return js_round(raw_to_db(raw) * 10) / 10


BUS_CH = {"main": 8, "mon1": 9, "mon2": 10}


@unittest.skipUnless(BROWSER, "Playwright with Chromium is not installed")
class GeqKeyboardTests(NoHardwareMixin, unittest.TestCase):
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
        self.geq = []
        orig = self.hub.dispatch_action

        def record(msg):
            code, res = orig(msg)
            if msg.get("action") == "setBusGeq":
                self.geq.append(({k: v for k, v in msg.items() if k != "clientId"}, code))
            return code, res
        self.hub.dispatch_action = record
        self.ctx = self.browser.new_context(viewport={"width": 1366, "height": 768})
        self.addCleanup(self.ctx.close)
        self.ctx.add_init_script("localStorage.setItem('flow888.v3.page', '\"output\"');")
        self.page = self.ctx.new_page()
        self.page.goto(self.base + "/v3/")
        self.page.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
        self.page.wait_for_selector("#geq-0")

    # ---- helpers ----
    def band(self, i=0):
        return f"#geq-{i}"

    def press(self, key, i=0, times=1):
        self.page.focus(self.band(i))
        for _ in range(times):
            self.page.keyboard.press(key)
            self.page.wait_for_timeout(250)
        self.page.wait_for_timeout(350)

    def aria_now(self, i=0):
        v = self.page.get_attribute(self.band(i), "aria-valuenow")
        return None if v is None else float(v)

    def last_raw(self):
        return self.geq[-1][0]["value"]

    def assert_midi_matches_last(self, bus="main"):
        msg, code = self.geq[-1]
        self.assertEqual(code, 200)
        self.assertEqual(self.driver.midiOutShortMsg.call_args_list[-1].args[1],
                         dword(BUS_CH[bus], 10 + msg["band"], msg["value"]))

    # ---- 1. focus by Tab ----
    def test_tab_reaches_the_first_band_after_the_mix_buttons(self):
        self.page.focus('.page-head [data-mix="mon2"]')
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "geq-0")
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "geq-1")

    # ---- 2-5. arrows ----
    def test_arrow_up_and_right_raise_by_half_a_db(self):
        self.press("ArrowUp")
        self.assertEqual(self.geq[-1][0], {"action": "setBusGeq", "bus": "main", "band": 1, "value": db_to_raw(0.5)})
        self.press("ArrowRight")
        self.assertEqual(self.last_raw(), db_to_raw(1.0))
        self.assertEqual(self.aria_now(), shown(db_to_raw(1.0)))
        self.assert_midi_matches_last()

    def test_arrow_down_and_left_lower_by_half_a_db(self):
        self.press("ArrowDown", i=8)
        self.assertEqual(self.geq[-1][0], {"action": "setBusGeq", "bus": "main", "band": 9, "value": db_to_raw(-0.5)})
        self.press("ArrowLeft", i=8)
        self.assertEqual(self.geq[-1][0]["value"], db_to_raw(-1.0))
        self.assertEqual(self.aria_now(8), shown(db_to_raw(-1.0)))
        self.assert_midi_matches_last()

    def test_repeated_presses_accumulate_and_keep_focus(self):
        self.press("ArrowUp", times=5)
        self.assertEqual([m["value"] for m, _ in self.geq], [db_to_raw(0.5 * k) for k in range(1, 6)])
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "geq-0")
        self.assertEqual(self.aria_now(), shown(db_to_raw(2.5)))

    # ---- 6-8. Home / End / bounds ----
    def test_home_goes_to_minimum_and_end_to_maximum(self):
        self.press("Home", i=2)
        self.assertEqual((self.last_raw(), self.aria_now(2)), (0, -15.0))
        self.press("End", i=2)
        self.assertEqual((self.last_raw(), self.aria_now(2)), (127, 15.0))
        self.assert_midi_matches_last()

    def test_cannot_pass_the_limits(self):
        self.press("End", i=3)
        n = len(self.geq)
        self.press("ArrowUp", i=3, times=2)
        self.assertEqual(self.aria_now(3), 15.0)
        self.assertTrue(all(m["value"] == 127 for m, _ in self.geq[n:]), self.geq[n:])
        self.press("Home", i=3)
        n = len(self.geq)
        self.press("ArrowDown", i=3, times=2)
        self.assertEqual(self.aria_now(3), -15.0)
        self.assertTrue(all(m["value"] == 0 for m, _ in self.geq[n:]), self.geq[n:])

    # ---- 9. ARIA ----
    def test_aria_range_and_value_match_the_control(self):
        attrs = self.page.evaluate("(() => { const e = document.querySelector('#geq-4'); return ['role','aria-valuemin','aria-valuemax','aria-valuenow','aria-valuetext','aria-label','tabindex'].map(a => e.getAttribute(a)); })()")
        self.assertEqual(attrs[:3], ["slider", "-15", "15"])
        self.assertIsNone(attrs[3], "no aria-valuenow while the value is not known")
        self.assertEqual(attrs[4], "unknown")
        self.assertEqual(attrs[5:], ["1k Hz", "0"])
        self.press("ArrowUp", i=4, times=3)
        self.assertEqual(self.last_raw(), db_to_raw(1.5))
        now = self.aria_now(4)
        self.assertEqual(now, shown(db_to_raw(1.5)))
        label = self.page.text_content('.geq-band b[data-i="4"]')
        self.assertEqual(float(label), now, "screen-reader value = visible value")
        self.assertEqual(self.page.get_attribute("#geq-4", "aria-valuetext"), f"{label} dB")
        # between key press and reload the value shown is the 0.5 dB step itself
        self.page.focus("#geq-4")
        self.page.keyboard.press("ArrowUp")
        self.assertEqual(self.aria_now(4), 2.0)

    # ---- 11. payload per bus ----
    def test_payload_and_bytes_follow_the_selected_bus(self):
        self.page.click('.page-head [data-mix="mon1"]')
        self.page.wait_for_selector("#geq-6")
        self.press("ArrowUp", i=6)
        self.assertEqual(self.geq[-1][0], {"action": "setBusGeq", "bus": "mon1", "band": 7, "value": db_to_raw(0.5)})
        self.assert_midi_matches_last("mon1")

    # ---- 12. mouse unchanged ----
    def test_mouse_drag_still_sends_through_the_same_mapping(self):
        box = self.page.locator("#geq-0").bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        for k in range(1, 9):
            self.page.mouse.move(x, y - 5 * k)
            self.page.wait_for_timeout(30)
        self.page.mouse.up()
        self.page.wait_for_timeout(600)
        raw = self.last_raw()
        self.assertIn(raw, {db_to_raw(k * 0.5) for k in range(-30, 31)}, "mouse snaps to 0.5 dB steps")
        self.assertEqual(self.aria_now(), shown(raw))
        self.assert_midi_matches_last()

    # ---- 13. no focus, no keys ----
    def test_arrows_do_nothing_without_focus(self):
        self.page.click("h1")
        for key in ("ArrowUp", "ArrowRight", "Home", "End"):
            self.page.keyboard.press(key)
        self.page.wait_for_timeout(400)
        self.assertEqual(self.geq, [])

    def test_arrows_do_not_scroll_the_page(self):
        self.page.set_viewport_size({"width": 1366, "height": 500})
        self.page.wait_for_timeout(300)
        self.page.evaluate("document.querySelector('#stage').scrollTop = 40")
        before = self.page.evaluate("document.querySelector('#stage').scrollTop")
        self.press("ArrowDown")
        self.press("ArrowUp")
        self.assertEqual(self.page.evaluate("document.querySelector('#stage').scrollTop"), before)

    def test_locked_or_offline_keys_send_nothing(self):
        box = self.page.locator("#btn-lock").bounding_box()
        self.page.mouse.move(box["x"] + 5, box["y"] + 5)
        self.page.mouse.down(); self.page.wait_for_timeout(950); self.page.mouse.up()
        self.page.wait_for_timeout(300)
        self.press("ArrowUp")
        self.assertEqual(self.geq, [])


if __name__ == "__main__":
    unittest.main()
