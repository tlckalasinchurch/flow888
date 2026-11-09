"""
Behringer FLOW 8 Parameter Mapping Functions.
Handles conversion between raw MIDI values (0–127) and engineering units.

Status:
- Mute Mapping: VERIFIED (0 = OFF, 127 = ON)
- Pan Mapping: VERIFIED (0 = -100% Left, 64 = Center 0%, 127 = +100% Right)
- Fader Raw Mapping: VERIFIED (0 = OFF, 1–127 = Mapped Fader)
- Fader dB Curve: UNVERIFIED APPROXIMATION (Exact firmware logarithmic taper unreleased;
  piecewise linear approximation provided with explicit -inf handling).
"""

import math
from typing import Union
from .midi_constants import (
    MUTE_VAL_OFF, MUTE_VAL_ON,
    PAN_VAL_LEFT, PAN_VAL_CENTER, PAN_VAL_RIGHT,
    FADER_VAL_OFF, FADER_VAL_MIN_AUDIBLE, FADER_VAL_MAX
)

# ---------------------------------------------------------------------------
# Mute Mapping (VERIFIED)
# ---------------------------------------------------------------------------

def mute_bool_to_midi(muted: bool) -> int:
    """Convert boolean mute state to MIDI CC value (0 = OFF, 127 = ON)."""
    return MUTE_VAL_ON if muted else MUTE_VAL_OFF


def mute_midi_to_bool(val: int) -> bool:
    """
    Convert MIDI CC value to boolean mute state.
    0 = Unmuted (False), 1–127 = Muted (True).
    """
    if not (0 <= val <= 127):
        raise ValueError(f"Mute MIDI value out of bounds (0-127): {val}")
    return val > 0


# ---------------------------------------------------------------------------
# Pan Mapping (VERIFIED)
# ---------------------------------------------------------------------------

def pan_percent_to_midi(percent: float) -> int:
    """
    Convert percentage (-100.0% to +100.0%) to MIDI CC value.
    -100.0% -> 0 (Hard Left)
       0.0% -> 64 (Center)
    +100.0% -> 127 (Hard Right)
    """
    clamped = max(-100.0, min(100.0, float(percent)))
    if clamped == 0.0:
        return PAN_VAL_CENTER
    elif clamped < 0.0:
        # Scale -100..0 to 0..64
        val = round(PAN_VAL_CENTER + (clamped / 100.0) * PAN_VAL_CENTER)
        return max(PAN_VAL_LEFT, min(PAN_VAL_CENTER, val))
    else:
        # Scale 0..100 to 64..127
        val = round(PAN_VAL_CENTER + (clamped / 100.0) * (PAN_VAL_RIGHT - PAN_VAL_CENTER))
        return max(PAN_VAL_CENTER, min(PAN_VAL_RIGHT, val))


def pan_midi_to_percent(val: int) -> float:
    """
    Convert MIDI CC value (0–127) to percentage (-100.0% to +100.0%).
    0 -> -100.0%
    64 -> 0.0%
    127 -> +100.0%
    """
    if not (0 <= val <= 127):
        raise ValueError(f"Pan MIDI value out of bounds (0-127): {val}")

    if val == PAN_VAL_CENTER:
        return 0.0
    elif val < PAN_VAL_CENTER:
        return round(((val - PAN_VAL_CENTER) / float(PAN_VAL_CENTER)) * 100.0, 2)
    else:
        return round(((val - PAN_VAL_CENTER) / float(PAN_VAL_RIGHT - PAN_VAL_CENTER)) * 100.0, 2)


# ---------------------------------------------------------------------------
# Fader Mapping (RAW: VERIFIED | dB CONVERSION: UNVERIFIED APPROXIMATION)
# ---------------------------------------------------------------------------

# Unity gain position on 0–127 scale in standard digital mixer firmware
FADER_UNITY_MIDI = 101
FADER_MIN_DB = -70.0
FADER_UNITY_DB = 0.0
FADER_MAX_DB = 10.0

def fader_midi_to_db(val: int) -> float:
    """
    Convert raw MIDI fader value (0–127) to decibels (dB).
    
    Status: UNVERIFIED APPROXIMATION.
    - Value 0 is strictly OFF: returns float('-inf').
    - Value 1 to 101: Piecewise linear approximation from -70.0 dB to 0.0 dB (Unity).
    - Value 101 to 127: Piecewise linear approximation from 0.0 dB to +10.0 dB.
    """
    if not (0 <= val <= 127):
        raise ValueError(f"Fader MIDI value out of bounds (0-127): {val}")

    if val == FADER_VAL_OFF:
        return float('-inf')

    if val <= FADER_UNITY_MIDI:
        # Range 1 .. 101 maps to -70 dB .. 0 dB
        fraction = (val - FADER_VAL_MIN_AUDIBLE) / float(FADER_UNITY_MIDI - FADER_VAL_MIN_AUDIBLE)
        return round(FADER_MIN_DB + fraction * (FADER_UNITY_DB - FADER_MIN_DB), 2)
    else:
        # Range 101 .. 127 maps to 0 dB .. +10 dB
        fraction = (val - FADER_UNITY_MIDI) / float(FADER_VAL_MAX - FADER_UNITY_MIDI)
        return round(FADER_UNITY_DB + fraction * (FADER_MAX_DB - FADER_UNITY_DB), 2)


def fader_db_to_midi(db: Union[float, int]) -> int:
    """
    Convert decibels (dB) to raw MIDI fader value (0–127).
    
    Status: UNVERIFIED APPROXIMATION.
    - db <= -70.0 or db == -inf: returns 0 (OFF).
    - -70.0 < db <= 0.0: maps to 1 .. 101.
    - 0.0 < db <= +10.0: maps to 101 .. 127.
    """
    if db == float('-inf') or (math.isinf(db) and db < 0) or db < FADER_MIN_DB:
        return FADER_VAL_OFF

    if db <= FADER_UNITY_DB:
        fraction = (float(db) - FADER_MIN_DB) / (FADER_UNITY_DB - FADER_MIN_DB)
        val = round(FADER_VAL_MIN_AUDIBLE + fraction * (FADER_UNITY_MIDI - FADER_VAL_MIN_AUDIBLE))
        return max(FADER_VAL_MIN_AUDIBLE, min(FADER_UNITY_MIDI, val))
    else:
        fraction = (float(db) - FADER_UNITY_DB) / (FADER_MAX_DB - FADER_UNITY_DB)
        val = round(FADER_UNITY_MIDI + fraction * (FADER_VAL_MAX - FADER_UNITY_MIDI))
        return max(FADER_UNITY_MIDI, min(FADER_VAL_MAX, val))


# ---------------------------------------------------------------------------
# Preamp Gain Mapping (UNVERIFIED APPROXIMATION: -20 dB to +60 dB)
# ---------------------------------------------------------------------------

GAIN_MIN_DB = -20.0
GAIN_MAX_DB = 60.0

def gain_db_to_midi(db: Union[float, int]) -> int:
    """
    Convert Preamp Gain in decibels (-20.0 dB to +60.0 dB) to MIDI CC (0–127).
    Status: UNVERIFIED APPROXIMATION (Linear dB approximation across 80 dB span).
    """
    clamped = max(GAIN_MIN_DB, min(GAIN_MAX_DB, float(db)))
    fraction = (clamped - GAIN_MIN_DB) / (GAIN_MAX_DB - GAIN_MIN_DB)
    return round(fraction * 127)

def gain_midi_to_db(val: int) -> float:
    """
    Convert MIDI CC (0–127) to Preamp Gain in decibels (-20.0 dB to +60.0 dB).
    Status: UNVERIFIED APPROXIMATION.
    """
    if not (0 <= val <= 127):
        raise ValueError(f"Gain MIDI value out of bounds (0-127): {val}")
    return round(GAIN_MIN_DB + (val / 127.0) * (GAIN_MAX_DB - GAIN_MIN_DB), 1)


# ---------------------------------------------------------------------------
# Low Cut Frequency Mapping (UNVERIFIED APPROXIMATION: 20 Hz to 600 Hz)
# ---------------------------------------------------------------------------

LOW_CUT_MIN_HZ = 20.0
LOW_CUT_MAX_HZ = 600.0

def low_cut_hz_to_midi(hz: Union[float, int]) -> int:
    """
    Convert Low Cut frequency in Hertz (20 Hz to 600 Hz) to MIDI CC (0–127).
    Status: UNVERIFIED APPROXIMATION (Linear frequency approximation across 580 Hz span).
    """
    clamped = max(LOW_CUT_MIN_HZ, min(LOW_CUT_MAX_HZ, float(hz)))
    fraction = (clamped - LOW_CUT_MIN_HZ) / (LOW_CUT_MAX_HZ - LOW_CUT_MIN_HZ)
    return round(fraction * 127)

def low_cut_midi_to_hz(val: int) -> float:
    """
    Convert MIDI CC (0–127) to Low Cut frequency in Hertz (20 Hz to 600 Hz).
    Status: UNVERIFIED APPROXIMATION.
    """
    if not (0 <= val <= 127):
        raise ValueError(f"Low Cut MIDI value out of bounds (0-127): {val}")
    return round(LOW_CUT_MIN_HZ + (val / 127.0) * (LOW_CUT_MAX_HZ - LOW_CUT_MIN_HZ), 1)


# ---------------------------------------------------------------------------
# 4-Band PEQ Gain Mapping (VERIFIED: -15 dB to +15 dB, 64 = 0 dB)
# ---------------------------------------------------------------------------

EQ_MIN_DB = -15.0
EQ_MAX_DB = 15.0
EQ_CENTER_MIDI = 64

def eq_db_to_midi(db: Union[float, int]) -> int:
    """
    Convert EQ band gain (-15.0 dB to +15.0 dB) to MIDI CC (0–127).
    0.0 dB -> 64 (Center)
    -15.0 dB -> 0
    +15.0 dB -> 127
    """
    clamped = max(EQ_MIN_DB, min(EQ_MAX_DB, float(db)))
    if clamped == 0.0:
        return EQ_CENTER_MIDI
    elif clamped < 0.0:
        val = round(EQ_CENTER_MIDI + (clamped / 15.0) * EQ_CENTER_MIDI)
        return max(0, min(EQ_CENTER_MIDI, val))
    else:
        val = round(EQ_CENTER_MIDI + (clamped / 15.0) * (127 - EQ_CENTER_MIDI))
        return max(EQ_CENTER_MIDI, min(127, val))

def eq_midi_to_db(val: int) -> float:
    """
    Convert MIDI CC (0–127) to EQ band gain in dB (-15.0 dB to +15.0 dB).
    """
    if not (0 <= val <= 127):
        raise ValueError(f"EQ MIDI value out of bounds (0-127): {val}")
    if val == EQ_CENTER_MIDI:
        return 0.0
    elif val < EQ_CENTER_MIDI:
        return round(((val - EQ_CENTER_MIDI) / float(EQ_CENTER_MIDI)) * 15.0, 2)
    else:
        return round(((val - EQ_CENTER_MIDI) / float(127 - EQ_CENTER_MIDI)) * 15.0, 2)


# ---------------------------------------------------------------------------
# Compressor Mapping (VERIFIED: 0% to 100%, 0-100 raw, 101-127 clamp to 100%)
# ---------------------------------------------------------------------------

def compressor_percent_to_midi(percent: Union[float, int]) -> int:
    """
    Convert compressor amount (0.0% to 100.0%) to MIDI CC (0–100).
    """
    clamped = max(0.0, min(100.0, float(percent)))
    return round(clamped)

def compressor_midi_to_percent(val: int) -> float:
    """
    Convert MIDI CC (0–127) to compressor amount (0.0% to 100.0%).
    Values 101–127 clamp to 100.0%.
    """
    if not (0 <= val <= 127):
        raise ValueError(f"Compressor MIDI value out of bounds (0-127): {val}")
    return float(min(100, val))

