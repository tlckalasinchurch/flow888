"""
Behringer FLOW 8 Control Package.
Dedicated Windows Desktop Workstation Engine for FLOW 8 Digital Mixer.
"""

from .midi_constants import (
    WinMmError,
    FLOW8_MIDI_IN_NAME,
    FLOW8_MIDI_OUT_NAME,
    MIDI_CH_INPUT_1,
    MIDI_CH_MAIN,
    CC_VOLUME_FADER,
    CC_MUTE,
    CC_PAN,
    MUTE_VAL_OFF,
    MUTE_VAL_ON,
    PAN_VAL_LEFT,
    PAN_VAL_CENTER,
    PAN_VAL_RIGHT,
    FADER_VAL_OFF,
    FADER_VAL_MAX,
)
from .parameter_mapping import (
    mute_bool_to_midi,
    mute_midi_to_bool,
    pan_percent_to_midi,
    pan_midi_to_percent,
    fader_midi_to_db,
    fader_db_to_midi,
    gain_db_to_midi,
    gain_midi_to_db,
    low_cut_hz_to_midi,
    low_cut_midi_to_hz,
    eq_db_to_midi,
    eq_midi_to_db,
    compressor_percent_to_midi,
    compressor_midi_to_percent,
)
from .midi_out import (
    Flow8MidiOut,
    Flow8MidiError,
    Flow8NotConnectedError,
    Flow8ValidationError,
    Flow8DeviceBusyError,
)
from .midi_in import Flow8MidiIn
from .domain_model import (
    ConnectorType,
    ChannelKind,
    SubsystemType,
    PhysicalConnector,
    LogicalChannel,
    OutputBus,
    UsbAudioTopology,
    PHYSICAL_CONNECTORS,
    LOGICAL_CHANNELS,
    OUTPUT_BUSES,
    FLOW8_AUDIO_TOPOLOGY,
)
from .state_model import (
    VerificationLevel,
    SyncStatus,
    EventSource,
    ParameterState,
    Flow8StateStore,
)
from .command_boundary import (
    Flow8CommandBoundary,
    Flow8CommandError,
    Flow8CommandRejectedError,
    CommandLogEntry,
)
from .parameter_engine import (
    Flow8ChannelStrip,
    Flow8BusStrip,
    Flow8ParameterEngine,
)

__all__ = [
    'Flow8MidiOut',
    'Flow8MidiIn',
    'Flow8MidiError',
    'Flow8NotConnectedError',
    'Flow8ValidationError',
    'Flow8DeviceBusyError',
    'mute_bool_to_midi',
    'mute_midi_to_bool',
    'pan_percent_to_midi',
    'pan_midi_to_percent',
    'fader_midi_to_db',
    'fader_db_to_midi',
    'gain_db_to_midi',
    'gain_midi_to_db',
    'low_cut_hz_to_midi',
    'low_cut_midi_to_hz',
    'eq_db_to_midi',
    'eq_midi_to_db',
    'compressor_percent_to_midi',
    'compressor_midi_to_percent',
    'WinMmError',
    'FLOW8_MIDI_IN_NAME',
    'FLOW8_MIDI_OUT_NAME',
    'MIDI_CH_INPUT_1',
    'MIDI_CH_MAIN',
    'CC_VOLUME_FADER',
    'CC_MUTE',
    'CC_PAN',
    # Domain Model
    'ConnectorType',
    'ChannelKind',
    'SubsystemType',
    'PhysicalConnector',
    'LogicalChannel',
    'OutputBus',
    'UsbAudioTopology',
    'PHYSICAL_CONNECTORS',
    'LOGICAL_CHANNELS',
    'OUTPUT_BUSES',
    'FLOW8_AUDIO_TOPOLOGY',
    # State Model
    'VerificationLevel',
    'SyncStatus',
    'EventSource',
    'ParameterState',
    'Flow8StateStore',
    # Command Boundary
    'Flow8CommandBoundary',
    'Flow8CommandError',
    'Flow8CommandRejectedError',
    'CommandLogEntry',
    # Parameter Engine
    'Flow8ChannelStrip',
    'Flow8BusStrip',
    'Flow8ParameterEngine',
]
