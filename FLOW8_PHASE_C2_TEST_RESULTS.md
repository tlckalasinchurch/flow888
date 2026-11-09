# Phase C.2 — Test Results

**Target:** Behringer FLOW 8 Digital Mixer
**Date:** 2026-11-09
**Framework:** `unittest` (unchanged — pytest was **not** installed and the project
was **not** migrated)
**Environment:** Windows, Python 3.14, physical `FLOW 8 MIDI OUT` / `FLOW 8 MIDI IN`
endpoints present on the machine

---

## 1. Headline

| Metric | Value |
|---|---|
| Total tests collected | **104** |
| Passed | **99** |
| Failed | **0** |
| Errors | **0** |
| Skipped | **5** (all physical-hardware tests, opted out by default) |
| Exit status | **0** |
| MIDI sent to hardware during the default run | **none** |

Baseline before this phase: 50 tests, 0 skipped, and the 6 "hardware" tests
executed against the live mixer.

---

## 2. Commands and actual output

### 2.1 Full regression suite (default, safe)

```
python -m unittest discover -s tests -v
```

```
Ran 104 tests in 0.056s

OK (skipped=5)
EXIT_FULL=0
```

The five skips are, by name:

```
test_hardware_in_lifecycle                      skipped
test_hardware_out_lifecycle                     skipped
test_hardware_out_reconnect                     skipped
test_hardware_out_context_manager               skipped
test_dispatch_is_api_acknowledgement_only       skipped
```

Every skip reason states that nothing was transmitted and how to opt in.

### 2.2 Focused modules

```
python -m unittest tests.test_parameter_engine tests.test_midi_out \
                      tests.test_domain_and_state tests.test_parameter_mapping -v
python -m unittest tests.test_channel_addressing tests.test_bus_mappings \
                      tests.test_command_boundary_integrity -v
python -m unittest tests.test_hardware_midi_out -v
```

- Core modules: all pass.
- New Phase C.2 modules: all pass (see section 4).
- Hardware module: 5 tests, all skipped by default.

### 2.3 Tier-1 hardware opt-in (non-mutating) — verified

```
FLOW8_HW_TESTS=1 python -m unittest tests.test_hardware_midi_out -v
```

```
test_hardware_in_lifecycle           ... ok
test_hardware_out_context_manager    ... ok
test_hardware_out_lifecycle          ... ok
test_hardware_out_reconnect          ... ok
test_dispatch_is_api_acknowledgement_only ... skipped

Ran 5 tests in 0.256s

OK (skipped=1)
```

Confirms the gate works in both directions: tier 1 enables endpoint lifecycle
tests and still refuses the mutating tier. Tier 1 opens/closes endpoints only and
transmits no MIDI, so mixer state cannot change.

### 2.4 Tier-2 (mutating) — NOT executed

`FLOW8_HW_TESTS_MUTATE=1` was deliberately **not** set. Phase C.2 changes the test
harness and the state model; it has no mandate to write new parameter values to the
mixer, and the audit's restriction on undocumented hardware operations still
applies. The tier exists and is documented for an operator-supervised session.

---

## 3. Safety verification (requirement: default suite must not touch hardware)

Three independent confirmations:

1. **Skip at class level.** `@unittest.skipUnless(...)` is on the class, so `setUp()`
   never runs without opt-in. `Flow8MidiOut()` is never constructed, `midiOutOpen`
   is never called, `find_device_id()` never enumerates.
2. **Observed skip output.** All 5 hardware tests report `skipped`, 0 executed
   (section 2.1).
3. **No transport path.** The remaining 99 tests either use `MagicMock` for
   `winmm`, or a `Flow8MidiOut` with `_is_open = False` (offline), which returns
   before `midiOutShortMsg`.

There is no test in the default suite that can reach `midiOutShortMsg` on a real
handle.

---

## 4. Coverage added in Phase C.2

| Area | Test module | What it pins |
|---|---|---|
| Dispatch transaction | `test_command_boundary_integrity.py` | failed dispatch does not commit state; offline ≠ dispatched; rejection/validation logging; `hardware_applied` stays `None`; latency is host-side |
| Allowlist integrity | `test_command_boundary_integrity.py` | channel/CC scope, bounds ordering, identity match, `(channel, cc)` uniqueness, every param has a state record |
| Bounds enforcement | `test_command_boundary_integrity.py` | table-driven over all 97 entries: min/max accepted, below-min and above-max rejected; boolean strictness |
| Capability scope | `test_command_boundary_integrity.py` | gain/low-cut/compressor on Ch 1–4 only; phantom Ch 1–2; compressor 5/6 not offered |
| Channel addressing | `test_channel_addressing.py` | strip→MIDI channel, strip 6 = 7/8 pair, connector resolution, literal status bytes, `ch5` ≠ `ch6` |
| Stereo balance | `test_channel_addressing.py` | balance accepted on 5/6/7, rejected on mono, state labelled `balance` |
| Bus layer | `test_bus_mappings.py` | 5 buses × channel/CC/status/value; 11 invalid addresses; 3 CC collision pairs |
| Verification levels | `test_domain_and_state.py` | nothing graded `HARDWARE_TESTED`; compressor 5/6 `UNKNOWN` |
| Hardware gating | `test_hardware_midi_out.py` | default skip; two-tier opt-in |

### 4.1 Byte-level coverage movement

Before Phase C.2: **5 of 97** `(channel, CC)` pairs asserted at the wire.

After: the bus layer (6 pairs) is fully covered plus the ch1 pairs previously
covered, and channel addressing asserts one pair per strip. Remaining uncovered
sets are the per-channel EQ middle bands, sends on Ch 2–7, gain/low-cut/compressor
on Ch 2–4, and phantom on Ch 2. Not addressed in this phase — recorded as an open
item rather than claimed as done.

---

## 5. Assertions changed (disclosed)

Phase C.2 changed behaviour by design, so some existing expectations had to change.
Every change tightens an assertion; none weakens one:

| Test | Before | After | Reason |
|---|---|---|---|
| `test_offline_dispatch_flag` | `raw_midi_sent == 75` | `raw_midi_sent is None`, `raw_midi_prepared == 75` | Offline sends nothing by definition (C.2 §3C) |
| `test_preamp_gain_channel_restrictions` | `raw_midi_sent == 20` | `raw_midi_prepared == 20` | Same; test is about capability, not delivery |
| `test_compressor_channel_restrictions` | `raw_midi_sent == 50` | `raw_midi_prepared == 50` | Same |
| `test_phantom_power_channel_restrictions` | `raw_midi_sent` 127/0 | `raw_midi_prepared` 127/0 | Same |
| `test_bus_balance_restrictions` | `raw_midi_sent == 64` | `raw_midi_prepared == 64` | Same |
| `test_4band_eq_all_input_channels` | `raw_midi_sent == 64` | `raw_midi_prepared == 64` | Same |
| `test_auxiliary_sends_all_input_channels` | `raw_midi_sent == 45` | `raw_midi_prepared == 45` | Same |
| `test_unit_conversions` (9 asserts) | `raw_midi_sent` | `raw_midi_prepared` | These assert conversion maths, not delivery |
| `test_state_store_verification_levels` | 4 × `HARDWARE_TESTED` | 4 × `API_ACKNOWLEDGED` + no `HARDWARE_TESTED` anywhere | Required verification-level correction |
| `test_command_boundary_allowlist` | `raw_midi_sent == 60` | `raw_midi_sent is None`, `raw_midi_prepared == 60` | Same |

`test_mocked_hardware_dispatch` keeps `raw_midi_sent == 100` because that path is
connected and genuinely submits bytes.

No assertion was deleted, and no test was removed or renamed.

---

## 6. Failure encountered and fixed

One genuine failure during development:

```
FAIL: test_failed_dispatch_does_not_commit_commanded_state
AssertionError: 'dispatch failed' not found in
  'failed to send midi cc (0x3207b0): error code 1'
```

The log entry's `error_message` intentionally preserves the underlying transport
error verbatim (better diagnostics) rather than replacing it with a generic string.
The test expectation was corrected to assert the transport text in the log entry
and `"hardware dispatch failed"` in the raised exception, which is where that
wording lives.

---

## 7. Limitations

- **No physical confirmation.** Tier 2 was not run; no observation channel exists.
  Nothing here demonstrates that the mixer applied anything or that audio changed.
- **No USB trace.** Transmission is still unmeasured; `driver_dispatched` remains
  an API-acknowledgement claim only.
- **`HARDWARE_TESTED` is vacant.** Nothing in the codebase holds that grade now,
  which is the honest state: there is no retained physical observation.
- **Bus-layer byte coverage is complete for the 6 bus parameters, but sends on
  Ch 2–7, EQ middle bands, and gain/low-cut/compressor on Ch 2–4 remain without
  wire-level assertions.** Recorded as an open item, not claimed as done.
