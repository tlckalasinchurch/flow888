# Phase C.2 — Safety Report

**Target:** Behringer FLOW 8 Digital Mixer
**Date:** 2026-11-09
**Scope:** Physical hardware safety of the automated test suite, and the evidence
discipline applied to every dispatch claim.

---

## 1. Summary

| Risk | Before C.2 | After C.2 |
|---|---|---|
| Default `unittest discover` transmitted MIDI to the mixer | **Yes** | **No** |
| Default suite could leave Main / Ch 1 silent | **Yes** (observed) | **No** |
| Opt-in required for hardware access | No | Yes, two tiers |
| Automatic restore using guessed values | None existed | Still none, and now explicitly forbidden |
| Dispatch success confusable with delivery | Yes | No — five distinct statuses |
| Failed dispatch recorded as commanded | Yes | No — state untouched |

---

## 2. Incident recorded by the C.1 audit

`FLOW8_PHASE_C1_AUDIT.md` §0.3 recorded that running the test suite transmitted
real CC to the connected mixer, because `tests/test_hardware_midi_out.py` was
discovered automatically, was not mocked, and had no gate. The final device state
was **Main fader 0 and Ch 1 fader 0 (silent)**, with no restore logic.

That is the defect this report closes.

---

## 3. The gate

### 3.1 Why two tiers

"Open an endpoint" and "change the mix" are different risks and deserve different
consent:

| Tier | Environment | Transmits MIDI? | Can change mixer state? |
|---|---|---|---|
| 0 (default) | — | No | No |
| 1 | `FLOW8_HW_TESTS=1` | No | No |
| 2 | `FLOW8_HW_TESTS=1` + `FLOW8_HW_TESTS_MUTATE=1` | Yes (CC) | Yes |

Tier 1 covers enumeration and open/close/reconnect/context-manager plus MIDI-In
start/stop. It is useful for driver troubleshooting and is completely
non-destructive.

### 3.2 Why class-level skipping matters

`@unittest.skipUnless(...)` is applied to the **class**, not to individual test
methods. Skipped classes never instantiate `TestCase`, so `setUp()` never runs,
`Flow8MidiOut()` is never constructed, and `midiOutOpen` / `midiInOpen` are never
called. There is no window in which the default suite touches a device.

### 3.3 Default run evidence

```
python -m unittest discover -s tests -v
  -> Ran 104 tests
  -> OK (skipped=5)
  -> exit 0
```

The five skips are exactly the hardware classes, and every skip message states:

> Physical hardware tests are disabled by default (nothing was transmitted).

---

## 4. What tier 2 refuses to do

| Prohibited action | Rationale |
|---|---|
| Write any fader (Main, Monitor, channel) | A wrong fader value can silence a live PA. Unrecoverable from software without knowing the prior value. |
| Enable +48 V phantom power | Energising phantom into an unknown load is a hardware risk. No readback exists. |
| Restore previous values automatically | The prior state is unknown. A guessed restore is worse than leaving visible state — and the phase brief forbids it. |
| Write bus limiter / GEQ / FX engine | Not implemented; addresses unverified. |

Every tier-2 operation lands on a **neutral** position:

| Operation | Value | Neutral because |
|---|---|---|
| `ch1.pan` | `0.0 %` → raw 64 | centre |
| `ch1.eq_low` | `0.0 dB` → raw 64 | flat |
| `ch1.mute` | `True` then `False` | ends unmuted |

The mixer therefore ends in a sane state regardless of where it started, without
any assumption about its starting state.

---

## 5. Evidence discipline

### 5.1 Four things that are not the same thing

| Level | Question | Represented by | Available today |
|---|---|---|---|
| 1 | Did the driver accept the message? | `driver_dispatched`, `dispatch_status=DRIVER_DISPATCHED` | **Yes** |
| 2 | Did bytes leave the host on USB? | nothing — needs a USB trace | No |
| 3 | Did the mixer change? | `hardware_applied` | **Never `True`** |
| 4 | Did the audio change? | nothing — needs capture | No |

### 5.2 `hardware_applied` is structurally unconfirmable

The field exists and defaults to `None` on every path: offline, dispatched, and
failed. No code sets it to `True`. This is deliberate — there is no confirmation
channel, so any `True` would be fabrication. When an inbound path is built, this is
the field that gets written.

### 5.3 Verification levels

`HARDWARE_TESTED` now has **zero** holders in the state store, because no physical
observation was ever retained. A regression test enforces that:

```python
for param_id, record in store.get_all_parameters().items():
    assert record["verification_level"] != VerificationLevel.HARDWARE_TESTED.value
```

The four previously mis-graded parameters (`main.fader`, `ch1.fader`, `ch1.mute`,
`ch1.pan`) are `API_ACKNOWLEDGED`, which is exactly what a WinMM return code
proves.

---

## 6. Transaction safety

### 6.1 Failure cannot masquerade as success

| Path | `state` committed? | `raw_midi_sent` | `dispatch_status` |
|---|---|---|---|
| Rejected (not in allowlist) | No | `None` | `REJECTED` |
| Invalid value / bad type | No | `None` | `VALIDATION_FAILED` |
| Offline | Yes (pending) | `None` | `ACCEPTED_OFFLINE` |
| Driver dispatched | Yes | value | `DRIVER_DISPATCHED` |
| Dispatch failed | **No** | `None` | `DISPATCH_FAILED` |

The failed-dispatch row is the key fix: previously state was committed and a raw
value recorded for a message the mixer never received.

### 6.2 Troubleshooting is preserved

On failure the log entry still carries `raw_midi_prepared` (the computed value) and
`error_message` (the verbatim driver error), plus the exception text. Losing the
value would have made failures undiagnosable, which is why the corrected design
keeps both fields.

---

## 7. Residual risks

| Risk | Severity | Mitigation / status |
|---|---|---|
| Tier 2 still changes mixer state if an operator enables it | Medium | Documented in the class docstring; neutral targets only; no fader/phantom writes; no restore attempted |
| `driver_dispatched` misread as delivery by future code | Medium | Renamed semantics documented in `command_boundary` and `midi_out` docstrings; `hardware_applied` kept separate and `None` |
| Only 5 of 97 pairs historically byte-tested | Low | Bus layer now byte-tested; remaining gaps recorded as open items in the test-results report |
| No inbound observation channel | Medium | Blocks any `HARDWARE_TESTED` claim; documented, not worked around |
| Compressor on Ch 5/6 | Low | Classified `UNKNOWN`; command refused with an explicit message |

---

## 8. Compliance with phase restrictions

| Restriction | Status |
|---|---|
| FLOW 8 only | Compliant |
| No Phase D | Compliant |
| No Audio Engine / DSP / UI / Mobile / AI | Compliant |
| No undocumented MIDI commands | Compliant — no mappings invented, no channels changed |
| No automatic hardware restoration | Compliant — none added |
| No destructive hardware tests | Compliant — faders and phantom excluded even in tier 2 |
| No deletion of existing files | Compliant |
| Preserve unrelated functionality | Compliant — API additions are defaulted/backward compatible |
| Do not install pytest / change framework | Compliant — `unittest` retained |
