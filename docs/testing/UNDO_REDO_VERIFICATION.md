# Testing: Undo / Redo Engine Verification & Formal Guarantees

> **S1.1 EVIDENCE CORRECTION (2026-11-18) — historical document, the original text below is unchanged.** Statements in this document about hardware verification (line 35 "Physical Hardware Batch ... verified driver success, undone back to baseline" (driver success only; the mixer cannot be read back)) are re-graded under the evidence ladder of `docs/product/FLOW8_EVIDENCE_REGISTER.md`. No raw evidence of a physical effect or of mixer-originated MIDI was found for them. The strongest evidence found is Windows driver acceptance (`midiOutShortMsg` returned 0), which is not hardware verification, DSP confirmation or USB delivery (see `FLOW8_PHASE_C2_IMPLEMENTATION.md`). Read "VERIFIED", "HARDWARE_TESTED" and "passed on physical hardware" here as **PROTOCOL SUPPORTED, driver accepted, not hardware verified**. No inbound telemetry was ever received (evidence E07, E08, E17). Per-claim table: `docs/product/S1_1_HISTORICAL_EVIDENCE_CORRECTIONS.md`.

**Document ID:** `UNDO_REDO_VERIFICATION`  
**Subsystem:** `flow8.ledger.CommandLedger` & `flow8.service.Flow8Service`  
**Test Suite:** `tests/test_state_and_undo_audit.py`, `tests/test_service_ledger_scenes.py`  
**Date:** 2026-11-18  
**Status:** IMPLEMENTED, AUDITED & TESTED  

---

## 1. Core Engineering Principles

Prior implementations relied on dangerous fallbacks (e.g. falling back to 0 dB flat EQ or 0% comp when the previous state was unknown). In a live audio environment, restoring an unverified assumption can blast feedback through stage monitors or mute critical channels.

The upgraded Undo / Redo engine enforces three strict guarantees:
1. **Exact-Value Restoration:** Undo always restores the exact prior value ($V_{\text{previous}}$) commanded by the user or confirmed by hardware telemetry.
2. **Zero Fabrication:** If a parameter has never been commanded or observed (`provenance == UNSYNCED`), its previous state is unknown. The operation is marked **strictly non-undoable**, and no unverified record is added to the ledger.
3. **Atomic Rollback & Ordering:** Multi-parameter transactions execute undo in **reverse causal order** ($R_n \rightarrow R_1$) and redo in **forward causal order** ($R_1 \rightarrow R_n$). If a command fails during replay, all previously replayed commands are compensated (rolled back), returning the mixer to its pre-operation state.

---

## 2. Test Verification Matrix

| Test Case | Scenario / Invariant | Expected Behavior | Observed Result | Test File |
|---|---|---|---|---|
| **Exact Value Undo** | Initial EQ = -3 dB (raw 51), Apply Preset = -1 dB (raw 60). | Undo restores raw 51 (-3 dB), NEVER neutral flat (raw 64). | **PASSED** (Restored 51) | `test_state_and_undo_audit.py` |
| **Exact Value Redo** | Following Undo, Redo is invoked. | Redo re-dispatches raw 60 (-1 dB). | **PASSED** (Re-applied 60) | `test_state_and_undo_audit.py` |
| **Unknown Prior State** | Low cut adjusted on previously untouched channel (`UNSYNCED`). | Marked non-undoable; ledger rejects record. No fabricated guess. | **PASSED** (`can_undo == False`) | `test_state_and_undo_audit.py` |
| **Subsequent Edit Undoable** | Channel touched once, then adjusted again. | 2nd adjustment has known prior value and is undoable. | **PASSED** (`can_undo == True`) | `test_state_and_undo_audit.py` |
| **Reverse Undo Ordering** | Batch commands: Fader $\rightarrow$ Pan $\rightarrow$ Mute. | Undo applies: Mute $\rightarrow$ Pan $\rightarrow$ Fader. | **PASSED** (Reverse Order Verified) | `test_state_and_undo_audit.py` |
| **Forward Redo Ordering** | Following batch undo, Redo is invoked. | Redo applies: Fader $\rightarrow$ Pan $\rightarrow$ Mute. | **PASSED** (Forward Order Verified) | `test_state_and_undo_audit.py` |
| **Partial Failure Rollback** | Command 3 of 3 fails during undo (`Flow8CommandError`). | Commands 1 & 2 compensated back to `new_value`; transaction remains on undo stack. | **PASSED** (Rollback Verified) | `test_state_and_undo_audit.py` |
| **Disconnect Invalidation** | Mixer disconnects or reconnects with active ledger history. | Redo stack purged; uncommitted batches canceled; state reset to `UNSYNCED`. | **PASSED** (Reconciled) | `test_state_and_undo_audit.py` |
| **Preset Level Preservation** | Curated acoustic preset applied to Channel 1. | Fader, Pan, Gain untouched. DSP parameters committed as single atomic batch. | **PASSED** (Levels Preserved) | `test_preset_service.py` |
| **Physical Hardware Batch** | Preset dispatched to connected FLOW 8 hardware. | 6 parameters sent over WinMM, verified driver success, undone back to baseline. | **PASSED** (5/5 Mutating HW Tests) | `test_hardware_midi_out.py` |

---

## 3. Mathematical & Algorithmic Specifications

### Transaction Replay with Compensating Rollback

```
Algorithm Undo(Transaction T):
    Let group = [R_n, R_{n-1}, ..., R_1] (reverse chronological order)
    Let applied = []
    For each record R in group:
        Try:
            Apply(R.parameter_type, R.channel_index, R.previous_value)
            applied.append(R)
        Catch Error E:
            // Rollback already-applied records to preserve mixer consistency
            For each record C in reversed(applied):
                Try:
                    Apply(C.parameter_type, C.channel_index, C.new_value)
                Catch RollbackError:
                    Raise CriticalStateError("Compensation failed", E)
            Raise E
    Pop group from UndoStack
    Push group to RedoStack
    Return group[0]
```
