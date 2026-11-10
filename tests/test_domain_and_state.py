"""
Unit tests for FLOW 8 Domain Model, State Store, and Command Boundary.
Verifies topology, strict allowlist enforcement, state transitions, and error handling.
"""

import unittest
from flow8.domain_model import (
    PHYSICAL_CONNECTORS,
    LOGICAL_CHANNELS,
    OUTPUT_BUSES,
    FLOW8_AUDIO_TOPOLOGY,
    ConnectorType,
    ChannelKind,
)
from flow8.state_model import (
    Flow8StateStore,
    VerificationLevel,
    SyncStatus,
    EventSource,
)
from flow8.command_boundary import (
    Flow8CommandBoundary,
    Flow8CommandRejectedError,
)
from flow8.midi_out import Flow8MidiOut, Flow8ValidationError

class TestDomainAndState(unittest.TestCase):

    # -----------------------------------------------------------------------
    # 1. Hardware Domain Model Tests
    # -----------------------------------------------------------------------
    def test_physical_input_topology(self):
        # 1. Inputs 1-2 must be XLR with Phantom Power
        self.assertEqual(PHYSICAL_CONNECTORS["IN_1"].connector_type, ConnectorType.XLR_FEMALE)
        self.assertTrue(PHYSICAL_CONNECTORS["IN_1"].has_phantom_power)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_1"].has_hi_z)

        self.assertEqual(PHYSICAL_CONNECTORS["IN_2"].connector_type, ConnectorType.XLR_FEMALE)
        self.assertTrue(PHYSICAL_CONNECTORS["IN_2"].has_phantom_power)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_2"].has_hi_z)

        # 2. Inputs 3-4 must be Combo without Hi-Z and without Phantom
        self.assertEqual(PHYSICAL_CONNECTORS["IN_3"].connector_type, ConnectorType.XLR_TRS_COMBO)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_3"].has_hi_z)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_3"].has_phantom_power)

        self.assertEqual(PHYSICAL_CONNECTORS["IN_4"].connector_type, ConnectorType.XLR_TRS_COMBO)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_4"].has_hi_z)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_4"].has_phantom_power)

        # 3. Hi-Z must be on Connectors 6R and 8R ONLY
        self.assertFalse(PHYSICAL_CONNECTORS["IN_5L"].has_hi_z)
        self.assertTrue(PHYSICAL_CONNECTORS["IN_6R"].has_hi_z)
        self.assertFalse(PHYSICAL_CONNECTORS["IN_7L"].has_hi_z)
        self.assertTrue(PHYSICAL_CONNECTORS["IN_8R"].has_hi_z)

    def test_logical_channel_relationships(self):
        # Channels 1-4 are Mono Inputs
        for ch in (1, 2, 3, 4):
            self.assertEqual(LOGICAL_CHANNELS[ch].kind, ChannelKind.MONO_INPUT)
            self.assertEqual(LOGICAL_CHANNELS[ch].pan_or_balance, "PAN")
            self.assertTrue(LOGICAL_CHANNELS[ch].has_low_cut)
            self.assertTrue(LOGICAL_CHANNELS[ch].has_preamp_gain)

        # Channel 5/6 and 7/8 are Stereo Pairs
        self.assertEqual(LOGICAL_CHANNELS[5].kind, ChannelKind.STEREO_INPUT)
        self.assertEqual(LOGICAL_CHANNELS[5].pan_or_balance, "BALANCE")
        self.assertIn("IN_6R", LOGICAL_CHANNELS[5].physical_connectors)
        self.assertTrue(LOGICAL_CHANNELS[5].has_hi_z)

        self.assertEqual(LOGICAL_CHANNELS[6].kind, ChannelKind.STEREO_INPUT)
        self.assertEqual(LOGICAL_CHANNELS[6].pan_or_balance, "BALANCE")
        self.assertIn("IN_8R", LOGICAL_CHANNELS[6].physical_connectors)
        self.assertTrue(LOGICAL_CHANNELS[6].has_hi_z)

    def test_output_buses(self):
        # MAIN, MON1, MON2 have 9-band GEQ and Limiters
        self.assertTrue(OUTPUT_BUSES["MAIN"].has_9band_geq)
        self.assertTrue(OUTPUT_BUSES["MAIN"].has_limiter)
        self.assertTrue(OUTPUT_BUSES["MON1"].has_9band_geq)
        self.assertTrue(OUTPUT_BUSES["MON1"].has_limiter)
        self.assertTrue(OUTPUT_BUSES["MON2"].has_9band_geq)
        self.assertTrue(OUTPUT_BUSES["MON2"].has_limiter)

        # FX buses do not have GEQ or Limiter
        self.assertFalse(OUTPUT_BUSES["FX1"].has_9band_geq)
        self.assertFalse(OUTPUT_BUSES["FX2"].has_9band_geq)

        # PHONES bus is a physical monitoring output tap, not an independent DSP bus
        self.assertEqual(OUTPUT_BUSES["PHONES"].kind, ChannelKind.MONITOR_OUTPUT)

    def test_audio_topology_counts(self):
        self.assertEqual(FLOW8_AUDIO_TOPOLOGY.capture_channel_count, 10)
        self.assertEqual(FLOW8_AUDIO_TOPOLOGY.playback_channel_count_standard, 2)
        self.assertEqual(FLOW8_AUDIO_TOPOLOGY.playback_channel_count_driver, 4)
        self.assertEqual(FLOW8_AUDIO_TOPOLOGY.sample_rate_hz, 48000)
        self.assertEqual(FLOW8_AUDIO_TOPOLOGY.bit_depth, 24)

    # -----------------------------------------------------------------------
    # 2. State Store Tests
    # -----------------------------------------------------------------------
    def test_state_store_verification_levels(self):
        store = Flow8StateStore()
        # WinMM driver acceptance is not an application-level acknowledgement.
        # No code path may produce API_ACKNOWLEDGED without that evidence.
        for param_id in ("main.fader", "ch1.fader", "ch1.mute", "ch1.pan"):
            self.assertEqual(
                store.get_parameter(param_id).verification_level,
                VerificationLevel.UNKNOWN,
            )
        self.assertFalse(any(
            record["verification_level"] == VerificationLevel.API_ACKNOWLEDGED.value
            for record in store.get_all_parameters().values()
        ))

        # Nothing may be graded HARDWARE_TESTED without a recorded observation.
        for param_id, record in store.get_all_parameters().items():
            self.assertNotEqual(
                record["verification_level"],
                VerificationLevel.HARDWARE_TESTED.value,
                f"{param_id} claims HARDWARE_TESTED without physical confirmation",
            )

        # Compressor capability on the stereo pairs is unresolved, not denied.
        self.assertEqual(store.get_parameter("ch5.compressor").verification_level, VerificationLevel.UNKNOWN)
        self.assertEqual(store.get_parameter("ch6.compressor").verification_level, VerificationLevel.UNKNOWN)

        # Channels 2-7 must be PROTOCOL_VERIFIED, NOT HARDWARE_TESTED
        self.assertEqual(store.get_parameter("ch2.fader").verification_level, VerificationLevel.PROTOCOL_VERIFIED)
        self.assertEqual(store.get_parameter("ch5.fader").verification_level, VerificationLevel.PROTOCOL_VERIFIED)

        # EZ Gain must be HARDWARE_SPECIFIED
        self.assertEqual(store.get_parameter("global.ez_gain").verification_level, VerificationLevel.HARDWARE_SPECIFIED)

    def test_state_transitions(self):
        store = Flow8StateStore()
        notifications = []
        store.subscribe(lambda p: notifications.append((p.param_id, p.sync_status)))

        # 1. Command a value -> PENDING_DISPATCH
        p = store.set_commanded_value("ch1.fader", 50, EventSource.LOCAL_HOST, raw_midi_value=50)
        self.assertEqual(p.commanded_value, 50)
        self.assertEqual(p.sync_status, SyncStatus.PENDING_DISPATCH)
        self.assertEqual(len(notifications), 1)

        # 2. Receive observed telemetry matching commanded -> SYNCED
        p2 = store.set_observed_value("ch1.fader", 50, EventSource.PHYSICAL_HARDWARE, raw_midi_value=50)
        self.assertEqual(p2.sync_status, SyncStatus.SYNCED)
        self.assertEqual(len(notifications), 2)

        # 3. Receive divergent telemetry -> DIVERGENT
        p3 = store.set_observed_value("ch1.fader", 80, EventSource.PHYSICAL_HARDWARE, raw_midi_value=80)
        self.assertEqual(p3.sync_status, SyncStatus.DIVERGENT)
        self.assertEqual(len(notifications), 3)

    # -----------------------------------------------------------------------
    # 3. Command Boundary Tests
    # -----------------------------------------------------------------------
    def test_command_boundary_allowlist(self):
        midi_out = Flow8MidiOut()
        store = Flow8StateStore()
        boundary = Flow8CommandBoundary(midi_out, store)

        # Permitted parameter succeeds
        entry = boundary.execute_command("main.fader", 60)
        self.assertTrue(entry.success)
        self.assertFalse(entry.dispatched_to_hardware)  # Offline in mock/unit test
        self.assertIsNone(entry.raw_midi_sent)  # nothing was submitted to the driver
        self.assertEqual(entry.raw_midi_prepared, 60)
        self.assertEqual(store.get_parameter("main.fader").commanded_value, 60)

        # Disallowed parameter raises Flow8CommandRejectedError
        with self.assertRaises(Flow8CommandRejectedError):
            boundary.execute_command("ch5.gain", 50)  # Ch 5 has no preamp gain

        with self.assertRaises(Flow8CommandRejectedError):
            boundary.execute_command("global.ez_gain", 1)

    def test_command_boundary_validation(self):
        midi_out = Flow8MidiOut()
        store = Flow8StateStore()
        boundary = Flow8CommandBoundary(midi_out, store)

        # Out-of-bounds fader value raises Flow8ValidationError
        with self.assertRaises(Flow8ValidationError):
            boundary.execute_command("ch1.fader", 128)

        with self.assertRaises(Flow8ValidationError):
            boundary.execute_command("ch1.fader", -1)

    def test_command_logging(self):
        midi_out = Flow8MidiOut()
        store = Flow8StateStore()
        boundary = Flow8CommandBoundary(midi_out, store)

        boundary.execute_command("ch1.fader", 10)
        boundary.execute_command("ch1.mute", True)
        self.assertEqual(len(boundary.command_log), 2)
        self.assertEqual(boundary.command_log[0].param_id, "ch1.fader")
        self.assertEqual(boundary.command_log[1].param_id, "ch1.mute")

if __name__ == '__main__':
    unittest.main()
