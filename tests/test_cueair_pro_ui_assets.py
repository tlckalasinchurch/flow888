"""Static guard for the CueAir Pro UI layer: navigation only, no direct hardware access."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from flow8 import web_console

UI = Path(web_console.__file__).parent / "web_ui"


class CueAirProUiTests(unittest.TestCase):
    def setUp(self):
        self.html = (UI / "index.html").read_text(encoding="utf-8")
        self.js = (UI / "app.js").read_text(encoding="utf-8")
        self.css = (UI / "styles.css").read_text(encoding="utf-8")

    def test_browser_never_talks_to_hardware(self):
        for api in ("requestMIDIAccess", "navigator.bluetooth", "navigator.usb", "WebSocket("):
            self.assertNotIn(api, self.js)

    def test_three_areas_exist(self):
        for marker in ('id="side-nav"', 'id="sel-panel"', 'id="layer-tabs"', 'class="app-header"'):
            self.assertIn(marker, self.html)

    def test_sidebar_covers_every_section(self):
        goes = set(re.findall(r'class="side-item" data-go="(\w+)"', self.html))
        self.assertEqual(goes, {"mixer", "channel", "eq", "comp", "sends", "fx", "presets", "setup"})

    def test_chrome_block_sends_no_command_itself(self):
        start = self.js.index("// ---------- Chrome: sidebar")
        end = self.js.index("function setView(")
        chrome = self.js[start:end]
        self.assertNotIn("postAction(", chrome)
        self.assertNotIn("quietAction(", chrome)
        self.assertNotIn("fetch(", chrome)
        self.assertNotIn("action:", chrome)

    def test_gate_and_solo_are_shown_as_unavailable(self):
        self.assertIn("sp-tile unavailable", self.js)
        self.assertIn('disabled aria-disabled="true"', self.js)
        self.assertIn("Solo and Gate: not available", self.js)

    def test_touch_targets_are_at_least_44px_on_coarse_pointers(self):
        self.assertRegex(self.css, re.compile(r"\.icon-btn\s*\{[^}]*width:\s*44px;\s*height:\s*44px", re.S))
        self.assertRegex(
            self.css,
            re.compile(r"@media \(pointer: coarse\) \{ \.layer-tab, \.side-item[^}]*min-height:\s*44px", re.S))


if __name__ == "__main__":
    unittest.main()
