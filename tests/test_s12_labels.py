"""S1.2 safety tests: EQ band labels carry no unsourced frequency (decision D5; L-01, L-02)."""
import re
import tkinter as tk
import unittest

from flow8.service import Flow8Service
from flow8.ui import theme
from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget
from flow8.ui.components.mixer_console import MixerConsole

from tests._no_hardware import NoHardwareMixin

FREQUENCY = re.compile(r"\d\s*(k?Hz)", re.I)


def all_text(widget):
    texts = []
    for child in widget.winfo_children():
        try:
            texts.append(str(child.cget("text")))
        except tk.TclError:
            pass
        texts.extend(all_text(child))
    return texts


class EqLabelTests(NoHardwareMixin, unittest.TestCase):
    def test_l01_titles_are_band_numbers(self):
        titles = {key: title for key, title, _ in ChannelDetailPanel.EQ_BANDS}
        self.assertEqual(titles, {"low": "BAND 1", "low_mid": "BAND 2", "hi_mid": "BAND 3", "hi": "BAND 4"})
        for title in titles.values():
            self.assertIsNone(FREQUENCY.search(title))

    def test_l02_rendered_eq_tab_has_no_frequency_figure(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        fonts = theme.build_fonts(root)
        console = MixerConsole(root, fonts, service=Flow8Service(auto_connect=False))
        console.pack(fill="both", expand=True)
        console.select_target(SelectionTarget.input(1))
        console.inspector.show_tab(ChannelDetailPanel.TAB_EQ)
        root.update()
        texts = [t for t in all_text(console.inspector.eq_tab) if t]
        self.assertTrue(any("BAND 1" in t for t in texts), texts)
        for text in texts:
            self.assertIsNone(FREQUENCY.search(text), text)
        self.assertTrue(any("unconfirmed" in t.lower() for t in texts), "EQ tab must say band frequencies are unconfirmed")


if __name__ == "__main__":
    unittest.main()
