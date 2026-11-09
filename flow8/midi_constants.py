"""
Behringer FLOW 8 USB MIDI Constants & Definitions.
Scope: Phase 2A Verified Parameters ONLY.
"""

from enum import IntEnum

# WinMM API Return Codes
class WinMmError(IntEnum):
    MMSYSERR_NOERROR = 0
    MMSYSERR_ERROR = 1
    MMSYSERR_BADDEVICEID = 2
    MMSYSERR_NOTENABLED = 3
    MMSYSERR_ALLOCATED = 4
    MMSYSERR_INVALHANDLE = 5
    MMSYSERR_NODRIVER = 6
    MMSYSERR_NOMEM = 7
    MMSYSERR_NOTSUPPORTED = 8
    MMSYSERR_BADERRNUM = 9
    MMSYSERR_INVALFLAG = 10
    MMSYSERR_INVALPARAM = 11
    MMSYSERR_HANDLEBUSY = 12
    MMSYSERR_INVALIDALIAS = 13
    MMSYSERR_BADDB = 14
    MMSYSERR_KEYNOTFOUND = 15
    MMSYSERR_READERROR = 16
    MMSYSERR_WRITEERROR = 17
    MMSYSERR_DELETEERROR = 18
    MMSYSERR_VALNOTFOUND = 19
    MMSYSERR_NODRIVERCB = 20
    MIDIERR_UNPREPARED = 64
    MIDIERR_STILLPLAYING = 65
    MIDIERR_NOMAP = 66
    MIDIERR_NOTREADY = 67
    MIDIERR_NODEVICE = 68
    MIDIERR_INVALIDSETUP = 69
    MIDIERR_BADOPENMODE = 70
    MIDIERR_DONT_CONTINUE = 71

# WinMM Callback Types
MIM_OPEN = 0x3C1
MIM_CLOSE = 0x3C2
MIM_DATA = 0x3C3
MIM_LONGDATA = 0x3C4
MIM_ERROR = 0x3C5
MOM_OPEN = 0x3C7
MOM_CLOSE = 0x3C8
MOM_DONE = 0x3C9
CALLBACK_FUNCTION = 0x00030000

# Verified MIDI Channels (1-based for public API, 0-based for protocol status byte)
MIDI_CH_INPUT_1 = 1      # Mic 1 (Status: 0xB0)
MIDI_CH_INPUT_2 = 2      # Mic 2 (Status: 0xB1)
MIDI_CH_INPUT_3 = 3      # Mic/Line 3 (Status: 0xB2)
MIDI_CH_INPUT_4 = 4      # Mic/Line 4 (Status: 0xB3)
MIDI_CH_INPUT_5 = 5      # Line 5/6 Stereo (Status: 0xB4)
MIDI_CH_INPUT_6 = 6      # Line 7/8 Stereo (Status: 0xB5)
MIDI_CH_INPUT_7 = 7      # USB/BT Audio Return (Status: 0xB6)

# Bus MIDI Channels
MIDI_CH_MAIN = 8         # Main L/R Bus (Status: 0xB7)
MIDI_CH_MON1 = 9         # Monitor 1 Master Bus (Status: 0xB8)
MIDI_CH_MON2 = 10        # Monitor 2 Master Bus (Status: 0xB9)
MIDI_CH_FX1 = 11         # FX 1 Master Send Bus (Status: 0xBA)
MIDI_CH_FX2 = 12         # FX 2 Master Send Bus (Status: 0xBB)

# Verified Control Change (CC) Numbers
CC_EQ_LOW = 1            # 4-Band EQ Low band
CC_EQ_LOW_MID = 2        # 4-Band EQ Low-Mid band
CC_EQ_HI_MID = 3         # 4-Band EQ High-Mid band
CC_EQ_HI = 4             # 4-Band EQ High band
CC_MUTE = 5              # Mute toggle / state
CC_SOLO = 6              # Solo toggle / state
CC_VOLUME_FADER = 7      # Volume / Fader level
CC_GAIN = 8              # Preamp Gain (Ch 1-4 only)
CC_LOW_CUT = 9           # Low Cut filter (Ch 1-4 only)
CC_PAN = 10              # Panning / Balance
CC_COMPRESSOR = 11       # 1-Knob Compressor (Ch 1-4 only)
CC_PHANTOM = 12          # +48V Phantom Power (Ch 1-2 only)
CC_SEND_MON1 = 14        # Aux Send to Monitor 1
CC_SEND_MON2 = 15        # Aux Send to Monitor 2
CC_SEND_FX1 = 16         # Send to FX 1
CC_SEND_FX2 = 17         # Send to FX 2

# Verified CC Value Limits
CC_VAL_MIN = 0
CC_VAL_MAX = 127

# Parameter-Specific Values
MUTE_VAL_OFF = 0
MUTE_VAL_ON = 127

PAN_VAL_LEFT = 0
PAN_VAL_CENTER = 64
PAN_VAL_RIGHT = 127

FADER_VAL_OFF = 0
FADER_VAL_MIN_AUDIBLE = 1
FADER_VAL_MAX = 127

# Endpoint Names
FLOW8_MIDI_IN_NAME = "FLOW 8 MIDI IN"
FLOW8_MIDI_OUT_NAME = "FLOW 8 MIDI OUT"
