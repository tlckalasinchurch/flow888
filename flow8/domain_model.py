"""
Behringer FLOW 8 Shared Hardware Domain Model.
Formalizes the complete physical and logical topology of FLOW 8.
Scope: Behringer FLOW 8 ONLY.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConnectorType(Enum):
    XLR_FEMALE = "XLR Female"
    XLR_TRS_COMBO = "XLR / 1/4\" TRS Combo"
    TRS_QUARTER_INCH = "1/4\" TRS Balanced/Unbalanced"
    TS_QUARTER_INCH = "1/4\" TS Unbalanced"
    USB_TYPE_B = "USB 2.0 Type-B"
    BLUETOOTH_RF = "2.4 GHz RF"

class ChannelKind(Enum):
    MONO_INPUT = "Mono Input"
    STEREO_INPUT = "Stereo Linked Input"
    STEREO_RETURN = "Stereo Audio Return"
    MASTER_BUS = "Master Output Bus"
    AUX_MONITOR_BUS = "Auxiliary Monitor Bus"
    FX_SEND_BUS = "Effects Send Bus"
    MONITOR_OUTPUT = "Physical Monitoring Output"

class SubsystemType(Enum):
    USB_MIDI = "USB MIDI Control (Class-Compliant MIDI 1.0)"
    USB_AUDIO = "USB Audio Interface (24-bit / 48 kHz Multi-Track)"
    BLUETOOTH_LE = "Bluetooth Low Energy Control (GATT Server)"
    BLUETOOTH_A2DP = "Bluetooth Classic Audio (A2DP Stereo Sink)"
    FOOTSWITCH = "Hardware Dual Footswitch GPIO"

# ---------------------------------------------------------------------------
# Descriptors
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhysicalConnector:
    connector_id: str
    connector_type: ConnectorType
    label: str
    description: str
    has_phantom_power: bool = False
    has_hi_z: bool = False
    is_balanced: bool = True

@dataclass(frozen=True)
class LogicalChannel:
    channel_index: int       # Logical strip index 1..7 (MIDI ch 8 is the MAIN bus, not a strip)
    name: str
    kind: ChannelKind
    physical_connectors: Tuple[str, ...]
    has_low_cut: bool
    has_preamp_gain: bool
    has_4band_eq: bool
    has_compressor: bool
    has_hi_z: bool
    has_phantom: bool
    pan_or_balance: str      # "PAN" for mono, "BALANCE" for stereo
    # MIDI channel that carries this strip. Declared explicitly so the
    # strip -> MIDI channel binding is data, not index arithmetic.
    midi_channel: int = 0
    # True only where a verified MIDI control address exists for the compressor.
    compressor_control_verified: bool = True

@dataclass(frozen=True)
class OutputBus:
    bus_id: str
    name: str
    kind: ChannelKind
    has_9band_geq: bool
    has_limiter: bool
    physical_output: str

# ---------------------------------------------------------------------------
# Official FLOW 8 Hardware Topology Specification
# ---------------------------------------------------------------------------

PHYSICAL_CONNECTORS: Dict[str, PhysicalConnector] = {
    "IN_1": PhysicalConnector(
        connector_id="IN_1",
        connector_type=ConnectorType.XLR_FEMALE,
        label="Input 1 (Mic 1)",
        description="Midas-designed microphone preamplifier",
        has_phantom_power=True,
        has_hi_z=False,
        is_balanced=True
    ),
    "IN_2": PhysicalConnector(
        connector_id="IN_2",
        connector_type=ConnectorType.XLR_FEMALE,
        label="Input 2 (Mic 2)",
        description="Midas-designed microphone preamplifier",
        has_phantom_power=True,
        has_hi_z=False,
        is_balanced=True
    ),
    "IN_3": PhysicalConnector(
        connector_id="IN_3",
        connector_type=ConnectorType.XLR_TRS_COMBO,
        label="Input 3 (Mic/Line 3)",
        description="Microphone or line-level balanced input",
        has_phantom_power=False,
        has_hi_z=False,
        is_balanced=True
    ),
    "IN_4": PhysicalConnector(
        connector_id="IN_4",
        connector_type=ConnectorType.XLR_TRS_COMBO,
        label="Input 4 (Mic/Line 4)",
        description="Microphone or line-level balanced input",
        has_phantom_power=False,
        has_hi_z=False,
        is_balanced=True
    ),
    "IN_5L": PhysicalConnector(
        connector_id="IN_5L",
        connector_type=ConnectorType.TRS_QUARTER_INCH,
        label="Input 5L",
        description="Stereo line input left channel",
        has_phantom_power=False,
        has_hi_z=False,
        is_balanced=True
    ),
    "IN_6R": PhysicalConnector(
        connector_id="IN_6R",
        connector_type=ConnectorType.TRS_QUARTER_INCH,
        label="Input 6R (Hi-Z Guitar)",
        description="Stereo line input right channel or dedicated Hi-Z guitar direct input",
        has_phantom_power=False,
        has_hi_z=True,
        is_balanced=False
    ),
    "IN_7L": PhysicalConnector(
        connector_id="IN_7L",
        connector_type=ConnectorType.TRS_QUARTER_INCH,
        label="Input 7L",
        description="Stereo line input left channel",
        has_phantom_power=False,
        has_hi_z=False,
        is_balanced=True
    ),
    "IN_8R": PhysicalConnector(
        connector_id="IN_8R",
        connector_type=ConnectorType.TRS_QUARTER_INCH,
        label="Input 8R (Hi-Z Guitar)",
        description="Stereo line input right channel or dedicated Hi-Z guitar direct input",
        has_phantom_power=False,
        has_hi_z=True,
        is_balanced=False
    ),
    "FOOTSWITCH": PhysicalConnector(
        connector_id="FOOTSWITCH",
        connector_type=ConnectorType.TRS_QUARTER_INCH,
        label="Footswitch Input",
        description="Dual footswitch jack for Mute / Tap Tempo",
        has_phantom_power=False,
        has_hi_z=False,
        is_balanced=False
    ),
    "USB_PORT": PhysicalConnector(
        connector_id="USB_PORT",
        connector_type=ConnectorType.USB_TYPE_B,
        label="USB Audio/MIDI Port",
        description="USB 2.0 interface (10 in / 2-4 out + MIDI)",
        has_phantom_power=False,
        has_hi_z=False,
        is_balanced=False
    )
}

LOGICAL_CHANNELS: Dict[int, LogicalChannel] = {
    1: LogicalChannel(
        channel_index=1,
        name="Channel 1",
        kind=ChannelKind.MONO_INPUT,
        physical_connectors=("IN_1",),
        midi_channel=1,
        has_low_cut=True,
        has_preamp_gain=True,
        has_4band_eq=True,
        has_compressor=True,
        has_hi_z=False,
        has_phantom=True,
        pan_or_balance="PAN"
    ),
    2: LogicalChannel(
        channel_index=2,
        name="Channel 2",
        kind=ChannelKind.MONO_INPUT,
        physical_connectors=("IN_2",),
        midi_channel=2,
        has_low_cut=True,
        has_preamp_gain=True,
        has_4band_eq=True,
        has_compressor=True,
        has_hi_z=False,
        has_phantom=True,
        pan_or_balance="PAN"
    ),
    3: LogicalChannel(
        channel_index=3,
        name="Channel 3",
        kind=ChannelKind.MONO_INPUT,
        physical_connectors=("IN_3",),
        midi_channel=3,
        has_low_cut=True,
        has_preamp_gain=True,
        has_4band_eq=True,
        has_compressor=True,
        has_hi_z=False,
        has_phantom=False,
        pan_or_balance="PAN"
    ),
    4: LogicalChannel(
        channel_index=4,
        name="Channel 4",
        kind=ChannelKind.MONO_INPUT,
        physical_connectors=("IN_4",),
        midi_channel=4,
        has_low_cut=True,
        has_preamp_gain=True,
        has_4band_eq=True,
        has_compressor=True,
        has_hi_z=False,
        has_phantom=False,
        pan_or_balance="PAN"
    ),
    5: LogicalChannel(
        channel_index=5,
        name="Channel 5/6",
        kind=ChannelKind.STEREO_INPUT,
        physical_connectors=("IN_5L", "IN_6R"),
        midi_channel=5,
        compressor_control_verified=False,
        has_low_cut=False,
        has_preamp_gain=False,
        has_4band_eq=True,
        has_compressor=True,
        has_hi_z=True,  # on 6R
        has_phantom=False,
        pan_or_balance="BALANCE"
    ),
    6: LogicalChannel(
        channel_index=6,
        name="Channel 7/8",
        kind=ChannelKind.STEREO_INPUT,
        physical_connectors=("IN_7L", "IN_8R"),
        midi_channel=6,
        compressor_control_verified=False,
        has_low_cut=False,
        has_preamp_gain=False,
        has_4band_eq=True,
        has_compressor=True,
        has_hi_z=True,  # on 8R
        has_phantom=False,
        pan_or_balance="BALANCE"
    ),
    7: LogicalChannel(
        channel_index=7,
        name="USB/BT Return",
        kind=ChannelKind.STEREO_RETURN,
        physical_connectors=("USB_PORT",),
        midi_channel=7,
        compressor_control_verified=False,
        has_low_cut=False,
        has_preamp_gain=False,
        has_4band_eq=True,
        has_compressor=False,
        has_hi_z=False,
        has_phantom=False,
        pan_or_balance="BALANCE"
    )
}

# Reverse index: MIDI channel -> logical strip index.
LOGICAL_CHANNEL_BY_MIDI_CHANNEL: Dict[int, int] = {
    spec.midi_channel: idx for idx, spec in LOGICAL_CHANNELS.items()
}


def logical_channel_for_connector(connector_id: str) -> Optional[int]:
    """
    Resolve a physical connector ID (e.g. "IN_7L", "IN_6R", "USB_PORT")
    to the logical strip index that owns it.

    This is the sanctioned way to answer "which strip controls input 7/8?" --
    it prevents a UI from assuming strip 6 == input 6.
    """
    for idx, spec in LOGICAL_CHANNELS.items():
        if connector_id in spec.physical_connectors:
            return idx
    return None


OUTPUT_BUSES: Dict[str, OutputBus] = {
    "MAIN": OutputBus(
        bus_id="MAIN",
        name="Main L/R",
        kind=ChannelKind.MASTER_BUS,
        has_9band_geq=True,
        has_limiter=True,
        physical_output="Gold-Plated XLR L/R"
    ),
    "MON1": OutputBus(
        bus_id="MON1",
        name="Monitor 1",
        kind=ChannelKind.AUX_MONITOR_BUS,
        has_9band_geq=True,
        has_limiter=True,
        physical_output="1/4\" TRS Balanced (MON 1)"
    ),
    "MON2": OutputBus(
        bus_id="MON2",
        name="Monitor 2",
        kind=ChannelKind.AUX_MONITOR_BUS,
        has_9band_geq=True,
        has_limiter=True,
        physical_output="1/4\" TRS Balanced (MON 2)"
    ),
    "FX1": OutputBus(
        bus_id="FX1",
        name="FX 1 Send",
        kind=ChannelKind.FX_SEND_BUS,
        has_9band_geq=False,
        has_limiter=False,
        physical_output="Internal DSP FX 1 Engine (16 Reverbs/Delays)"
    ),
    "FX2": OutputBus(
        bus_id="FX2",
        name="FX 2 Send",
        kind=ChannelKind.FX_SEND_BUS,
        has_9band_geq=False,
        has_limiter=False,
        physical_output="Internal DSP FX 2 Engine (16 Modulation/Pitch)"
    ),
    "PHONES": OutputBus(
        bus_id="PHONES",
        name="Headphones",
        kind=ChannelKind.MONITOR_OUTPUT,
        has_9band_geq=False,
        has_limiter=False,
        physical_output="1/4\" TRS Stereo Headphone Jack (Switchable monitoring tap mirroring Main, Mon 1, or Mon 2)"
    )
}

@dataclass(frozen=True)
class UsbAudioTopology:
    standard: str = "USB 2.0 Audio Class Compliant"
    sample_rate_hz: int = 48000
    bit_depth: int = 24
    capture_channel_count: int = 10
    playback_channel_count_standard: int = 2
    playback_channel_count_driver: int = 4
    capture_channels: Tuple[str, ...] = (
        "Mic 1", "Mic 2", "Mic/Line 3", "Mic/Line 4",
        "Line 5 (L)", "Line 6 (R / Hi-Z)",
        "Line 7 (L)", "Line 8 (R / Hi-Z)",
        "Main L", "Main R"
    )
    playback_channels: Tuple[str, ...] = (
        "USB Out 1 (L)", "USB Out 2 (R)",
        "USB Out 3 (L / Aux)", "USB Out 4 (R / Aux)"
    )

FLOW8_AUDIO_TOPOLOGY = UsbAudioTopology()
