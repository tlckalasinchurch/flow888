"""Static guard: the web console never shows an unknown (UNSYNCED) value as a reading.

Product rule: only a value the app sent (COMMANDED) or the mixer reported (OBSERVED) may be
shown as a value. Anything else renders as "--", and FlowAi gives no advice based on it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from flow8 import web_console

UI = Path(web_console.__file__).parent / "web_ui"


class UiProvenanceDisplayTests(unittest.TestCase):
    def setUp(self):
        self.js = (UI / "app.js").read_text(encoding="utf-8")

    def _function_body(self, name: str) -> str:
        start = self.js.index(f"function {name}(")
        nxt = self.js.find("\n  function ", start + 1)
        return self.js[start:nxt if nxt != -1 else len(self.js)]

    def test_known_means_commanded_or_observed(self):
        self.assertIn("const isKnown = (p) => p === 'COMMANDED' || p === 'OBSERVED';", self.js)

    def test_send_values_are_never_formatted_without_provenance(self):
        # A raw send formatted as dB would turn the default 0 into "-∞ dB".
        self.assertIsNone(re.search(r"midiToDbStr\(ch\.sends", self.js))
        sends_tab = self._function_body("renderCueSendsTab")
        self.assertIn("unknown: !sendKnown(ch, target)", sends_tab)

    def test_channel_tab_guards_every_value(self):
        body = self._function_body("renderCueChannelTab")
        for prov in ("panProvenance", "muteProvenance", "gainProvenance", "lowCutProvenance",
                     "compressorProvenance", "eqProvenance"):
            self.assertIn(prov, body, prov)
        self.assertIn("sendText(ch, 'mon1')", body)

    def test_strip_chips_guard_low_cut_eq_and_sends(self):
        body = self._function_body("stripInfo")
        self.assertIn("isKnown(ch.lowCutProvenance)", body)
        self.assertIn("isKnown(ch.eqProvenance)", body)
        self.assertIn("sendKnown(ch, target)", body)

    def test_flowai_advice_only_from_known_values(self):
        body = self._function_body("renderFlowAiDrawer")
        self.assertIn("lcKnown && (ch.lowCut || 0) < 10", body)
        self.assertIn("eqKnown && eqFlat", body)
        self.assertIn("fx1Known && (ch.sends?.fx1 || 0) === 0", body)
        self.assertIn("badge: 'UNKNOWN'", body)

    def test_input_tab_does_not_claim_phantom_state(self):
        body = self._function_body("renderCueInputTab")
        self.assertIn("isKnown(ch.phantomProvenance)", body)


if __name__ == "__main__":
    unittest.main()
