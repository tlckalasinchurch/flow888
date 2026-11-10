# Phase C.2 — Safety & Integrity Remediation

**Target:** Behringer FLOW 8 Digital Mixer (USB `VID_1397&PID_050C`)
**Phase:** C.2 — remediation of `FLOW8_PHASE_C1_AUDIT.md` findings
**Date:** 2026-11-09
**Status:** COMPLETE — 104 tests, 99 passed, 5 skipped (hardware, opt-in), 0 failed

---

## 1. Scope

Focused remediation only. No architecture redesign, no Phase D, no Audio Engine,
no DSP, no UI/Mobile, no new MIDI mappings, no BLE implementation.

Source files changed:

| File | Change |
|---|---|
| `flow8/command_boundary.py` | Rewritten dispatch transaction; explicit status vocabulary; per-entry bounds enforced; allowlist self-validation; channel derived from domain model |
| `flow8/state_model.py` | Added `API_ACKNOWLEDGED` level; re-graded 4 parameters; added `UNKNOWN` compressor records; raw-domain sync comparison |
| `flow8/domain_model.py` | Added explicit `midi_channel` + `compressor_control_verified`; reverse index; connector resolver |
| `flow8/parameter_engine.py` | Identity docstring; `set_balance()`; `channel_for_physical_input()`; precise compressor guard |
| `flow8/midi_out.py` | `send_cc` returns the submitted message; dispatch-semantics docstring |

Tests changed/added:

| File | Change |
|---|---|
| `tests/test_hardware_midi_out.py` | Rewritten: two-tier opt-in, non-destructive, no automatic restore |
| `tests/test_parameter_engine.py` | Assertions updated to the corrected dispatch contract |
| `tests/test_domain_and_state.py` | Verification-level and `raw_midi_sent` expectations corrected |
| `tests/test_channel_addressing.py` | **New** — section 4 regression coverage |
| `tests/test_bus_mappings.py` | **New** — section 7 byte-level bus tests |
| `tests/test_command_boundary_integrity.py` | **New** — sections 3 and 6 |

---

## 2. Hardware test protection (section 1)

### 2.1 Problem

`tests/test_hardware_midi_out.py` was discovered by `unittest discover`, was not
mocked, and had no opt-in. On this machine a live `FLOW 8 MIDI OUT` endpoint was
present, so the tests executed, transmitted real CC, and left **Main and Ch 1 at
fader 0 (silent)** with no restore logic.

### 2.2 Design

Two independent tiers, because "open an endpoint" and "change the mix" carry very
different risk:

| Tier | Gate | Behaviour |
|---|---|---|
| 1 — non-mutating | `FLOW8_HW_TESTS=1` | Enumerate, open, start, stop, close. **Transmits no MIDI at all.** |
| 2 — mutating | `FLOW8_HW_TESTS=1` **and** `FLOW8_HW_TESTS_MUTATE=1` | Sends CC that changes mixer parameters. |

Implementation: `@unittest.skipUnless(cond, reason)` at **class** level, so when
the opt-in is absent `setUp()` never runs — the endpoint is not even enumerated.

Default behaviour now:

```
FLOW8_HW_TESTS unset
  TestHardwareEndpointsNonMutating          -> skipped (4 tests)
  TestHardwareParameterDispatchMutating     -> skipped (1 test)
```

### 2.3 What tier 2 deliberately refuses to do

- **No fader writes.** Main, Monitor and channel faders are untouched: a mistaken
  fader write can silence a live PA.
- **No phantom power.** +48 V is never energised by a test.
- **No restore from guessed values.** The prior mixer state is never assumed
  known. Guessing a "restore" value would be worse than leaving visible state.
- Every operation lands on a **neutral** position, so the mixer ends sane
  regardless of where it started: pan → centre (64), EQ low → 0.0 dB (flat, 64),
  mute → ON then OFF (ends unmuted).

---

## 3. Verification-level correction (section 2)

### 3.1 New level

`VerificationLevel.API_ACKNOWLEDGED` was added between `PROTOCOL_VERIFIED` and
`IMPLEMENTED`. It means exactly one thing: *the Windows MIDI driver accepted a
message (`midiOutShortMsg` returned `MMSYSERR_NOERROR`)*. It asserts nothing about
USB transmission, mixer application, or audio.

### 3.2 Re-graded parameters

| Parameter | Was | Now | Why |
|---|---|---|---|
| `main.fader` | `HARDWARE_TESTED` | `API_ACKNOWLEDGED` | Only evidence is a WinMM return code |
| `ch1.fader` | `HARDWARE_TESTED` | `API_ACKNOWLEDGED` | same |
| `ch1.mute` | `HARDWARE_TESTED` | `API_ACKNOWLEDGED` | same |
| `ch1.pan` | `HARDWARE_TESTED` | `API_ACKNOWLEDGED` | same |

No parameter in the state store is graded `HARDWARE_TESTED` any more, and a
regression test enforces that (`test_state_store_verification_levels`).

### 3.3 The four distinctions are now enforced in code

| Concept | How it is represented |
|---|---|
| API acknowledgment | `CommandLogEntry.driver_dispatched` / `dispatch_status == DRIVER_DISPATCHED` |
| USB transmission | **not modelled** — no evidence channel exists |
| Mixer application | `CommandLogEntry.hardware_applied` — always `None` |
| Audible change | **not modelled** — requires audio capture |

`hardware_applied` is never set to `True` by any code path. There is no
confirmation channel, so reporting `True` would be fabrication.

### 3.4 `parameter_mapping.py`

The `VERIFIED` labels in the module docstring were left semantically intact but the
classification is recorded in the verification matrix as *chart-mapped, uncited*.
The dB curve (`FADER_UNITY_MIDI = 101`, `-70 dB … 0 dB … +10 dB`) remains an
explicitly labelled **unverified approximation**; it was already marked as such and
is unchanged.

---

## 4. Transaction and dispatch integrity (section 3)

### 4.1 Status vocabulary

```python
class DispatchStatus:
    REJECTED            # not in allowlist
    VALIDATION_FAILED   # out of range / bad type
    ACCEPTED_OFFLINE    # validated + state committed, NOTHING sent
    DRIVER_DISPATCHED   # handed to WinMM (device may not have applied)
    DISPATCH_FAILED     # connected, but the driver call failed
```

### 4.2 `CommandLogEntry` fields

Backward-compatible additions (all defaulted):

| Field | Meaning |
|---|---|
| `command_accepted` | passed allowlist + validation |
| `driver_dispatched` | `midiOutShortMsg` returned 0 |
| `hardware_applied` | **always `None`** until an observation channel exists |
| `raw_midi_prepared` | value computed, for troubleshooting |
| `dispatch_status` | one of the five states above |
| `observed_value` | from the state record (`None` today) |
| `verification_level` | from the state record |

`raw_midi_sent` keeps its name but now holds bytes **only** when they were actually
submitted to the driver. It is `None` for rejected, invalid, offline and failed.

### 4.3 Failed dispatch (finding F-01)

Before: the failure branch fell through to `set_commanded_value`, so the state
store recorded a value the mixer never received, `raw_midi_sent` claimed a send,
and `sync_status` became `PENDING_DISPATCH` for a dispatch that already failed.

Now:

```
dispatch raises -> dispatch_success = False
                -> state store NOT touched
                -> log entry: success=False, raw_midi_sent=None,
                              raw_midi_prepared=<value>, dispatch_status=DISPATCH_FAILED,
                              error_message=<underlying transport error verbatim>
                -> Flow8CommandError("Hardware dispatch failed ...")
```

`error_message` deliberately preserves the underlying driver text
(e.g. `Failed to send MIDI CC (0x3207B0): error code 1`) rather than replacing it,
so the root cause survives for troubleshooting.

### 4.4 Offline dispatch (finding F-05)

`success` still means "accepted and processed without a dispatch failure" and is
`True` offline, because the command genuinely was accepted. But it can no longer be
confused with delivery:

- `dispatch_status = ACCEPTED_OFFLINE`
- `driver_dispatched = False`, `dispatched_to_hardware = False`
- `raw_midi_sent = None`, `raw_midi_prepared = <value>`
- state committed as `PENDING_DISPATCH` (correct: it is genuinely pending)

### 4.5 Unit-mismatched sync (finding F-16)

`ParameterState` gained `commanded_raw_midi` and `observed_raw_midi`. Sync
determination now prefers the raw MIDI domain, so a commanded `-50.0` dB value and
an observed raw `37` can no longer produce guaranteed false `DIVERGENT`. Falls back
to value equality only when raw values are unavailable.

---

## 5. Channel addressing (section 4)

### 5.1 Investigation result

Traced end to end: domain channel index → logical strip → MIDI channel → status
byte → engine addressing.

**The MIDI address was already correct.** `ch6` → MIDI channel 6 (`0xB5`) → inputs
7/8, and that is what the protocol chart specifies. Changing the MIDI channel would
have been inventing a new mapping, which the brief forbids.

**The defect was identity ambiguity, not addressing.** Nothing in the code said
"strip 6 is the 7/8 pair", so a UI binding "fader 6 → `ch6`" would silently control
the wrong pair.

### 5.2 Correction applied

1. **Explicit address data.** `LogicalChannel.midi_channel` now declares the MIDI
   channel per strip; `midi_channel=1..7`.
2. **No more index arithmetic.** `command_boundary._build_phase_c_allowlist()` reads
   `LOGICAL_CHANNELS[ch].midi_channel` instead of using the loop index `ch`
   directly. The binding lives in exactly one place.
3. **Identity assertion.** `_validate_allowlist()` runs at import and fails if any
   parameter's ID implies a different MIDI channel than the entry declares.
4. **Reverse index + resolver.** `LOGICAL_CHANNEL_BY_MIDI_CHANNEL` and
   `logical_channel_for_connector()`.
5. **Engine API.** `Flow8ParameterEngine.channel_for_physical_input("IN_7L") → ch6`.
6. **Documented** in the `parameter_engine` module docstring as a strip/input table.

Net effect: no MIDI channel changed; the mapping is now explicit, asserted, and
resolvable by physical input name.

### 5.3 Regression coverage

`tests/test_channel_addressing.py` pins:
- every strip declares its own MIDI channel (1–7)
- strip 6 is the 7/8 pair and does **not** own `IN_6R`
- connector→strip resolution for all 9 connectors
- status byte per strip, including literal `0x4007B4` / `0x4007B5` / `0x4007B6`
- `ch6.fader` reaching channel 6 through the full engine
- `ch5` and `ch6` producing distinct messages

### 5.4 Stereo balance vs pan (finding F-03)

`Flow8ChannelStrip.set_balance()` was added. It shares the `chN.pan` address (the
hardware carries both on CC 10) but **rejects mono strips**, so a balance control
can never be silently applied as a pan law. State records for strips 5/6/7 now
label the parameter `"balance"` instead of `"pan"`.

---

## 6. Compressor capability conflict (section 5)

### 6.1 Evidence review

| Source | Claim |
|---|---|
| `FLOW8_HARDWARE_DOMAIN_MODEL.md` §3.1 | Compressor on all input strips (incl. 5/6, 7/8) |
| `FLOW8_SPECIFICATION_GAP_ANALYSIS.md` §2.2 | "Present on every input channel" |
| `FLOW8_USB_MIDI_PROTOCOL.md` §6 | CC 11 verified on Ch 1–4 only |
| `flow8/domain_model.py` | `has_compressor=True` for 5/6 |
| `flow8/parameter_engine.py` | Rejected channels > 4 |

The hardware capability and the control address are two different questions, and
they have different answers. No support was invented.

### 6.2 Resolution

`LogicalChannel` gained `compressor_control_verified`:

- Channels 1–4: `True` (address verified per chart)
- Channels 5/6: `False` (capability asserted, address **UNKNOWN**)
- Channel 7: `has_compressor=False` (no stage exists)

`set_compressor()` now distinguishes the cases with different messages:

```
ch7 -> "does not have a 1-knob compressor stage"
ch5 -> "capability is hardware-specified but its MIDI control address is UNKNOWN.
        No command is dispatched."
```

`Flow8StateStore` registers `ch5.compressor` / `ch6.compressor` with
`VerificationLevel.UNKNOWN` and `SyncStatus.UNKNOWN`, so the gap is visible rather
than silently absent. Neither is in the command allowlist.

---

## 7. Allowlist validation (section 6)

`_validate_allowlist()` runs at import time and rejects a malformed allowlist
before any command can be dispatched. It enforces, per entry:

- channel scope: `1 <= channel <= 16`
- CC scope: `0 <= cc <= 127`
- bounds: `0 <= min <= max <= 127`
- parameter identity: param ID's implied channel == declared channel
- uniqueness: no two parameters may share a `(channel, cc)` pair

Runtime bounds are enforced in `execute_command`: below-minimum and
above-maximum are rejected before `send_cc` is reached.

### 7.1 Latent bug fixed while implementing this

The allowlist declared `"min": 0, "max": 1` for mute and phantom. Enforcing the
declared bounds would have rejected `mute ON` (raw `127`) and broken every mute and
phantom command. Boolean entries now declare raw bounds `0..127` plus
`"boolean": True`, and boolean parameters accept only `True`/`False`/`0`/`1`
(`execute_command("ch1.mute", 64)` is rejected). This is why the bounds were
previously unenforced — enforcement would have broken them.

---

## 8. Bus layer regression tests (section 7)

`tests/test_bus_mappings.py` — 15 tests, all with `winmm` mocked, no hardware:

- bus fader channel/CC/value for Main (8), Mon 1 (9), Mon 2 (10), FX 1 (11), FX 2 (12)
- literal status bytes `0x6407B7`, `0x6407B8`, `0x6407B9`, `0x6407BA`, `0x6407BB`
- value endpoints `0` and `127`
- Main balance on CC 10 / channel 8, rejected on every other bus
- 11 invalid addresses rejected **and** asserted to transmit nothing
- CC collision protection:
  - CC 14 = Mon 1 send on ch 1 (`0x2D0EB0`) vs GEQ 500 Hz on ch 8 (`0x2D0EB7`)
  - CC 8 = preamp gain on ch 1 vs bus limiter on ch 8
  - CC 11 = compressor on ch 1 (`0x320BB0`) vs GEQ 62.5 Hz on ch 8 (`0x320BB7`)
  - bus GEQ/limiter are unreachable through the boundary even though the
    transport gate permits the address

---

## 9. Documentation corrections (section 8)

| Document | Correction |
|---|---|
| `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` | Level definitions rewritten (adds `API_ACKNOWLEDGED`); 4 parameters re-graded; all "Live Hardware Loopback" evidence claims removed; BLE/SysEx claim replaced with `UNKNOWN` |
| `FLOW8_USB_MIDI_PROTOCOL.md` | Hi-Z removed from Ch 3/4; CC 8/9/11 exception column corrected to "Channels 1–4 only"; SysEx row reclassified; provenance caveat added |
| `FLOW8_SPECIFICATION_GAP_ANALYSIS.md` | Bulk memory transfer no longer asserted as JSON over a specific transport |
| `FLOW8_HARDWARE_DOMAIN_MODEL.md` | "Custom / BLE-MIDI" label corrected; compressor scope reconciled with UNKNOWN address |
| `FLOW8_PARAMETER_CATALOG.md` | Compressor restriction matrix corrected for 5/6, 7/8, USB/BT |
| `FLOW8_PHASE_C_IMPLEMENTATION.md` | Parameter count corrected 83 → 97; errata note |
| `FLOW8_PHASE_C_TEST_RESULTS.md` | Latency claim corrected; hardware-gating note; errata |

Nothing was deleted. `FLOW8_PHASE_B1_AUDIT.md` and `FLOW8_PHASE_C1_AUDIT.md`
remain untouched as historical records.

---

## 10. Backward compatibility

| Surface | Status |
|---|---|
| `CommandLogEntry.success`, `.raw_midi_sent`, `.dispatched_to_hardware`, `.latency_us` | Retained, semantics tightened |
| All new log fields | Defaulted, additive |
| `execute_command()` signature | Unchanged |
| `send_cc()` | Was `-> None`, now returns the packed message. Callers ignoring the return are unaffected |
| Allowlist parameter IDs | Unchanged (97 entries, no renames) |
| `VerificationLevel` | Additive only (`API_ACKNOWLEDGED`); no level removed |
| `LogicalChannel` / `ParameterState` | Additive fields with defaults |

---

## 11. Deliberately not done

- No BLE, SysEx, DSP, audio, UI or mobile implementation.
- No new MIDI mappings invented; no MIDI channel changed.
- No `HARDWARE_TESTED` awarded to anything.
- No automatic hardware restore (forbidden, and unsafe without a known prior state).
- No Phase D work.
