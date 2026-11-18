# S1.2 Regression Migration Plan

Date: 2026-11-18. Preparation only: **no test was changed, no source changed, no MIDI sent.** Baseline re-run this session (offline, no hardware): `python -m unittest discover -s tests` → **366 run, OK, skipped=5, expected failures=3** (358 passed). Design: `S1_2_IMPLEMENTATION_PLAN.md`; new tests: `S1_2_SAFETY_TEST_SPEC.md`.

## 1. Principle

Existing tests encode behaviour that the owner has now ruled unsafe (gain dispatch, unauthorised phantom ON, low-level acceptance of unauthorised pairs). **They are migrated, never deleted, skipped or turned into expected failures.** Each keeps its name and its stated intent; only the setup or the expected result changes where the behaviour itself was the thing being removed. The reason for every change is recorded below so a reviewer can verify no protection was lost.

## 2. Inventory: tests that depend on gain, phantom or the 37 pairs

Search method: grep of `tests/` for `set_gain`, `.gain`, `set_phantom`, `.phantom`, `send_cc(`, `PhantomPower`, `AnalogGainSafetyGate`, then reading each hit's test body.

### 2.1 Tests that WILL change behaviour (15 tests, migration required)

| # | Test (file::class::method) | Lines | Reliance today | After the change | Migration | Intent kept by |
|---|---|---|---|---|---|---|
| 1 | `tests/test_parameter_engine.py::TestParameterEngine::test_preamp_gain_channel_restrictions` | ~64–74 | `set_gain(20, raw)` succeeds on ch 1–4 | Rejected by the boundary | Ch 1–4: `assertRaises(Flow8CommandRejectedError)` plus REJECTED log and zero driver calls; ch 5–7 keep `Flow8ValidationError` | Channel restriction (5–7 have no gain stage) still asserted; the new assertion states the owner's block |
| 2 | same file `::test_unit_conversions` | 215–242 (gain at 219–221) | `set_gain(-20 dB)` → raw 0, `set_gain(60 dB)` → raw 127 through the engine | Rejected | Assert the conversion with the pure functions `parameter_mapping.gain_db_to_midi(-20.0) == 0`, `(60.0) == 127`; add the engine rejection; low-cut, EQ, send, compressor conversions untouched | The mapping arithmetic is still tested (these are unverified approximations, C-12) |
| 3 | same file `::test_phantom_power_channel_restrictions` | 99–112 | `set_phantom(True)` succeeds on ch 1 | ON refused without authorization | ON: via `authorize_phantom_on(engine_adapter, 1)` (real gate); OFF on ch 2 unchanged; ch 3–7 `Flow8ValidationError` unchanged | Channel scope and prepared values 127/0 still asserted |
| 4 | `tests/test_bus_mappings.py::TestBusCcCollisionProtection::test_cc8_gain_versus_bus_limiter` | 159–168 | `set_gain(-20 dB)` dispatches 0x0008B0; `send_cc(8, 8, 64)` accepted (0x4008B7) | Both refused (gain blocked; bus limiter pair blocked by G-04) | Keep the purpose "CC 8 means different things on ch 1 and ch 8": assert both are refused with different rule ids; assert the reference encoder values `packed(1, 8, 0) == 0x0008B0` and `packed(8, 8, 64) == 0x4008B7` still differ; driver not called; boundary rejection of `main.limiter` kept | Collision awareness preserved |
| 5 | same class `::test_cc11_compressor_versus_main_geq` | 170–175 | `send_cc(8, 11, 50)` accepted | Refused (GEQ pair blocked) | Keep the compressor half (ch 1 CC 11 dispatches 0x320BB0); replace the GEQ half with: refused, driver count unchanged, `packed(8, 11, 50) == 0x320BB7` compared with `packed(1, 11, 50)` | same |
| 6 | same class `::test_same_cc_on_different_channels_encodes_differently` | 135–140 | `send_cc(8, 14, 45)` accepted | Refused | ch 1 CC 14 dispatches; ch 8 CC 14 refused; the encoder assertion `assertNotEqual(packed(1,14,45), packed(8,14,45))` kept | same |
| 7 | same class `::test_literal_mon_send_vs_geq_500` | 142–147 | `send_cc(8, 14, 45)` accepted (0x2D0EB7) | Refused | ch 1 half unchanged; ch 8 half: refused + literal `0x2D0EB7` compared with the reference encoder | same |
| 8 | `tests/test_preset_service.py::TestPresetServiceIntegration::test_apply_channel_preset_on_mic_channel` | 11–35 (gain at 15) | Baseline gain set with `service.set_gain(1, 24.0, "dB")`; asserts preset leaves gain unchanged | `set_gain` refused | Baseline through `state_store.set_commanded_value("ch1.gain", 24, EventSource.LOCAL_HOST, raw_midi_value=24)` (sends nothing); add: preset emits no CC 8 | "Preset preserves gain" strengthened |
| 9 | same file `::test_preset_undo_and_redo` | 59–91 (gain at 69) | same baseline | same | same pattern | same |
| 10 | `tests/test_service_ledger_scenes.py::PhantomIsolationTests::test_set_phantom_is_never_recorded` | 138–143 | `set_phantom(1, True)`, `(1, False)`, `(2, True)` direct | ON refused | ON through `authorize_phantom_on`; OFF direct; ledger assertions unchanged | Ledger never records phantom |
| 11 | same class `::test_undo_and_redo_never_touch_phantom` | 145–159 | `set_phantom(1, True)` direct, then undo/redo with a spy | ON refused | ON via helper; the rest unchanged | undo/redo isolation |
| 12 | same class `::test_scenes_never_store_or_recall_phantom` | 167–181 | direct ON | ON refused | ON via helper; rest unchanged | scene isolation |
| 13 | `tests/test_scene_ui.py::PhantomSafetyTests::test_scenes_never_touch_or_display_phantom` | 199–219 | direct `set_phantom(1, True)` | refused | helper | same |
| 14 | same class `::test_recall_leaves_the_strip_phantom_button_alone` | 221–229 | direct ON | refused | helper | same |
| 15 | `tests/test_mixer_history.py::UndoRedoBehaviourTests::test_undo_never_touches_phantom` | 177–188 | direct ON | refused | helper | same |

Counting rule for the phantom tests: they count **log entries ending in `.phantom`**. A refused ON would add a REJECTED entry; the helper path adds exactly one accepted entry, so the existing "before/after" counts stay valid.

### 2.2 Tests that must keep passing unchanged (re-run only)

| File | Tests | Why unchanged |
|---|---|---|
| `tests/test_safety_dialogs.py` | all `PhantomPowerSafetyGateTests`, `PhantomPowerDialogUITests`, `AnalogGainSafetyGateTests` | They use mock services; the ambient grant wraps the call without changing `set_phantom(1, True)`; gate classes are re-exported (identity). The test that patches `AnalogGainSafetyGate.is_verified_mapping_available` to True (line 256) is a test-side patch, not a production bypass, and still raises `NotImplementedError` |
| `tests/test_channel_detail.py` | the phantom UI flows (lines about 175–390), gain preview tests (about 477–500), `BoundaryTests` | The dialog path goes through the real gate, so the real service accepts the confirmed ON; `assert_called_once_with(1, True)` still holds |
| `tests/test_command_boundary_integrity.py` | `test_phantom_scope` (133–140), `test_rejection_is_logged_without_dispatch` (ch 5 gain, 228) | Allowlist is not extended; ch 3–7 phantom and ch 5 gain stay rejected |
| `tests/test_domain_and_state.py` | line 174 (ch 5 gain rejected) | unchanged |
| `tests/test_midi_out.py` | lines 54–63 (`send_cc` refuses (13,7), (5,8), (7,11), (3,12)) | Still refused |
| `tests/test_command_ledger.py` | line 19 (phantom push refused) | unchanged; new gain case added in the new module |
| `tests/test_bus_mappings.py` | all other tests (faders, balance, allowlist, transport gate (118), `test_collision_is_resolved_by_the_boundary_too`) | no pair from the 37 or gain is used |
| `tests/test_channel_addressing.py` | `send_cc(idx, 7, 64)` | fader pairs stay allowed |
| `tests/test_hardware_midi_out.py` | opt-in, skipped by default | uses ch 1 pan, EQ low, mute only; no gain, phantom, or blocked pair |
| `tests/test_stage1_state_sync.py`, `tests/test_real_world_audit_defects.py` | Stage 1 tests | unaffected |

## 3. Migration helpers (test code only)

```text
tests/_safety_helpers.py
  authorize_phantom_on(target, channel)
      # target: Flow8Service, or an adapter exposing set_phantom(ch, enabled) over an engine
      token = PhantomPowerSafetyGate.issue_token(channel)
      assert PhantomPowerSafetyGate.confirm_and_dispatch(target, channel, token)
  record_driver_calls(out)  -> returns the MagicMock behind out._winmm.midiOutShortMsg
tests/_no_hardware.py
  patches Flow8MidiOut.open / Flow8MidiIn.open / winmm open lookups to raise
```

The helper uses the **real** gate, so migrated tests prove that the authorised path works, not that a bypass exists. There is no flag, environment variable or production hook behind it.

## 4. Expected red set during implementation (so surprises are visible)

After steps 3–4 and **before** step 5 (migration), exactly these tests are expected to fail, and no others: the 15 listed in §2.1. Any other failure pauses the work. After step 5 the red set must be empty. The new `test_s12_*` tests are red before their fix and green after, as listed in the test spec.

## 5. Strategy for each pattern

| Pattern | Used by | Rule |
|---|---|---|
| A. Authorised phantom ON | rows 3, 10–15 | helper; same assertions; no assertion removed |
| B. Gain baseline without sending | rows 8, 9 | `state_store.set_commanded_value`; assertion that no CC 8 was emitted added |
| C. Dispatch expected → refusal expected | rows 1, 2, 4 | the refusal asserts rule id, REJECTED status and zero driver calls |
| D. Low-level pair accepted → refused | rows 4–7 | keep the collision intent through the independent reference encoder `packed()`; assert refusal and zero driver calls |
| E. Pure arithmetic | row 2 | call `parameter_mapping` functions directly |

## 6. No silent deletion (verification)

1. Step 0 writes `docs/product/test_inventory_before.txt` (all 366 test ids, 5 of which are skipped by default) with its SHA-256.
2. After step 8: `tools/test_inventory.py` writes the new inventory and checks `before ⊆ after`. Differences are listed: additions only.
3. A scan of the `tests/` diff confirms that no `skip`, `skipIf`, `skipUnless`, `expectedFailure` or `@unittest.skip` line was added to an existing test, that no `def test_` line was removed or renamed, and that assertion counts of migrated tests are equal or higher (a simple count of `assert` calls per migrated test, before and after, reported in the final table).
4. The migrated tests keep their module, class and method names; the report lists each with before and after assertion counts.

## 7. Backward-compatibility checklist

| Item | Check |
|---|---|
| Public names `PhantomPowerSafetyGate`, `PhantomPowerConfirmationToken` import from `flow8.ui.safety_dialogs` | identity test P-11 |
| `Flow8Service.set_phantom(channel, enabled)` signature unchanged | inspect.signature test |
| `Flow8CommandBoundary.ACTIVE_ALLOWLIST` content unchanged (97 ids) | equality test against the frozen id list |
| `Flow8MidiOut.send_cc` error type for refused pairs stays `Flow8ValidationError` | existing tests at `test_midi_out.py` and `test_bus_mappings.py:118` |
| Command log fields and `DispatchStatus` values unchanged | existing boundary tests |
| `FLOW8-CyberNeon.spec` / `main.py` import | start the app offline in a test and import `main` without opening ports |

## 8. Rollback of the test changes

Step 0 copies every test file listed above into `docs/product/rollback_s1_2/<timestamp>/tests/` with SHA-256. If a migrated test cannot be fixed, the original file is restored from that copy after saving the current version into a new timestamped folder; nothing is deleted and no Git history operation is used. The new `test_s12_*` modules are additions and are simply left in place if the source change is rolled back (they would then be the red set, which documents the unresolved gap).

## Addendum after implementation (2026-11-18): two further migrated tests

Two existing tests outside the 15 listed in §2.1 also depended on the old behaviour and were migrated (names kept, assertions increased):

| Test | Reason | Change |
|---|---|---|
| `tests/test_channel_detail.py::BoundaryTests::test_inspector_only_reaches_the_phantom_setter_through_the_safety_gate` | It asserted that `flow8/ui/safety_dialogs.py` contains the only `set_phantom` call; the gate moved to `flow8/safety.py` (decision D3) | The UI dialog module must now reach no setter, and `flow8/safety.py` must contain exactly `set_phantom` |
| `tests/test_command_boundary_integrity.py::TestAllowlistBoundsEnforcement::test_every_entry_enforces_min_and_max` | It iterated every allowlist entry including gain and phantom | Gain: every value refused (REJECTED); phantom: OFF succeeds, ON refused without a grant, bad values still `Flow8ValidationError`; all other entries unchanged |

The expected red set before step 5 was therefore 17 tests, not 15. Assertion counts: 70 before, 85 after across the 17 migrated tests; no test was removed, skipped or marked expected failure.
