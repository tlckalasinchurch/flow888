"""Focused tests for the FLOW 8 Cyber Neon application shell (UI.2-T1).

These tests never open a MIDI port, never require a FLOW 8, and never mock a
hardware response. They assert the opposite of fabrication: that the shell is
honest about what it cannot know, and that starting and stopping it transmits
no MIDI.
"""

from __future__ import annotations

import ast
import pathlib
import re
import tkinter as tk
import unittest
from tkinter import font as tkfont
from unittest import mock

import flow8.midi_in
import flow8.midi_out
from flow8.ui import theme
from flow8.ui.app import Flow8App
from flow8.ui.components import widget_texts
from flow8.ui.status import FORBIDDEN_CLAIMS, SessionStatus

UI_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent / "flow8" / "ui"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _tk_usable() -> bool:
    try:
        root = tk.Tk()
    except Exception:  # pragma: no cover - depends on host display
        return False
    root.destroy()
    return True


TK_USABLE = _tk_usable()
requires_display = unittest.skipUnless(TK_USABLE, "no Tk display available")


# ---------------------------------------------------------------------------
# 1. Theme tokens
# ---------------------------------------------------------------------------

class ThemeTokenTests(unittest.TestCase):
    def test_colour_tokens_are_valid_hex(self):
        for name, value in theme.COLORS.items():
            self.assertRegex(value, HEX_COLOR, f"colour token {name!r} is not #RRGGBB")

    def test_required_palette_keys_present(self):
        required = {
            "background", "background_alt", "surface", "surface_alt",
            "surface_hover", "border", "text", "text_secondary", "text_muted",
            "cyan", "cyan_soft", "purple", "purple_soft", "lime",
            "success", "warning", "danger",
        }
        self.assertTrue(required.issubset(theme.COLORS))

    def test_spacing_and_radius_scale(self):
        for key in (
            "radius_small", "radius_medium", "radius_large",
            "spacing_small", "spacing_medium", "spacing_large", "spacing_xlarge",
        ):
            self.assertIn(key, theme.TOKENS)
            self.assertIsInstance(theme.TOKENS[key], int)
            self.assertGreater(theme.TOKENS[key], 0)

    def test_window_identity_and_bounds(self):
        self.assertEqual(theme.WINDOW_TITLE, "FLOW 8 — Cyber Neon Workstation")
        self.assertEqual(theme.WINDOW_MIN_SIZE, (1366, 768))
        self.assertGreater(theme.WINDOW_DEFAULT_SIZE[0], theme.WINDOW_MIN_SIZE[0])
        self.assertGreater(theme.WINDOW_DEFAULT_SIZE[1], theme.WINDOW_MIN_SIZE[1])

    def test_font_preferences_start_with_inter(self):
        self.assertEqual(theme.FONT_PREFERENCES[0], "Inter")
        self.assertIn("Segoe UI", theme.FONT_PREFERENCES)


# ---------------------------------------------------------------------------
# 2-6. Shell behaviour
# ---------------------------------------------------------------------------

@requires_display
class ShellTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._destroy_root)
        self.app = Flow8App(root=self.root)

    def _destroy_root(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # -- construction -------------------------------------------------------

    def test_shell_constructs_without_hardware(self):
        self.assertEqual(self.root.title(), theme.WINDOW_TITLE)
        self.assertEqual(
            tuple(int(part) for part in self.root.minsize()),
            theme.WINDOW_MIN_SIZE,
        )
        self.assertFalse(self.app.closed)
        self.assertFalse(self.app._owns_root)

    def test_fonts_resolve_to_installed_families(self):
        installed = {name.lower() for name in tkfont.families(self.root)}
        for role in ("title", "nav", "section", "body", "status_value"):
            family = self.app.fonts[role].actual("family").lower()
            self.assertIn(family, installed, f"font role {role!r} is not installed")

    # -- identity -----------------------------------------------------------

    def test_header_identifies_flow8(self):
        texts = " | ".join(self.app.header.text_snapshot())
        self.assertIn("FLOW 8", texts)
        self.assertIn("CYBER NEON WORKSTATION", texts)
        self.assertIn("Behringer FLOW 8", texts)

    def test_window_title_is_product_identity(self):
        self.assertIn("FLOW 8", self.root.title())
        self.assertIn("Cyber Neon", self.root.title())

    # -- honest statuses ----------------------------------------------------

    def test_header_reports_port_state_not_device_detection(self):
        self.assertEqual(
            self.app.header.device_status_var.get(),
            "MIDI PORTS CLOSED",
        )

    def test_transport_statuses_are_honest(self):
        values = self.app.status_bar.values
        self.assertEqual(values["midi_out"].get(), "CLOSED")
        self.assertEqual(values["midi_in"].get(), "CLOSED")
        self.assertEqual(values["midi_error"].get(), "NONE")
        self.assertEqual(values["usb_audio"].get(), "NOT INTEGRATED")
        self.assertEqual(values["audio_telemetry"].get(), "NO TELEMETRY")
        self.assertEqual(values["hardware_observation"].get(), "UNKNOWN")

    def test_status_bar_renders_labels_and_values(self):
        texts = " ".join(self.app.status_bar.text_snapshot())
        self.assertIn("MIDI OUT:", texts)
        self.assertIn("MIDI IN:", texts)
        self.assertIn("MIDI ERROR:", texts)
        self.assertIn("USB AUDIO:", texts)
        self.assertIn("AUDIO TELEMETRY:", texts)
        self.assertIn("HARDWARE OBSERVATION:", texts)

    def test_partial_midi_port_state_is_reported_without_device_claim(self):
        self.app.header.set_midi_port_status(True, False, "MIDI IN busy", False)
        self.app.status_bar.set_midi_port_status(True, False, "MIDI IN busy", False)
        self.assertEqual(self.app.header.device_status_var.get(), "MIDI PORTS PARTIAL")
        self.assertEqual(self.app.status_bar.values["midi_out"].get(), "OPEN")
        self.assertEqual(self.app.status_bar.values["midi_in"].get(), "CLOSED")
        self.assertEqual(self.app.status_bar.values["midi_error"].get(), "MIDI IN busy")
        self.assertEqual(self.app.status_bar.values["usb_audio"].get(), "NOT INTEGRATED")
        self.assertEqual(self.app.status_bar.values["hardware_observation"].get(), "UNKNOWN")

    def test_open_midi_input_without_listener_is_partial(self):
        self.app.header.set_midi_port_status(True, True, None, False)
        self.app.status_bar.set_midi_port_status(True, True, None, False)
        self.assertEqual(self.app.header.device_status_var.get(), "MIDI PORTS PARTIAL")
        self.assertEqual(
            self.app.status_bar.values["midi_in"].get(),
            "OPEN / NOT LISTENING",
        )

    def test_no_forbidden_hardware_claims_rendered(self):
        rendered = " ".join(self.app.text_snapshot()).upper()
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotRegex(
                rendered,
                rf"\b{re.escape(claim)}\b",
                f"shell claims {claim!r}",
            )

    def test_no_meter_or_channel_value_rendered(self):
        rendered = " ".join(self.app.text_snapshot()).upper()
        for absent in ("DB", "METERS ACTIVE", "LEVEL", "PEAK"):
            self.assertNotIn(absent, rendered)

    # -- navigation ---------------------------------------------------------

    def test_mixer_is_enabled_and_selected(self):
        self.assertTrue(self.app.navigation.is_enabled("mixer"))
        self.assertEqual(self.app.navigation.selected, "mixer")
        self.assertEqual(str(self.app.navigation.buttons["mixer"].cget("state")), "normal")

    def test_unimplemented_destinations_are_disabled(self):
        for key in ("routing", "fx", "scenes", "recording"):
            self.assertFalse(self.app.navigation.is_enabled(key), key)
            self.assertEqual(
                str(self.app.navigation.buttons[key].cget("state")),
                "disabled",
                f"{key} must be disabled",
            )
        self.assertIn("NOT IMPLEMENTED", " ".join(self.app.navigation.text_snapshot()))

    def test_disabled_destination_cannot_navigate(self):
        self.assertFalse(self.app.show_page("routing"))
        self.assertFalse(self.app.show_page("scenes"))
        self.assertEqual(self.app.navigation.selected, "mixer")

    def test_workspace_placeholder_states_next_ticket(self):
        texts = " ".join(widget_texts(self.app.workspace))
        self.assertIn("MIXER CONSOLE", texts)
        self.assertIn("COMING IN UI.2-T2", texts)

    def test_all_five_destinations_exist(self):
        self.assertEqual(
            set(self.app.navigation.items),
            {"mixer", "routing", "fx", "scenes", "recording"},
        )

    # -- lifecycle ----------------------------------------------------------

    def test_close_marks_shell_closed(self):
        self.app.close()
        self.assertTrue(self.app.closed)


# ---------------------------------------------------------------------------
# 6. No MIDI on start-up or shutdown
# ---------------------------------------------------------------------------

@requires_display
class MidiSafetyTests(unittest.TestCase):
    def test_startup_and_shutdown_transmit_no_midi(self):
        """Transport entry points are trapped: any call fails the test."""
        failure = AssertionError("shell attempted MIDI transport activity")
        with mock.patch.object(flow8.midi_out.Flow8MidiOut, "open", side_effect=failure) as out_open, \
                mock.patch.object(flow8.midi_out.Flow8MidiOut, "send_cc", side_effect=failure) as send_cc, \
                mock.patch.object(flow8.midi_in.Flow8MidiIn, "open", side_effect=failure) as in_open, \
                mock.patch.object(flow8.midi_in.Flow8MidiIn, "start", side_effect=failure) as in_start:
            root = tk.Tk()
            root.withdraw()
            app = Flow8App(root=root)
            app.close()

            out_open.assert_not_called()
            send_cc.assert_not_called()
            in_open.assert_not_called()
            in_start.assert_not_called()

    def test_status_snapshot_defaults_are_honest(self):
        status = SessionStatus()
        self.assertEqual(status.device, "NOT VERIFIED")
        self.assertEqual(status.midi, "UNKNOWN")
        self.assertEqual(status.usb_audio, "NOT INTEGRATED")
        self.assertEqual(status.audio_telemetry, "NO TELEMETRY")
        self.assertEqual(status.hardware_observation, "UNKNOWN")


# ---------------------------------------------------------------------------
# Static architectural guards
# ---------------------------------------------------------------------------

class UIImportBoundaryTests(unittest.TestCase):
    def test_ui_modules_do_not_import_transport_or_ctypes(self):
        forbidden = {"ctypes", "flow8.midi_out", "flow8.midi_in"}
        for path in sorted(UI_DIRECTORY.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name, forbidden, f"{path.name}: {alias.name}")
                        self.assertFalse(alias.name.startswith("flow8.midi"), path.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertNotIn(module, forbidden, f"{path.name}: {module}")
                    self.assertFalse(module.startswith("flow8.midi"), path.name)

    def test_ui_sources_contain_no_driver_call_sites(self):
        for path in sorted(UI_DIRECTORY.rglob("*.py")):
            source = path.read_text(encoding="utf-8").lower()
            for marker in ("winmm", "send_cc", "midioutshortmsg", "midiinshortmsg"):
                self.assertNotIn(marker, source, f"{path.name} references {marker}")


if __name__ == "__main__":
    unittest.main()
