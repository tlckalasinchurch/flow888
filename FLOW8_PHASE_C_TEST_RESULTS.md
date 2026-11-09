# Phase C Test Results: FLOW 8 Parameter Engine
**Target:** Behringer FLOW 8 Digital Mixer  
**Date:** 2026-11-09  
**Execution Environment:** Windows 10 x86-64 / Python 3.14.8  
**Physical Hardware:** Behringer FLOW 8 (`USB\VID_1397&PID_050C\70-B9-50-66-4D-68`)  
**Verdict:** PASS (50/50 Tests Passed, 0 Failures, 0 Errors, 0 Skips)

> **Phase C.2 correction notice.** Two claims in this historical report were
> withdrawn by `FLOW8_PHASE_C1_AUDIT.md` and are superseded:
> 1. "0 Skips" was only true because the hardware tests had no opt-in gate. They
>    now skip by default (`FLOW8_HW_TESTS=1` to enable), and the suite is 104 tests.
> 2. The `<500 µs` figure below is **host-side function execution time**, not USB
>    transport, mixer response, or audio round-trip. No test asserts it.
> The raw results are preserved below unchanged as a record of what was run.

---

## 1. Test Execution Summary

### Test Command
```powershell
python -m unittest discover -s tests -v
```

### Complete Test Results
```text
test_audio_topology_counts (test_domain_and_state.TestDomainAndState.test_audio_topology_counts) ... ok
test_command_boundary_allowlist (test_domain_and_state.TestDomainAndState.test_command_boundary_allowlist) ... ok
test_command_boundary_validation (test_domain_and_state.TestDomainAndState.test_command_boundary_validation) ... ok
test_command_logging (test_domain_and_state.TestDomainAndState.test_command_logging) ... ok
test_logical_channel_relationships (test_domain_and_state.TestDomainAndState.test_logical_channel_relationships) ... ok
test_output_buses (test_domain_and_state.TestDomainAndState.test_output_buses) ... ok
test_physical_input_topology (test_domain_and_state.TestDomainAndState.test_physical_input_topology) ... ok
test_state_store_verification_levels (test_domain_and_state.TestDomainAndState.test_state_store_verification_levels) ... ok
test_state_transitions (test_domain_and_state.TestDomainAndState.test_state_transitions) ... ok
test_hardware_context_manager (test_hardware_midi_out.TestHardwareMidiOut.test_hardware_context_manager) ... ok
test_hardware_lifecycle (test_hardware_midi_out.TestHardwareMidiOut.test_hardware_lifecycle) ... ok
test_hardware_midi_in_lifecycle (test_hardware_midi_out.TestHardwareMidiOut.test_hardware_midi_in_lifecycle) ... ok
test_hardware_parameter_dispatches (test_hardware_midi_out.TestHardwareMidiOut.test_hardware_parameter_dispatches) ... ok
test_hardware_parameter_engine_dispatch (test_hardware_midi_out.TestHardwareMidiOut.test_hardware_parameter_engine_dispatch) ... ok
test_hardware_reconnect (test_hardware_midi_out.TestHardwareMidiOut.test_hardware_reconnect) ... ok
test_byte_encoding_and_dispatch (test_midi_out.TestFlow8MidiOut.test_byte_encoding_and_dispatch) ... ok
test_disconnection_during_dispatch (test_midi_out.TestFlow8MidiOut.test_disconnection_during_dispatch) ... ok
test_invalid_cc_number_validation (test_midi_out.TestFlow8MidiOut.test_invalid_cc_number_validation) ... ok
test_invalid_channel_validation (test_midi_out.TestFlow8MidiOut.test_invalid_channel_validation) ... ok
test_invalid_value_validation (test_midi_out.TestFlow8MidiOut.test_invalid_value_validation) ... ok
test_lifecycle_and_duplicate_handles (test_midi_out.TestFlow8MidiOut.test_lifecycle_and_duplicate_handles) ... ok
test_open_endpoint_allocation_error (test_midi_out.TestFlow8MidiOut.test_open_endpoint_allocation_error) ... ok
test_open_endpoint_not_found (test_midi_out.TestFlow8MidiOut.test_open_endpoint_not_found) ... ok
test_send_when_disconnected_raises_error (test_midi_out.TestFlow8MidiOut.test_send_when_disconnected_raises_error) ... ok
test_unverified_parameter_rejected (test_midi_out.TestFlow8MidiOut.test_unverified_parameter_rejected) ... ok
test_4band_eq_all_input_channels (test_parameter_engine.TestParameterEngine.test_4band_eq_all_input_channels) ... ok
test_auxiliary_sends_all_input_channels (test_parameter_engine.TestParameterEngine.test_auxiliary_sends_all_input_channels) ... ok
test_bus_balance_restrictions (test_parameter_engine.TestParameterEngine.test_bus_balance_restrictions) ... ok
test_bus_strip_instantiation (test_parameter_engine.TestParameterEngine.test_bus_strip_instantiation) ... ok
test_channel_strip_instantiation (test_parameter_engine.TestParameterEngine.test_channel_strip_instantiation) ... ok
test_compressor_channel_restrictions (test_parameter_engine.TestParameterEngine.test_compressor_channel_restrictions) ... ok
test_low_cut_channel_restrictions (test_parameter_engine.TestParameterEngine.test_low_cut_channel_restrictions) ... ok
test_mocked_hardware_dispatch (test_parameter_engine.TestParameterEngine.test_mocked_hardware_dispatch) ... ok
test_offline_dispatch_flag (test_parameter_engine.TestParameterEngine.test_offline_dispatch_flag) ... ok
test_phantom_power_channel_restrictions (test_parameter_engine.TestParameterEngine.test_phantom_power_channel_restrictions) ... ok
test_preamp_gain_channel_restrictions (test_parameter_engine.TestParameterEngine.test_preamp_gain_channel_restrictions) ... ok
test_unit_conversions (test_parameter_engine.TestParameterEngine.test_unit_conversions) ... ok
test_fader_cardinal_points (test_parameter_mapping.TestParameterMapping.test_fader_cardinal_points) ... ok
test_fader_clamping (test_parameter_mapping.TestParameterMapping.test_fader_clamping) ... ok
test_fader_monotonicity (test_parameter_mapping.TestParameterMapping.test_fader_monotonicity) ... ok
test_fader_off_handling (test_parameter_mapping.TestParameterMapping.test_fader_off_handling) ... ok
test_fader_out_of_bounds_midi (test_parameter_mapping.TestParameterMapping.test_fader_out_of_bounds_midi) ... ok
test_mute_bool_to_midi (test_parameter_mapping.TestParameterMapping.test_mute_bool_to_midi) ... ok
test_mute_midi_to_bool (test_parameter_mapping.TestParameterMapping.test_mute_midi_to_bool) ... ok
test_mute_out_of_bounds (test_parameter_mapping.TestParameterMapping.test_mute_out_of_bounds) ... ok
test_pan_center (test_parameter_mapping.TestParameterMapping.test_pan_center) ... ok
test_pan_clamping (test_parameter_mapping.TestParameterMapping.test_pan_clamping) ... ok
test_pan_extremes (test_parameter_mapping.TestParameterMapping.test_pan_extremes) ... ok
test_pan_monotonicity (test_parameter_mapping.TestParameterMapping.test_pan_monotonicity) ... ok
test_pan_out_of_bounds_midi (test_parameter_mapping.TestParameterMapping.test_pan_out_of_bounds_midi) ... ok

----------------------------------------------------------------------
Ran 50 tests in 1.141s

OK
```

---

## 2. Test Breakdown by Category

| Category | File | Count | Passed | Failed | Status |
|---|---|---|---|---|---|
| **Parameter Engine** | `tests/test_parameter_engine.py` | 12 | 12 | 0 | **PASS** |
| **Physical Hardware Integration** | `tests/test_hardware_midi_out.py` | 6 | 6 | 0 | **PASS** |
| **Domain Model & State Store** | `tests/test_domain_and_state.py` | 9 | 9 | 0 | **PASS** |
| **MIDI Out Driver & Mock** | `tests/test_midi_out.py` | 10 | 10 | 0 | **PASS** |
| **Parameter Mapping & Math** | `tests/test_parameter_mapping.py` | 13 | 13 | 0 | **PASS** |
| **TOTAL** | | **50** | **50** | **0** | **PASS (100%)** |

---

## 3. Physical Hardware Proof Verification

### Test: `test_hardware_parameter_engine_dispatch`
- **Mixer Hardware:** Behringer FLOW 8
- **USB VID/PID:** `VID_1397&PID_050C`
- **Endpoints Connected:** `FLOW 8 MIDI IN [0]`, `FLOW 8 MIDI OUT [0]`
- **Pipeline Exercised:**
  `Flow8ParameterEngine -> Flow8CommandBoundary -> Flow8MidiOut -> winmm.dll -> FLOW 8`
- **Messages Dispatched & Confirmed:**
  1. `ch1.pan` $\rightarrow 0.0\%$ (Center, raw MIDI `64`, Status `0xB0`, CC `10`): Dispatched, `dispatched_to_hardware = True`.
  2. `ch1.eq_low` $\rightarrow 0.0\text{ dB}$ (Center, raw MIDI `64`, Status `0xB0`, CC `1`): Dispatched, `dispatched_to_hardware = True`.
  3. `main.fader` $\rightarrow 0$ (Muted/off, raw MIDI `0`, Status `0xB7`, CC `7`): Dispatched, `dispatched_to_hardware = True`.
- **Latency Measurement (corrected):** each transaction's **host-side function
  execution time** was below $500\ \mu\text{s}$, measured with `time.perf_counter()`
  around `execute_command` in `flow8/command_boundary.py`. This covers validation,
  unit conversion, the `midiOutShortMsg` call and the state update. It is **not**
  USB transport latency, **not** mixer response latency, and **not** audio
  round-trip latency: `midiOutShortMsg` queues the message and returns before USB
  framing completes, and the tests sleep 50 ms between messages. No test asserts
  this value.

---

## 4. Dispatched-to-Hardware Flag Validation

| Test Condition | Mock / Hardware State | `success` | `dispatched_to_hardware` | Expected Behavior Verified |
|---|---|---|---|---|
| Offline Unit Test | `midi_out.is_connected = False` | `True` | `False` | State store accepts commanded value; log confirms no wire transmission. |
| Allowlist Rejection | Target `ch5.gain` (unsupported) | `False` | `False` | Exception raised (`Flow8CommandRejectedError`); zero dispatch. |
| Validation Error | Value `128` (out of range) | `False` | `False` | Exception raised (`Flow8ValidationError`); zero dispatch. |
| Connected Hardware | `midi_out.is_connected = True` | `True` | `True` | Physical message sent via `midiOutShortMsg`; log records wire delivery. |
