"""
Behringer FLOW 8 Channel Strip & Parameter Engine.
High-level control interface for FLOW 8 input channels and output buses.
Scope: Behringer FLOW 8 ONLY.

All commands flow strictly through the Command Boundary:
Parameter Engine -> Command Boundary -> Flow8MidiOut -> Windows Driver.

Strip identity (Phase C.2)
--------------------------
The numeric suffix of a channel strip is a STRIP index, not a physical input
number, because a stereo pair occupies one strip and the USB/BT return has no
connector at all:

    ch1  -> MIDI ch 1  -> input 1        (mono)
    ch2  -> MIDI ch 2  -> input 2        (mono)
    ch3  -> MIDI ch 3  -> input 3        (mono)
    ch4  -> MIDI ch 4  -> input 4        (mono)
    ch5  -> MIDI ch 5  -> inputs 5L + 6R (stereo pair)
    ch6  -> MIDI ch 6  -> inputs 7L + 8R (stereo pair)
    ch7  -> MIDI ch 7  -> USB/BT return  (no connector)

`ch6` therefore controls the 7/8 pair, never input 6. Resolve labels through
`Flow8ParameterEngine.channel_for_physical_input()` (or
`domain_model.logical_channel_for_connector`) instead of assuming chN == input N.
"""

from typing import Any, Dict, List, Optional, Callable, Union
from .domain_model import (
    LOGICAL_CHANNELS,
    OUTPUT_BUSES,
    ChannelKind,
    logical_channel_for_connector,
)
from .state_model import Flow8StateStore, ParameterState, EventSource
from .command_boundary import (
    Flow8CommandBoundary,
    CommandLogEntry,
    Flow8CommandError,
    Flow8CommandRejectedError,
)
from .midi_out import Flow8ValidationError

VALID_EQ_BANDS = ("low", "low_mid", "hi_mid", "hi")
VALID_SEND_TARGETS = ("mon1", "mon2", "fx1", "fx2")
VALID_BUS_IDS = ("main", "mon1", "mon2", "fx1", "fx2")

class Flow8ChannelStrip:
    """
    Dedicated controller for a single Behringer FLOW 8 input channel (1 to 7).
    Enforces hardware topology constraints and dispatches exclusively via Command Boundary.
    """

    def __init__(self, channel_index: int, boundary: Flow8CommandBoundary, state_store: Flow8StateStore):
        if not (1 <= channel_index <= 7):
            raise Flow8ValidationError(f"Invalid FLOW 8 channel index {channel_index}. Input channels are 1 to 7.")

        self.channel_index = channel_index
        self._prefix = f"ch{channel_index}"
        self._boundary = boundary
        self._state_store = state_store
        self._spec = LOGICAL_CHANNELS.get(channel_index)

    @property
    def name(self) -> str:
        return self._spec.name if self._spec else f"Channel {self.channel_index}"

    @property
    def kind(self) -> ChannelKind:
        return self._spec.kind if self._spec else ChannelKind.MONO_INPUT

    # -----------------------------------------------------------------------
    # Fader & Mute & Pan
    # -----------------------------------------------------------------------

    def set_fader(self, value: Union[int, float], unit: str = "raw", source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """Set channel fader level (unit: 'raw' [0-127] or 'dB' [-70.0 to +10.0 or -inf])."""
        return self._boundary.execute_command(f"{self._prefix}.fader", value, source=source, unit=unit)

    def set_mute(self, muted: bool, source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """Set channel mute state (True = Muted, False = Unmuted)."""
        return self._boundary.execute_command(f"{self._prefix}.mute", bool(muted), source=source, unit="raw")

    def set_pan(self, value: Union[int, float], unit: str = "raw", source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """
        Set channel pan or stereo balance.
        For Channels 1-4: Pan (0 = Left, 64 = Center, 127 = Right, or -100% to +100%).
        For Channels 5-7: Balance (0 = Left, 64 = Center, 127 = Right, or -100% to +100%).
        """
        return self._boundary.execute_command(f"{self._prefix}.pan", value, source=source, unit=unit)

    def set_balance(
        self,
        value: Union[int, float],
        unit: str = "raw",
        source: EventSource = EventSource.LOCAL_HOST
    ) -> CommandLogEntry:
        """
        Set stereo BALANCE for a stereo-linked strip (Ch 5/6, 7/8, USB/BT).

        Uses the same `chN.pan` address as set_pan() -- the hardware carries both
        concepts on CC 10 -- but rejects mono strips so a balance control can never
        be silently applied as a pan law.
        """
        if self.kind not in (ChannelKind.STEREO_INPUT, ChannelKind.STEREO_RETURN):
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) is mono and carries PAN, "
                "not BALANCE. Use set_pan()."
            )
        return self._boundary.execute_command(
            f"{self._prefix}.pan", value, source=source, unit=unit
        )

    # -----------------------------------------------------------------------
    # Preamp Gain & Low Cut (Channels 1-4 ONLY)
    # -----------------------------------------------------------------------

    def set_gain(self, value: Union[int, float], unit: str = "raw", source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """
        Set Preamp Gain (Channels 1-4 only).
        Unit: 'raw' (0-127) or 'dB' (-20.0 to +60.0 dB).
        Rejects on Channels 5-7 (Line and USB/BT inputs have no analog preamp gain).
        """
        if self.channel_index > 4 or (self._spec and not self._spec.has_preamp_gain):
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) does not have an analog preamp gain stage."
            )
        return self._boundary.execute_command(f"{self._prefix}.gain", value, source=source, unit=unit)

    def set_low_cut(self, value: Union[int, float], unit: str = "raw", source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """
        Set Low Cut filter frequency (Channels 1-4 only).
        Unit: 'raw' (0-127) or 'Hz' (20.0 to 600.0 Hz).
        Rejects on Channels 5-7.
        """
        if self.channel_index > 4 or (self._spec and not self._spec.has_low_cut):
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) does not have a low-cut filter stage."
            )
        return self._boundary.execute_command(f"{self._prefix}.low_cut", value, source=source, unit=unit)

    # -----------------------------------------------------------------------
    # 4-Band Parametric Equalizer (Channels 1-7)
    # -----------------------------------------------------------------------

    def set_eq_band(
        self,
        band: str,
        value: Union[int, float],
        unit: str = "raw",
        source: EventSource = EventSource.LOCAL_HOST
    ) -> CommandLogEntry:
        """
        Set EQ band gain (-15.0 dB to +15.0 dB, 64 = 0 dB).
        Band must be one of: 'low', 'low_mid', 'hi_mid', 'hi'.
        Unit: 'raw' (0-127) or 'dB' (-15.0 to +15.0 dB).
        """
        b_key = band.lower().replace("-", "_")
        if b_key not in VALID_EQ_BANDS:
            raise Flow8ValidationError(
                f"Invalid EQ band '{band}'. Valid bands: {VALID_EQ_BANDS}"
            )
        param_id = f"{self._prefix}.eq_{b_key}"
        return self._boundary.execute_command(param_id, value, source=source, unit=unit)

    # -----------------------------------------------------------------------
    # 1-Knob Dynamics Compressor (Channels 1-4 ONLY)
    # -----------------------------------------------------------------------

    def set_compressor(
        self,
        value: Union[int, float],
        unit: str = "raw",
        source: EventSource = EventSource.LOCAL_HOST
    ) -> CommandLogEntry:
        """
        Set 1-Knob Dynamics Compressor amount (Channels 1-4 only).
        Unit: 'raw' (0-127) or '%' (0.0 to 100.0%).
        Rejects on Channels 5-7.
        """
        if self._spec is not None and not self._spec.has_compressor:
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) does not have a 1-knob compressor stage."
            )
        if self._spec is not None and not self._spec.compressor_control_verified:
            # Capability is asserted by the hardware model, but no verified MIDI
            # control address exists. Classified UNKNOWN rather than invented.
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) compressor capability is "
                "hardware-specified but its MIDI control address is UNKNOWN. "
                "No command is dispatched."
            )
        if self.channel_index > 4:
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) is outside the verified "
                "compressor address scope (Channels 1-4)."
            )
        return self._boundary.execute_command(f"{self._prefix}.compressor", value, source=source, unit=unit)

    # -----------------------------------------------------------------------
    # Monitor & FX Auxiliary Sends (Channels 1-7)
    # -----------------------------------------------------------------------

    def set_send(
        self,
        target: str,
        value: Union[int, float],
        unit: str = "raw",
        source: EventSource = EventSource.LOCAL_HOST
    ) -> CommandLogEntry:
        """
        Set auxiliary send level to monitor or internal FX engine.
        Target must be one of: 'mon1', 'mon2', 'fx1', 'fx2'.
        Unit: 'raw' (0-127) or 'dB' (-70.0 to +10.0 dB).
        """
        t_key = target.lower()
        if t_key not in VALID_SEND_TARGETS:
            raise Flow8ValidationError(
                f"Invalid send target '{target}'. Valid targets: {VALID_SEND_TARGETS}"
            )
        param_id = f"{self._prefix}.send_{t_key}"
        return self._boundary.execute_command(param_id, value, source=source, unit=unit)

    # -----------------------------------------------------------------------
    # +48V Phantom Power (Channels 1-2 ONLY)
    # -----------------------------------------------------------------------

    def set_phantom(self, enabled: bool, source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """
        Set +48V Phantom Power state (Channels 1 & 2 only).
        Rejects on Channels 3-7.
        """
        if self.channel_index not in (1, 2):
            raise Flow8ValidationError(
                f"Channel {self.channel_index} ({self.name}) does not support +48V phantom power. "
                "Only Channels 1 and 2 feature hardware +48V relays."
            )
        return self._boundary.execute_command(f"{self._prefix}.phantom", bool(enabled), source=source, unit="raw")

    # -----------------------------------------------------------------------
    # State Inspection
    # -----------------------------------------------------------------------

    def get_parameter(self, param_name: str) -> ParameterState:
        """Retrieve the live ParameterState record for a parameter on this channel."""
        param_id = f"{self._prefix}.{param_name}"
        return self._state_store.get_parameter(param_id)


class Flow8BusStrip:
    """
    Dedicated controller for an output bus or effects send bus:
    'main', 'mon1', 'mon2', 'fx1', 'fx2'.
    """

    def __init__(self, bus_id: str, boundary: Flow8CommandBoundary, state_store: Flow8StateStore):
        b_key = bus_id.lower()
        if b_key not in VALID_BUS_IDS:
            raise Flow8ValidationError(f"Invalid FLOW 8 bus ID '{bus_id}'. Valid buses: {VALID_BUS_IDS}")

        self.bus_id = b_key
        self._boundary = boundary
        self._state_store = state_store

    def set_fader(self, value: Union[int, float], unit: str = "raw", source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """Set master fader / send level for this bus."""
        return self._boundary.execute_command(f"{self.bus_id}.fader", value, source=source, unit=unit)

    def set_balance(self, value: Union[int, float], unit: str = "raw", source: EventSource = EventSource.LOCAL_HOST) -> CommandLogEntry:
        """Set stereo balance (MAIN bus only)."""
        if self.bus_id != "main":
            raise Flow8ValidationError(f"Bus '{self.bus_id}' does not support stereo balance. Balance is Main L/R only.")
        return self._boundary.execute_command("main.balance", value, source=source, unit=unit)

    def get_parameter(self, param_name: str) -> ParameterState:
        """Retrieve the live ParameterState record for this bus."""
        param_id = f"{self.bus_id}.{param_name}"
        return self._state_store.get_parameter(param_id)


class Flow8ParameterEngine:
    """
    Unified high-level Parameter Engine for Behringer FLOW 8.
    Provides structured channel strip and bus controllers with guaranteed dispatch
    through the transactional Command Boundary.
    """

    def __init__(self, command_boundary: Flow8CommandBoundary, state_store: Flow8StateStore):
        self._boundary = command_boundary
        self._state_store = state_store
        self._channels: Dict[int, Flow8ChannelStrip] = {}
        self._buses: Dict[str, Flow8BusStrip] = {}

        # Instantiate channel strips (Channels 1-7)
        for ch in range(1, 8):
            self._channels[ch] = Flow8ChannelStrip(ch, self._boundary, self._state_store)

        # Instantiate bus strips
        for bid in VALID_BUS_IDS:
            self._buses[bid] = Flow8BusStrip(bid, self._boundary, self._state_store)

    @property
    def boundary(self) -> Flow8CommandBoundary:
        return self._boundary

    @property
    def state_store(self) -> Flow8StateStore:
        return self._state_store

    def channel(self, index: int) -> Flow8ChannelStrip:
        """Get the channel strip controller for input channel index (1 to 7)."""
        if index not in self._channels:
            raise Flow8ValidationError(f"Invalid input channel index {index}. Supported channels: 1 to 7.")
        return self._channels[index]

    def bus(self, bus_id: str) -> Flow8BusStrip:
        """Get the bus controller for bus_id ('main', 'mon1', 'mon2', 'fx1', 'fx2')."""
        b_key = bus_id.lower()
        if b_key not in self._buses:
            raise Flow8ValidationError(f"Invalid bus ID '{bus_id}'. Supported buses: {VALID_BUS_IDS}")
        return self._buses[b_key]

    # Convenience shortcuts
    def set_main_fader(self, value: Union[int, float], unit: str = "raw") -> CommandLogEntry:
        return self.bus("main").set_fader(value, unit=unit)

    def set_main_balance(self, value: Union[int, float], unit: str = "raw") -> CommandLogEntry:
        return self.bus("main").set_balance(value, unit=unit)

    def set_mon1_fader(self, value: Union[int, float], unit: str = "raw") -> CommandLogEntry:
        return self.bus("mon1").set_fader(value, unit=unit)

    def set_mon2_fader(self, value: Union[int, float], unit: str = "raw") -> CommandLogEntry:
        return self.bus("mon2").set_fader(value, unit=unit)

    def set_fx1_fader(self, value: Union[int, float], unit: str = "raw") -> CommandLogEntry:
        return self.bus("fx1").set_fader(value, unit=unit)

    def set_fx2_fader(self, value: Union[int, float], unit: str = "raw") -> CommandLogEntry:
        return self.bus("fx2").set_fader(value, unit=unit)

    def channel_for_physical_input(self, connector_id: str) -> Flow8ChannelStrip:
        """
        Resolve a physical connector (e.g. "IN_7L", "IN_6R", "USB_PORT") to the
        channel strip that controls it.

        Use this instead of assuming strip number == input number: input 7/8 is
        controlled by the `ch6` strip, and input 6 by `ch5`.
        """
        idx = logical_channel_for_connector(connector_id)
        if idx is None:
            from .domain_model import PHYSICAL_CONNECTORS
            if connector_id not in PHYSICAL_CONNECTORS:
                raise Flow8ValidationError(
                    f"Unknown FLOW 8 connector '{connector_id}'."
                )
            raise Flow8ValidationError(
                f"Connector '{connector_id}' is not mapped to a mixer channel strip."
            )
        return self.channel(idx)

    def get_state(self, param_id: str) -> ParameterState:
        """Read a live parameter state record from the store."""
        return self._state_store.get_parameter(param_id)

    def subscribe(self, listener: Callable[[ParameterState], None]):
        """Subscribe to all state store updates."""
        self._state_store.subscribe(listener)

    def unsubscribe(self, listener: Callable[[ParameterState], None]):
        """Unsubscribe from state store updates."""
        self._state_store.unsubscribe(listener)
