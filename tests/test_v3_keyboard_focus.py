"""V3-D09: a keyboard step on a fader, EQ node or send cell must keep focus on that control.

Each step reloads the session and render() rebuilds the page; render() restores focus only to an
element with an id. Before the fix the fader wells, EQ nodes and send cells had no id, focus fell to
<body> after the first step and every later arrow press did nothing. Payloads are unchanged: one
setFader / setEqBand / setSend per press, through the hub and the command boundary.
Browser tests (Playwright + Chromium, real Flow8LanHub, fake MIDI OUT driver) skip when Playwright
or Chromium is missing. No physical port is opened.
Evidence: docs/audit/FLOW8_UI_REFINEMENT_AUDIT.md (F18).
"""

from __future__ import annotations

import unittest
from ctypes import wintypes
from unittest import mock

from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service
from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import fake_open_port

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _pw:
        _pw.chromium.launch().close()
    BROWSER = True
except Exception:
    BROWSER = False


@unittest.skipUnless(BROWSER, "Playwright with Chromium is not installed")
class KeyboardFocusTests(NoHardwareMixin, unittest.TestCase):
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
        self.sent = []
        orig = self.hub.dispatch_action

        def record(msg):
            code, res = orig(msg)
            self.sent.append(({k: v for k, v in msg.items() if k != "clientId"}, code))
            return code, res
        self.hub.dispatch_action = record
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.addCleanup(self.ctx.close)
        self.ctx.add_init_script("localStorage.setItem('flow888.v3.page', '\"mix\"');")

    def open(self, proc):
        self.hub.dispatch_action({"action": "setFader", "channel": 2, "value": 96})  # a known start value
        self.ctx.add_init_script(f"localStorage.setItem('flow888.v3.proc', '\"{proc}\"');")
        self.page = self.ctx.new_page()
        self.page.goto(self.base + "/v3/")
        self.page.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
        self.page.wait_for_selector(".ws .bank .strip")

    def step(self, selector, presses=3):
        self.page.focus(selector)
        before = len(self.sent)
        for _ in range(presses):
            self.page.keyboard.press("ArrowUp")
            self.page.wait_for_timeout(400)  # the step's reload and re-render run in between
        return [m for m, code in self.sent[before:] if code == 200], self.page.evaluate("document.activeElement.id")

    def test_fader_keeps_focus_and_every_press_is_sent(self):
        self.open("eq")
        sel = ".ws .bank .strip:nth-child(2) .well"
        fid = self.page.get_attribute(sel, "id")
        self.assertTrue(fid)
        sent, active = self.step(sel)
        faders = [m for m in sent if m["action"] == "setFader"]
        self.assertEqual([(m["channel"], m["value"]) for m in faders], [(2, 97), (2, 98), (2, 99)])
        self.assertEqual(active, fid)

    def test_eq_node_keeps_focus_and_every_press_is_sent(self):
        self.open("eq")
        # Band 1 (LOW): the hub reports one EQ provenance per channel, read from LOW (lan_hub.py), so
        # LOW is the band whose steps accumulate from a fresh start. See F19 in the audit.
        sent, active = self.step('.eq-node[data-k="0"]')
        eq = [m for m in sent if m["action"] == "setEqBand"]
        self.assertEqual([m["band"] for m in eq], ["low"] * 3)
        self.assertEqual([m["value"] for m in eq], [66, 68, 70])  # 0.5, 1.0, 1.5 dB through dbToEqRaw
        self.assertEqual(active, "eqn-0")

    def test_send_cell_keeps_focus_and_every_press_is_sent(self):
        self.open("monsend")
        sent, active = self.step('.sends1 .cell[data-m="mon1"]')
        sends = [m for m in sent if m["action"] == "setSend"]
        self.assertEqual([(m["channel"], m["target"], m["value"]) for m in sends], [(1, "mon1", 1), (1, "mon1", 2), (1, "mon1", 3)])
        self.assertEqual(active, "cell-1-mon1")


if __name__ == "__main__":
    unittest.main()
