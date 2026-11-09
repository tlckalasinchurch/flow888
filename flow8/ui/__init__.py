"""Tkinter presentation layer for the FLOW 8 desktop workstation.

UI.2-T1 scope: the application shell only — identity header, navigation rail,
empty workspace, and honest status bar. No mixer strips, no faders, no meters,
no parameter dispatch, and no audio or telemetry integration.

This package never imports the MIDI transport modules and never transmits a
MIDI byte. All future hardware commands must travel
UI -> application service -> Parameter Engine -> Command Boundary -> driver.
"""
