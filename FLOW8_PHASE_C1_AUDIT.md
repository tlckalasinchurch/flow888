# FLOW 8 Phase C.1 — Independent Parameter & Protocol Audit

**Target:** Behringer FLOW 8 Digital Mixer (USB `VID_1397&PID_050C`)
**Audit type:** Read-only, independent verification of Phase C Parameter Engine and its hardware/protocol claims
**Date:** 2026-11-09
**Auditor role:** Senior Digital Mixer Protocol Engineer / Independent Audio Systems Auditor
**Audit scope:** The 11 source/test files and 7 documents listed in the audit brief. No other files were read.

---

## 0. Method, Evidence Hierarchy, and a Mandatory Disclosure

### 0.1 What this audit did

1. Read the 11 in-scope source/test files and the 7 in-scope documents in full.
2. Cross-checked every implemented `(MIDI channel, CC, value-range, capability-gate)` tuple against the only protocol evidence present in scope.
3. Traced the dispatch path (`ParameterEngine → CommandBoundary → Flow8MidiOut → winmm`) for offline, disconnected, rejected, conversion-failed, and send-failed cases.
4. Ran the focused Phase C tests and the full regression suite, and separately enumerated MIDI endpoints and the live allowlist/state inventory with read-only calls.
5. Did **not** edit source, add features, write firmware, delete files, or start Phase D.

### 0.2 Evidence grades used throughout

The audit grades evidence, not intent. A mapping is only accepted at the grade its evidence supports.

| Grade | Meaning | Present in scope? |
|---|---|---|
| **E0** | External official documentation, citable artifact (URL/PDF/revision) | **No** |
| **E1** | Project-internal protocol chart (`FLOW8_USB_MIDI_PROTOCOL.md`), uncited | **Yes — the sole source for every mapping** |
| **E2** | Code-internal self-consistency (allowlist ↔ engine ↔ state store ↔ transport gate) | Yes |
| **E3** | WinMM API acknowledgement (`midiOutShortMsg` returned `MMSYSERR_NOERROR`) | Yes |
| **E4** | Inbound message *received from the mixer* confirming the parameter identity | **No** |
| **E5** | Recorded operator observation of mixer UI or audible change | **No (asserted, not retained)** |

The decisive fact for this audit: **every one of the 97 parameter mappings traces to a single uncited project document (E1). No E0 artifact exists in scope, no E4 observation was ever captured, and no E5 observation is retained in any in-scope document.** Code tests prove E2 and E3 only.

### 0.3 Mandatory disclosure — the audit transmitted MIDI to the device

The brief required both *"Do not send new MIDI commands"* and *"Run the focused Phase C tests and full regression suite."* These conflict: `tests/test_hardware_midi_out.py` is **not** mock-based, and the audit enumeration confirmed a live endpoint (`FLOW 8 MIDI OUT`, device index 1) is present. The device was therefore **not** skipped, and running the suite emitted real Control Change messages.

Executed as instructed; disclosed here rather than hidden. Consequence to be aware of:

- `test_hardware_parameter_dispatches` (`tests/test_hardware_midi_out.py:48-86`) left **Main fader at raw 0 (`-∞`)**, **Ch 1 fader at raw 0**, Ch 1 unmuted, Ch 1 pan centred.
- `test_hardware_parameter_engine_dispatch` (`:88-119`) again set **Main fader to 0**.
- Net device state after the run: **Main and Ch 1 faders at 0 (silent)**. No restore-to-prior-value logic exists in the test.

**Finding F-14 (High):** the hardware test module mutates physical device state, is non-idempotent, does not capture or restore prior values, and runs automatically under `unittest discover`. Any regression run on a connected mixer silences Main and Ch 1. Recommended action: gate hardware tests behind an explicit env flag (e.g. `FLOW8_HW_TESTS=1`), snapshot-and-restore, and default to skip. See §11.

---

## 1. Executive Verdict

### **CONDITIONAL PASS**

**What genuinely passes:**

- The software architecture is sound and the layering is real. Every in-scope write path funnels through `Flow8CommandBoundary.execute_command` (`flow8/command_boundary.py:106`), and the transport gate in `Flow8MidiOut.send_cc` (`flow8/midi_out.py:197-237`) independently re-validates channel/CC scope. No bypass path exists in scope.
- MIDI **byte encoding is correct and tested**: `status_byte = 0xB0 | ((channel - 1) & 0x0F)` (`flow8/midi_out.py:244`) produces `0xB0…0xBF` for channels 1–16, verified against exact DWORDs in `tests/test_midi_out.py:65-95` and `tests/test_parameter_engine.py:171-192`.
- Hardware capability gating is consistent across three independent layers (engine guard → allowlist membership → transport gate) for phantom (Ch 1–2), preamp gain / low cut / compressor (Ch 1–4), and bus balance (Main only).
- **No parameter mapping is proven incorrect.** Nothing in scope contradicts a mapping at the byte level.
- Dispatch never mutates verification levels. There is no code path that auto-upgrades a parameter to `HARDWARE_TESTED`; `VerificationLevel` is assigned only in `Flow8StateStore._initialize_baseline_parameters` (`flow8/state_model.py:88-315`). This is exactly right and is the single strongest design decision in the phase.
- All tests pass, 50/50, zero skips.

**Why it is not a PASS:**

1. **The evidence base is one uncited internal document.** `FLOW8_USB_MIDI_PROTOCOL.md` self-declares "VERIFIED (Official Behringer FLOW 8 MIDI Implementation Chart)" but provides no citation, no revision, no URL, and no artifact. No E0 evidence exists in scope. Therefore every `PROTOCOL_VERIFIED` classification in `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` is, strictly, **UNVERIFIED — internally asserted only**.
2. **Four parameters are over-graded `HARDWARE_TESTED`.** `HARDWARE_TESTED` is claimed for `main.fader`, `ch1.fader`, `ch1.mute`, `ch1.pan` (`flow8/state_model.py:102,115,128,141`) on the strength of WinMM return codes plus an unretained operator claim. The matrix's own definition of `HARDWARE_TESTED` requires "confirmed via physical endpoint reception"; `FLOW8_HARDWARE_DOMAIN_MODEL.md:254` states inbound telemetry was never observed. The grade is not supported by retained evidence.
3. **The latency claim is a category error.** `<500 µs` is host-side function execution time (`flow8/command_boundary.py:228`), not USB transport, not mixer response, not audio round-trip. No test asserts it.
4. **The BLE/SysEx claim is unsupported and self-contradictory** across four in-scope documents, and nothing is implemented.
5. **The state/dispatch semantics are misleading in three specific, fixable ways** (`success=True` offline; `raw_midi_sent` populated when nothing was sent; state store updated after a failed send).

None of these require re-architecting Phase C. All are correctable by documentation downgrade plus a small, well-scoped set of code fixes (§11). Hence **CONDITIONAL PASS**, not FAIL.

**Severity roll-up:** 0 Critical · 4 High · 8 Medium · 6 Low.

---

## 2. Parameter-by-Parameter Verification Matrix

`Verdict` is what the *in-scope evidence* supports, not what the code claims.

Legend — **PV\***: protocol-verified against a project-internal uncited chart only (E1); **UNV**: unverified; **UNK**: unknown.

### 2.1 Input strip parameters (MIDI Channels 1–7)

| # | Parameter | Param ID | Ch | CC | Raw range | Engineering conversion | Direction | Capability gate | Evidence | Verdict | Severity if wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Preamp Gain** | `ch{1-4}.gain` | 1–4 | 8 | 0–127 | `-20…+60 dB`, linear over 80 dB (`parameter_mapping.py:146-152`) | ascending assumed | engine `parameter_engine.py:79`; allowlist `command_boundary.py:71-72`; gate `midi_out.py:214-220` | E1 only. Chart §2 note contradicts the Ch 1–4 restriction (see M-01) | **UNV** (range & linearity are approximations; the code itself labels them UNVERIFIED) | High |
| 2 | **Low Cut** | `ch{1-4}.low_cut` | 1–4 | 9 | 0–127 | `20…600 Hz`, **linear in Hz** (`:172-178`) | ascending assumed | `parameter_engine.py:91`; `command_boundary.py:71,73`; `midi_out.py:214-220` | E1 only | **UNV** — linear-in-Hz over 20–600 Hz is 4.57 Hz/step, implausible for a real HPF; a log/iso mapping is far more likely | High |
| 3 | **PEQ 4-band** | `ch{1-7}.eq_{low,low_mid,hi_mid,hi}` | 1–7 | 1, 2, 3, 4 | 0–127 | `-15…+15 dB`, 64 = 0 dB (`:199-205`) | ascending | allowlist `command_boundary.py:61-64` for all 7; no capability gate (all channels) | E1 only | **PV\*** (implausible otherwise; classic 64-centre curve) | Medium |
| 4 | **Dynamics / Compressor** | `ch{1-4}.compressor` | 1–4 | 11 | 0–127 (0–100 used) | `0…100 %`, 101–127 clamp (`:234-247`) | ascending assumed | `parameter_engine.py:136`; `command_boundary.py:71,74` | E1 only, **and the chart contradicts itself** (§2: "not on Ch 7" ⇒ 1–6; §6: "Ch 1–4") | **UNV** for Ch 1–4; **UNK** for Ch 5/6 (see M-02) | High |
| 5 | **Phantom +48V** | `ch{1,2}.phantom` | 1–2 | 12 | 0 / 127 | `0=OFF, 127=ON` (`:25-27`) | boolean | `parameter_engine.py:175`; `command_boundary.py:77-78`; `midi_out.py:214-220` | E1 only | **PV\*** | Medium |
| 6 | **Monitor 1 Send** | `ch{1-7}.send_mon1` | 1–7 | 14 | 0–127 | dB via fader curve | ascending | `parameter_engine.py:159`; `command_boundary.py:65` | E1 only | **PV\*** | Medium |
| 7 | **Monitor 2 Send** | `ch{1-7}.send_mon2` | 1–7 | 15 | 0–127 | dB via fader curve | ascending | `:66` | E1 only | **PV\*** | Medium |
| 8 | **FX 1 Send** | `ch{1-7}.send_fx1` | 1–7 | 16 | 0–127 | dB via fader curve | ascending | `:67` | E1 only | **PV\*** | Medium |
| 9 | **FX 2 Send** | `ch{1-7}.send_fx2` | 1–7 | 17 | 0–127 | dB via fader curve | ascending | `:68` | E1 only | **PV\*** | Medium |
| 10 | **Channel Fader** | `ch{1-7}.fader` | 1–7 | 7 | 0–127 | 0 = OFF; 1–101 → -70…0 dB; 101–127 → 0…+10 dB; **unity = 101 assumed** (`:87`) | ascending | `command_boundary.py:58` | E1 for CC; **the 101 unity point is an assumption with no source at all** | **UNV** for the dB curve; PV\* for raw 0–127 | High |
| 11 | **Mute** | `ch{1-7}.mute` | 1–7 | 5 | 0 / 127 | `0=OFF, 127=ON`; decode treats 1–127 as muted (`:30-37`) | boolean | `command_boundary.py:59` | E1 | **PV\*** | Low |
| 12 | **Pan / Balance** | `ch{1-7}.pan` | 1–7 | 10 | 0–127 | `0 = -100 %, 64 = 0 %, 127 = +100 %` (`:44-61`) | ascending | `command_boundary.py:60` | E1; chart says "Stereo pan or pair balance" without defining which for 5/6, 7/8 | **PV\*** for mono pan; **UNK** for stereo-pair *semantics* (pan vs constant-power balance) | Medium |

### 2.2 Bus / master parameters (MIDI Channels 8–12)

| # | Parameter | Param ID | Ch | CC | Raw range | Conversion | Evidence | Verdict | Implemented? |
|---|---|---|---|---|---|---|---|---|---|
| 13 | Main master level | `main.fader` | 8 | 7 | 0–127 | fader curve | E1 | PV\* | Yes |
| 14 | Main balance | `main.balance` | 8 | 10 | 0–127 | pan curve | E1 | PV\* | Yes |
| 15 | Monitor 1 master | `mon1.fader` | 9 | 7 | 0–127 | fader curve | E1 | PV\* | Yes |
| 16 | Monitor 2 master | `mon2.fader` | 10 | 7 | 0–127 | fader curve | E1 | PV\* | Yes |
| 17 | FX 1 master send | `fx1.fader` | 11 | 7 | 0–127 | fader curve | E1 | PV\* | Yes |
| 18 | FX 2 master send | `fx2.fader` | 12 | 7 | 0–127 | fader curve | E1 | PV\* | Yes |
| 19 | Bus limiter | `main/mon1/mon2.limiter` | 8–10 | 8 | 0–127 | -30…0 dB (undocumented) | E1 | **UNK** | **No** — documented in catalog, absent from allowlist |
| 20 | 9-band GEQ | `main/mon1/mon2.geq_*` | 8–10 | 11–19 | 0–127 | ±15 dB, 64 = 0 | E1 | **UNK** | **No** — documented, absent from allowlist |
| 21 | FX algorithm select | — | 14–15 | PC 1–16 | 1–16 | n/a | E1 | **UNK** | **No** — `send_cc` rejects Ch 13–16 |
| 22 | FX parameter tweaks | — | 14–15 | 1–4 | 0–127 | n/a | E1 | **UNK** | **No** |
| 23 | Solo | `ch{1-7}.solo` | 1–7 | 6 | 0–127 | boolean | E1 | **UNK** | **No** — transport allows CC6 (`midi_out.py:217,224`), no allowlist entry, no state record |
| 24 | Snapshot recall / reset | — | 16 | PC 1–16 | 1–16 | n/a | E1 | **UNK** | **No** |
| 25 | Tap tempo | — | 16 | Note 0 | vel 1–127 | n/a | E1 | **UNK** | **No** |
| 26 | EZ-Gain | `global.ez_gain` | 0 | — | — | — | `HARDWARE_SPECIFIED` (`state_model.py:306-315`) | **UNK** | No address exists; correctly modelled as a spec-only feature |

**Tally:** 97 implemented parameter IDs across 97 unique `(channel, CC)` pairs. 0 at E0, 0 at E4, **97 at E1+E2**, 5 byte-level verified at E3 (§10.4).

---

## 3. Incorrect or Unsupported MIDI Mappings

No mapping is *demonstrably wrong*. Five are **unsupported by the project's own cited source**, which is a different and still-serious defect.

### M-01 — Gain / Low Cut / Compressor restricted to Ch 1–4, but the chart says only "not on Ch 7"
- **File/lines:** `flow8/command_boundary.py:71-74`; `flow8/parameter_engine.py:79,91,136`; contrasted with `FLOW8_USB_MIDI_PROTOCOL.md` §2 table rows CC 8, CC 9, CC 11 ("Not applicable on Ch 7").
- **Evidence:** The chart's per-CC exception column excludes **only Channel 7**, which by plain reading makes CC 8/9/11 valid on Ch 1–6. Its own §6 coverage table then says "CC 8 on Ch 1–4", "CC 9 on Ch 1–4", "CC 11 on Ch 1–4". The document contradicts itself in two adjacent sections.
- **Assessment:** The *code* is probably right (Ch 5/6 and 7/8 are line-level pairs with trim, not -20…+60 dB preamps — `FLOW8_HARDWARE_DOMAIN_MODEL.md` §3.1). The *evidence* does not establish it. So the restriction is currently justified by hardware reasoning, not by protocol.
- **Severity:** High (it is the difference between "documented" and "inferred" for 12 of 97 parameters).
- **Action:** Correct the chart's §2 exception column to "Ch 1–4 only". Add a citation for the chart itself. Until then, downgrade these 12 to UNVERIFIED.

### M-02 — Compressor on Ch 5/6: the code rejects what the domain model says exists
- **File/lines:** `flow8/domain_model.py:234` (`has_compressor=True` for Channel 5/6) and `:247` (same for Channel 7/8) **vs** `flow8/parameter_engine.py:136` (`if self.channel_index > 4 … raise`) and `flow8/command_boundary.py:71` (compressor allowlist built only for `1 <= ch <= 4`).
- **Evidence:** `FLOW8_HARDWARE_DOMAIN_MODEL.md` §3.1 item 4 — "Fast-acting RMS compressor on **all input strips** (Ch 1–4 mono, Ch 5/6 & 7/8 stereo linked)"; `FLOW8_SPECIFICATION_GAP_ANALYSIS.md` §2.2 — "Present on **every input channel** (Ch 1–4, Ch 5/6, 7/8)"; chart — CC 11 verified on Ch 1–4 only.
- **Assessment:** This is a genuine, unresolved three-way contradiction between the hardware model, the gap analysis, and the protocol chart. `Flow8ChannelStrip.set_compressor` carries a **guard that can never fire** (`self._spec.has_compressor` is `True` for ch5/6, so only the `> 4` clause matters) — dead defensive code that documents an intent the allowlist does not honour.
- **Severity:** High. A user with a compressed guitar on 7/8 is told by the domain model the feature exists and by the engine that it does not.
- **Action:** Resolve explicitly. If the compressor truly exists on the stereo pairs, its control address is **UNKNOWN** and must be labelled `UNKNOWN`, not `N/A (REJECTED)`. Change the matrix rows for Ch 5/6 and 7/8 from "N/A (REJECTED)" to `UNKNOWN — capability specified, control address not verified`. Do not weaken the engine guard until an address exists.

### M-03 — Chart still assigns Hi-Z to Ch 3/4, contradicting the corrected domain model
- **File/lines:** `FLOW8_USB_MIDI_PROTOCOL.md` §1.1, rows Ch 3 and Ch 4 ("Combo, **Hi-Z**, Gain, Low Cut, 4-Band PEQ, Compressor").
- **Evidence:** `FLOW8_HARDWARE_DOMAIN_MODEL.md` §2.1 explicitly strikes this ("Hi-Z guitar/bass high-impedance inputs are physically located exclusively on Connector 6R and Connector 8R"), and `FLOW8_SPECIFICATION_GAP_ANALYSIS.md` §3 Assumption 1 lists it as "Defeated". `flow8/domain_model.py:209,222` correctly has `has_hi_z=False` for Ch 3/4.
- **Assessment:** The document that is the **sole source of protocol evidence** was never updated after the project's own hardware correction. Any `PROTOCOL_VERIFIED` claim that rests on it inherits the staleness. This is a direct hit on the credibility of the evidence base, not merely a typo.
- **Severity:** High (evidence-integrity).
- **Action:** Re-issue the chart with a revision number, a citation, and the Hi-Z correction. Until re-issued, the chart must not be described as "official".

### M-04 — `parameter_mapping.py` marks its fader/mute/pan mappings "VERIFIED" with no source
- **File/lines:** `flow8/parameter_mapping.py:6-9` (module docstring), `:22`, `:41`, `:83` ("VERIFIED"), `:192` ("VERIFIED" for PEQ), `:231` ("VERIFIED" for compressor).
- **Evidence:** No function-level citation, no reference to the chart section, no test that establishes semantics against hardware. `FADER_UNITY_MIDI = 101` (`:87`) is asserted as "Unity gain position on 0–127 scale in **standard digital mixer firmware**" — an appeal to a nonexistent universal standard. This is the parameter the entire dB conversion depends on.
- **Assessment:** The word "VERIFIED" here means "we believe this matches the chart", but it is placed in code where it reads as an established fact. The `-inf`/unity/+10 dB curve has **no evidentiary basis at all**, as the module itself half-admits on line 9.
- **Severity:** Medium.
- **Action:** Replace "VERIFIED" with `CHART-MAPPED (uncited)` and cite the chart section per function. Propagate the 101-unity assumption into the gap ledger as an open assumption.

### M-05 — `main.balance` uses CC 10 on Ch 8, which the chart grants "MAIN only" — consistent, but untested
- **File/lines:** `flow8/command_boundary.py:49`; `flow8/midi_out.py:228`; `flow8/parameter_engine.py:213`.
- **Evidence:** Chart §3, CC 10 row: "MAIN (Ch 8) only". Engine correctly rejects balance on `mon1/mon2/fx1/fx2` (`parameter_engine.py:213`), and `midi_out` correctly omits CC 10 for Ch 9/10 (`:229-230`). Internally consistent (E2), E1 otherwise.
- **Severity:** Low.
- **Action:** None required beyond adding the missing byte-level test (see F-09).

---

## 4. Stereo Channel Addressing Findings

**Question set:** Are 5/6 and 7/8 stereo-linked? Is balance different from mono pan? Are CC addresses correct? Can one side be controlled independently? Are logical channels mapped to the correct physical MIDI channel?

### 4.1 Representation — correct

`flow8/domain_model.py:227-250` models exactly **one logical strip per stereo pair**:

- `LOGICAL_CHANNELS[5]` → `name="Channel 5/6"`, `kind=STEREO_INPUT`, `physical_connectors=("IN_5L","IN_6R")`, `pan_or_balance="BALANCE"`.
- `LOGICAL_CHANNELS[6]` → `name="Channel 7/8"`, `physical_connectors=("IN_7L","IN_8R")`, `pan_or_balance="BALANCE"`.

The allowlist is generated by a single loop index (`command_boundary.py:56`), producing exactly one `(channel, CC)` per parameter per strip. **Verified at runtime:** 97 parameter IDs map to 97 unique `(channel, CC)` pairs — no pair is duplicated, so there is no second address that could reach the "other half" of a pair.

### 4.2 Can one side be controlled independently? — No

There is no parameter ID, CC, or channel for `IN_5L`, `IN_6R`, `IN_7L`, or `IN_8R` individually anywhere in scope. CC 10 on that channel is a single balance value for the pair. **This is correct and is a genuine PASS.** The stereo link is enforced by the address space, not by a software check that could be bypassed.

### 4.3 Is balance different from mono pan? — **Only in documentation, not in code**

- **File/lines:** `flow8/parameter_engine.py:61-67` (`set_pan` docstring distinguishes "Pan" for Ch 1–4 from "Balance" for Ch 5–7); `flow8/parameter_engine.py:211-215` (`set_balance` exists **only on `Flow8BusStrip` and only for `main`**).
- **Finding F-03 (Medium):** a stereo **input** strip has no `set_balance` method. Its balance is exposed as `.pan`, and its state record's `parameter_name` is literally `"pan"` (`flow8/state_model.py:135,178`: `parameter_name="pan"` for all ch 2–7). The MAIN bus, by contrast, has both `main.balance` and `parameter_name="balance"`. So the same physical concept is named two different ways depending on whether it is an input pair or the master.
- **Consequence:** a UI bound to `parameter_name` will render a balance control as "Pan" on Ch 5/6 and 7/8, and any future pan-law/balance-law divergence has nowhere to branch. The wire mapping is identical (`type: "pan"` for both, `command_boundary.py:60,49`), which is fine protocol-wise but means the distinction is currently **cosmetic**.
- **Action:** give stereo input strips a `set_balance` alias (or a `pan_or_balance` field on the state record), and stop labelling a balance as `"pan"` in state.

### 4.4 CC addresses — correct per the chart, and internally consistent

`flow8/midi_constants.py:56-57`: `MIDI_CH_INPUT_5 = 5  # Line 5/6 Stereo (Status: 0xB4)`, `MIDI_CH_INPUT_6 = 6  # Line 7/8 Stereo (Status: 0xB5)`. Matches chart §1.1. Status bytes verified numerically: `0xB0|4 = 0xB4`, `0xB0|5 = 0xB5`.

### 4.5 Logical → physical channel mapping — **correct, but the naming is a live hazard**

**Finding F-02 (Medium).** The parameter-ID namespace does **not** correspond to physical input numbers:

| Param prefix | MIDI Ch | Physical inputs | `chN` numeric reads as |
|---|---|---|---|
| `ch1`–`ch4` | 1–4 | IN_1…IN_4 | correct |
| `ch5` | 5 | **IN_5L + IN_6R** | "input 5" |
| `ch6` | 6 | **IN_7L + IN_8R** | "input 6" — **wrong by two** |
| `ch7` | 7 | USB/BT return (no jack) | "input 7" — **wrong** |

`ch6.fader` controls physical inputs **7 and 8**. `ch7.fader` controls the **USB/BT return**, which has no analog connector at all. Two of seven strip indices are numerically misleading by two or more positions.

This is defensible as a "strip index = fader position on the 6-strip surface" model (the domain doc describes 6 strip faders + 1 main), but the API never says so. A straightforward "fader 6 → `ch6`" binding in Phase D's UI silently mixes the wrong pair.

- **Severity:** Medium (latent, but a wrong-channel write to a live PA).
- **Action:** either rename to `strip5_6.*` / `strip7_8.*` / `usb_bt.*`, or add an explicit `physical_inputs` field on `ParameterState`/`LogicalChannel` and mandate that UI code resolves labels through it. At minimum, document the mapping in `parameter_engine.py`'s module docstring.

### 4.6 Minor model defects

- **F-11 (Low):** `flow8/domain_model.py:55` — `channel_index: int  # 1-based (1..8)`. Only 1–7 exist; `Flow8ChannelStrip.__init__` rejects 8 (`parameter_engine.py:32`) and channel 8 is the Main *bus*, not a strip. Misleading comment on the central dataclass.
- **F-12 (Low):** `FLOW8_HARDWARE_DOMAIN_MODEL.md` §1 mermaid and §3 label processing as "All Channels 1-8" / "Channels 1-8" while only 7 logical strips exist and Ch 7 is a digital return.

---

## 5. Bus and FX Addressing Findings

**Requirement:** per-channel Mon 1/Mon 2/FX 1/FX 2 sends must not be confused with bus master levels or FX engine parameters.

### 5.1 The four layers are genuinely separated — PASS

| Layer | Address | Implemented | Where |
|---|---|---|---|
| Per-channel Mon 1 send | Ch 1–7, CC 14 | Yes | `command_boundary.py:65` |
| Per-channel Mon 2 send | Ch 1–7, CC 15 | Yes | `:66` |
| Per-channel FX 1 send | Ch 1–7, CC 16 | Yes | `:67` |
| Per-channel FX 2 send | Ch 1–7, CC 17 | Yes | `:68` |
| Monitor master level | **Ch 9 / Ch 10, CC 7** | Yes | `:50-51` |
| FX master level | **Ch 11 / Ch 12, CC 7** | Yes | `:52-53` |
| FX engine parameters | **Ch 14 / Ch 15, CC 1–4 + PC** | **No** | rejected at `midi_out.py:213-237` (no branch matches Ch 13–16) |

Separation is enforced structurally: sends live on channels **1–7**, masters on **9–12**, and engines on **14–15** which the transport gate cannot address at all. There is no code path that could send a per-channel send value to a bus master. **This is a PASS.**

### 5.2 FX engine parameters are entirely absent, yet documented as covered

- **Finding F-06 (Medium).** `FLOW8_PHASE_C_IMPLEMENTATION.md` §3.1 item 4 says the allowlist contains "**83 verified parameter targets**". The actual size is **97** (measured at runtime, §10.3). Neither number includes any FX-engine parameter, and yet `FLOW8_USB_MIDI_PROTOCOL.md` §6 claims "FX Algorithm & Tweaks | PC 1–16, CC 1–4 on Ch 14–15 | VERIFIED | **Complete coverage**".
- The catalog (`FLOW8_PARAMETER_CATALOG.md` §2) also lists `ch{i}.solo` for all 7 channels — 7 parameter IDs that do not exist in the allowlist and have no state record.
- **Assessment:** "Complete coverage" is a coverage claim about the *protocol*, sitting in a table that readers will take as a claim about the *implementation*. Both counts in the implementation doc are wrong.
- **Action:** state the real count (97); add an "Implemented?" column to the catalog; mark FX engine, bus limiter, bus GEQ, solo, snapshot and tap tempo as `NOT IMPLEMENTED — address documented, no allowlist entry`. Do not let a protocol-coverage table stand in for an implementation table.

### 5.3 Transport gate is more permissive than the boundary — deliberate, but undocumented

- **Finding F-07 (Low).** `midi_out.py:228-230` allows CC 8 and CC 11–19 on Ch 8–10 (bus limiter and 9-band GEQ) and CC 6 (solo) on Ch 1–7. **None** of these has an allowlist entry, so they are unreachable through `Flow8CommandBoundary` — the layering is safe. But the gate advertises capability the engine cannot use, and a future direct `send_cc` caller would bypass the allowlist entirely.
- **Action:** either remove the unreachable CCs from the gate, or add a comment stating the gate is a *superset* and the allowlist is the authority. Also note `midi_out.py:5` still reads "Scope: Phase 2A Verified Parameters ONLY" and lists four parameters — stale after Phase C.

### 5.4 FX master semantics

- **F-13 (Low).** `Flow8BusStrip.set_fader` (`parameter_engine.py:207`) documents "Set master fader / send level for this bus". For `main` it is a master fader (−∞…+10 dB on the output); for `fx1`/`fx2` it is a **send** master feeding an FX engine, not a return/wet level. The chart is explicit ("FX 1 Master Send Level"), the code calls both the same thing, and there is **no FX return/wet level parameter at all** in scope. Rename for `fx*` (`set_send_master`).

---

## 6. CC Conflict Analysis

**Question:** do repeated CC numbers collide, and does MIDI channel addressing genuinely resolve each?

**Answer: yes, all are genuinely resolved — and this is the one area where the resolution is proven at bit level, not merely asserted.**

The resolution mechanism is `status_byte = 0xB0 | ((channel - 1) & 0x0F)` (`midi_out.py:244`), which correctly yields `0xB0…0xBF` for channels 1–16. Byte patterns are asserted against exact DWORDs in `tests/test_midi_out.py:73-95` and `tests/test_parameter_engine.py:184-192`.

| CC | Inputs 1–7 (`0xB0–B6`) | Main/Mon (`0xB7–B9`) | FX master (`0xBA–BB`) | FX engine (`0xBE–BF`) | Collides? | Resolution + status |
|---|---|---|---|---|---|---|
| 1–4 | PEQ bands | — | — | FX tweaks 1–4 | **Nominally yes** | Resolved by channel nibble. FX engine branch does not exist in `send_cc`, so unreachable. **Safe.** |
| 5 | Mute | — | — | — | No | — |
| 6 | Solo | — | — | — | No | Allowed by gate (`:217,224`), absent from allowlist → dead capability |
| 7 | Fader (send to Main) | **Bus master level** | **FX master send** | — | **Yes (intended)** | Intended reuse; correct per chart §3 |
| **8** | **Preamp Gain (Ch 1–4)** | **Bus Limiter** | — | — | **Yes** | **Resolved by channel.** `midi_out.py:214` grants CC 8 only for Ch 1–4; `:228-230` grants CC 8 for Ch 8–10. No input channel ≥ 8 and no bus ≤ 7, so the sets are disjoint. Limiter unreachable via boundary. **Genuinely resolved.** |
| 9 | Low Cut (Ch 1–4) | — | — | — | No | — |
| 10 | Pan / Balance | **Main balance** | — | — | **Yes (intended)** | Chart grants CC 10 on Ch 8 only; code omits it for Ch 9–12 |
| **11** | **Compressor (Ch 1–4)** | **GEQ 62.5 Hz** | — | — | **Yes** | **Resolved by channel.** Same disjoint-set argument as CC 8. GEQ unreachable via boundary. **Genuinely resolved.** |
| 12 | Phantom (Ch 1–2) | **GEQ 125 Hz** | — | — | **Yes** | Resolved by channel. Note: CC 12 is a *physical relay write*; see F-08 |
| 13 | — | GEQ 250 Hz | — | — | No | Gate allows `11 ≤ cc ≤ 19` on Ch 8–10 |
| **14–17** | **Mon1 / Mon2 / FX1 / FX2 sends** | **GEQ 500 Hz / 1 k / 2 k / 4 k** | — | — | **Yes — highest-risk pair** | Both sides are *implemented-adjacent* and semantically unrelated (aux send vs graphic EQ band). Resolution rests entirely on the channel nibble. Correct today; becomes dangerous the moment bus GEQ is implemented, because `main.geq_500` (Ch 8 CC 14) and `ch1.send_mon1` (Ch 1 CC 14) differ by one bit. **Genuinely resolved, but must be regression-locked.** |
| 18–19 | — | GEQ 8 k / 16 k | — | — | No | — |

### 6.1 Conflict verdict

- Every repeated CC is resolved by MIDI channel, and the channel→status-byte computation is correct and byte-tested.
- The dangerous coincidences are **CC 8**, **CC 11**, **CC 12** and **CC 14–17**, all of which pair a *channel-strip* function with an *output-bus* function on adjacent channel numbers.
- **F-10 (Low, preventive):** there is no test that asserts a stress table of `(channel, cc) → status byte` for the full 97-pair allowlist. A single off-by-one in the channel field would silently move a vocal fader command onto the Main bus. Recommend a table-driven encoding test over all 97 pairs (see §11).

---

## 7. State and Dispatch Verification

### 7.1 `dispatched_to_hardware` semantics — correctly narrow, but the name overpromises

- **Definition in code:** `flow8/command_boundary.py:41` (field), `:213-226` (assignment), `:246` (log). It is set `True` **only** when `self._midi_out.is_connected` is true **and** `send_cc` returned without raising. `send_cc` returns after `midiOutShortMsg` returned `MMSYSERR_NOERROR` (`midi_out.py:247-253`).
- **What that means:** the *Windows MIDI API accepted the short message into the driver queue*. It does **not** mean the mixer received it, parsed it, or applied it. WinMM buffers; `midiOutShortMsg` completing is not evidence of USB transmission.
- **Verdict:** the flag is implemented conservatively and **does not** overclaim — it is the strongest correct thing about the dispatch model. The **name** should be `accepted_by_winmm`. **Finding F-04 (Medium, naming/claim):** every downstream document and the Phase C test report read this flag as "Dispatched, `dispatched_to_hardware = True`" and then as "Physical Hardware Proof" (§8).

### 7.2 Offline case — `success=True` is misleading

- **File/lines:** `flow8/command_boundary.py:224-226` — the offline branch sets `dispatch_success = True` and `dispatched_to_hardware = False`.
- **Consequence:** `CommandLogEntry.success` is `True` (`:244`) for a command that **never touched the wire**. `tests/test_parameter_engine.py:158-169` explicitly asserts this.
- **Finding F-05 (Medium):** `success` conflates "accepted by the command boundary" with "delivered to hardware". A caller that checks only `.success` — the obvious thing to do — believes a silent mixer received the command. This is precisely the class of ambiguity the audit brief asks about.
- **Action:** rename to `accepted`; add a distinct `outcome` enum (`REJECTED / VALIDATED_OFFLINE / QUEUED / SEND_FAILED`). Keep the existing tests but assert the new enum.

### 7.3 Failed-send case — state is written **after** failure, and the log claims a raw value that was never sent

- **File/lines:** `command_boundary.py:216-221` (failure sets `dispatch_success = False`), then **falls through** to `:230-236` (`self._state_store.set_commanded_value(...)`) and `:242` (`raw_midi_sent=raw_midi`), logs the entry (`:249-251`), and only then raises at `:253-254`.
- **Consequences:**
  1. The state store records the commanded value even though dispatch failed. `sync_status` becomes `PENDING_DISPATCH` (`state_model.py:350-355`) — a status that means "awaiting dispatch" for a dispatch that already failed and will never retry.
  2. `raw_midi_sent` is populated (`:242`) in the failed case **and** the offline case, despite nothing being sent. The field name asserts a transmission that did not occur.
- **Finding F-01 (High).** Two separate fields (`success`, `raw_midi_sent`) both assert delivery for non-delivered commands. This is the most concrete correctness defect found.
- **Action:** (a) update state only on success, or write `SyncStatus.DIVERGENT`/a new `FAILED` on failure; (b) set `raw_midi_sent = None` whenever `dispatched_to_hardware is False`, and rename the field to `raw_value_prepared` or add `raw_value_queued`; (c) preserve the exception.

### 7.4 Rejected / conversion-failed cases — correct

- Allowlist rejection (`:121-136`), conversion failure (`:195-210`), and out-of-range (`:192`) all log `dispatched_to_hardware=False`, `raw_midi_sent=None`, `success=False` and raise the correct exception type (`Flow8CommandRejectedError` / `Flow8ValidationError`). **PASS.**

### 7.5 Allowlist `min`/`max` metadata is never enforced

- **File/lines:** declared on all 97 entries (`command_boundary.py:48-78`, e.g. `"min": 0, "max": 1` for mute and phantom, `:59,78`).
- **Evidence:** `grep -rn '\["min"\]\|\["max"\]' flow8/ tests/` → **no matches**. The only bounds check is the global `0 <= raw_midi <= 127` at `:192`.
- **Finding F-09 (Low, latent):** the schema promises per-parameter bounds and silently ignores them. It is harmless today because every non-boolean parameter is 0–127 and booleans are converted by `mute_bool_to_midi`, but a future 0–1 or 0–100 raw parameter would pass validation at 127.
- **Action:** enforce `spec["min"] <= raw_midi <= spec["max"]` inside the try-block, or delete the fields so the schema stops lying.

### 7.6 Bidirectional sync is non-functional — `observed_value` is never set in production

- **File/lines:** `flow8/state_model.py:368` defines `set_observed_value`. **Callers outside tests: zero** (`grep` finds only `tests/test_domain_and_state.py:129,134`). `flow8/midi_in.py` contains **no** reference to `Flow8StateStore`, `set_observed_value`, or `VerificationLevel` — the listener produces raw event dicts (`midi_in.py:107-118`) and nothing consumes them.
- **Consequence:** in any real session, `observed_value` stays `None` for all 97 parameters, so `sync_status` can only ever be `PENDING_DISPATCH` (`:350-352`). **`SYNCED` and `DIVERGENT` are unreachable in production code.** No inbound CC is ever mapped to a `param_id`.
- **Finding F-15 (Medium).** The docs are honest that Phase 2B did not claim sync, but `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` §1 defines `HARDWARE_TESTED` partly as "confirmed via physical endpoint reception" and then applies it — there is no reception path to confirm with.
- **Action:** state plainly in the matrix that observed-state reconciliation is **not implemented**; do not cite "loopback" (see §8.2).

### 7.7 Unit mismatch will break sync the moment it is wired up

- **File/lines:** `state_model.py:352` (`elif param.observed_value == value`) and `:387` (`if param.commanded_value == value`).
- **Defect:** `commanded_value` is stored in the caller's engineering unit (`command_boundary.py:231-236` passes `value` as given — e.g. `-50.0` dB, or `0.0` %), while `observed_value` from a future inbound MIDI path will be a raw `0–127` integer. `-50.0 == 0` is never true.
- **Finding F-16 (Medium, Phase D blocker):** sync would report `DIVERGENT` permanently, for every parameter, the day inbound handling is connected.
- **Action:** store both `commanded_raw` and `observed_raw` and compare those; keep engineering units as a display projection only.

### 7.8 Positive finding — no auto-upgrade path exists

`VerificationLevel` is assigned **only** in `_initialize_baseline_parameters` (`state_model.py:88-315`) and the enum is defined at `:17-22`. Nothing in `command_boundary`, `parameter_engine`, `midi_out`, or `midi_in` writes it. A successful WinMM call therefore **cannot** promote a parameter's level in code. Whatever inflation exists is in the **documents**, not the runtime. This should be preserved deliberately.

**Runtime inventory (read-only probe):** allowlist = **97**; state records = **98**; allowlist params missing a state record = **none**; levels present = `{HARDWARE_SPECIFIED, HARDWARE_TESTED, PROTOCOL_VERIFIED}` (note: `IMPLEMENTED` and `UNKNOWN` are defined but **never used** anywhere).

### 7.9 `IMPLEMENTED` and `UNKNOWN` are declared but never applied

- **Finding F-17 (Low).** `state_model.py:17-22` defines five levels; production only ever writes three. The audit brief's required distinction ("IMPLEMENTED means implemented in software"; "UNKNOWN remains unknown") is therefore **not expressible** in the current state model: 97 implemented parameters carry no `IMPLEMENTED` marking, and the genuinely unknown ones (compressor on 5/6, bus GEQ, FX engine) are either absent or mislabelled `N/A (REJECTED)`.
- **Action:** apply `IMPLEMENTED` to the 97 (or introduce an orthogonal `implemented: bool` plus `verification:` enum, which is cleaner — implementation status and evidence status are independent axes).

---

## 8. Physical Hardware Evidence

### 8.1 What `tests/test_hardware_midi_out.py` actually measures

| # | Test | Lines | What it actually establishes | Level |
|---|---|---|---|---|
| 1 | `test_hardware_lifecycle` | `:25-31` | `midiOutGetNumDevs`/`GetDevCapsW` found a device whose name contains "FLOW 8"; `midiOutOpen` returned 0; `midiOutClose` succeeded | Driver lifecycle |
| 2 | `test_hardware_reconnect` | `:33-41` | open→close→open returns 0 each time | Driver lifecycle |
| 3 | `test_hardware_context_manager` | `:43-46` | context manager opens/closes | Driver lifecycle |
| 4 | `test_hardware_parameter_dispatches` | `:48-86` | **No assertions at all** beyond "no exception raised" from 15 `send_*` calls | E3 only |
| 5 | `test_hardware_parameter_engine_dispatch` | `:88-119` | `entry.success`, `entry.dispatched_to_hardware` and `raw_midi_sent` are true/expected for 3 commands | E3 only |
| 6 | `test_hardware_midi_in_lifecycle` | `:121-135` | `midiInOpen`/`midiInStart`/`midiInStop`/`midiInClose` return without error; `time.sleep(0.2)` | Driver lifecycle |

**Nothing in this file reads a single byte back from the mixer.** `test_hardware_midi_in_lifecycle` starts the listener, sleeps 200 ms, stops it, and **never asserts that any event arrived**. There is no loopback test at all.

### 8.2 The four required evidence levels, separated

| Level | Question | Established? | Basis |
|---|---|---|---|
| **1. MIDI API acknowledgement** | Did WinMM accept the message? | **YES** | Device enumerated at index 1 (`FLOW 8 MIDI OUT`); `midiOutShortMsg` returned `MMSYSERR_NOERROR`; all 6 hardware tests executed rather than skipped |
| **2. Physical MIDI transmission evidence** | Did bytes leave the host on the USB wire? | **NO** | No USBPcap/USB trace, no timestamped driver log, no loopback from the mixer's own MIDI OUT, no retained artifact |
| **3. Physical mixer parameter change** | Did the mixer change state? | **NO** | No readback, no snapshot dump, no encoder/LCD capture. `FLOW8_HARDWARE_DOMAIN_MODEL.md:254` states inbound telemetry was never observed ("physical pots telemetry unobserved (TX off)") |
| **4. Audible audio behaviour change** | Did the audio change? | **NO** | No audio capture, no gain/null test, no listening test recorded |

### 8.3 Findings

- **F-04 (High) — `HARDWARE_TESTED` is over-assigned.** `flow8/state_model.py:102,115,128,141` mark `main.fader`, `ch1.fader`, `ch1.mute`, `ch1.pan` as `HARDWARE_TESTED`. Under this audit's (and the matrix's own) definition, that requires physical confirmation. Only level 1 is established. These four must be downgraded to `API_ACKNOWLEDGED` / `PROTOCOL_VERIFIED` until a readback test exists.
- **F-04b (Medium) — the matrix and the code disagree about the same parameter.** `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` §2 marks **EQ Low (CC 1) on Ch 1** as `HARDWARE_TESTED` with evidence "`test_hardware_parameter_engine_dispatch`". That test only asserts `entry.success`/`dispatched_to_hardware`/`raw_midi_sent` — i.e. level 1. And `state_model.py:203` records `ch1.eq_low` as `PROTOCOL_VERIFIED`, not `HARDWARE_TESTED`. The same parameter carries two different grades in two documents.
- **F-04c (Medium) — "Live Hardware Loopback" is cited as evidence and does not exist.** Matrix §2/§3 evidence column repeatedly reads "Live Hardware Loopback". No loopback exists in scope: `midi_in` is not coupled to the state store (§7.6), and the inbound test asserts nothing. This is the single most damaging claim in the report set because it is the justification for the top verification grade.
- **F-08 (Medium) — no safety interlock on phantom writes.** `parameter_engine.py:175` gates phantom to Ch 1–2, but there is no readback, no confirmation, and no refusal to energise +48 V onto a line-level source. A single `set_phantom(True)` on Ch 1 with a dynamic mic connected is an unrecoverable-in-software hardware action. Recommend: never automate phantom in CI, require explicit operator confirmation at the UI layer, and add `HARDWARE_TESTED` only after a readback path exists.

---

## 9. BLE / SysEx Evidence

**Claim under test:** "Bulk SysEx memory dumps are handled through BLE GATT."

### 9.1 Finding F-18 (High) — the claim is unsupported, self-contradictory, and unimplemented

Four in-scope documents give four different answers:

| Document | Line | Statement | What it really says |
|---|---|---|---|
| `FLOW8_USB_MIDI_PROTOCOL.md` | `:132` | "Bulk SysEx Memory Dump \| SysEx `0xF0 … 0xF7` \| **UNKNOWN / UNDOCUMENTED** \| Proprietary format **handled over BLE**" | Admits undocumented, then asserts a transport anyway |
| `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` | `:65` | "Standard MIDI SysEx dumps are not documented for USB MIDI. FLOW 8 **handles memory transfers over Bluetooth Low Energy GATT attributes**." | States as fact |
| `FLOW8_SPECIFICATION_GAP_ANALYSIS.md` | `:73` | "bulk memory **JSON** dumps are proprietary app functions" | **JSON**, not SysEx; "proprietary app function", not GATT attribute |
| `FLOW8_HARDWARE_DOMAIN_MODEL.md` | `:146` | BLE = "FLOW Mix App Control \| **Custom / BLE-MIDI**" — while §4.1 says BLE is "**exclusively** for telemetry and parameter synchronization" | Conflates custom GATT with **BLE-MIDI** (a standard GATT MIDI service), and contradicts itself in the same document |

### 9.2 Classification

| Question | Answer |
|---|---|
| Officially documented? | **No.** No official artifact in scope; the chart itself says UNKNOWN/UNDOCUMENTED |
| Protocol verified? | **No.** No service UUID, characteristic UUID, packet capture, or payload sample |
| Implemented? | **No.** Zero SysEx, zero BLE transport code in scope. `domain_model.py:35` merely declares an enum member with the string "Bluetooth Low Energy Control (GATT Server)" |
| Merely proposed? | **Yes** — and inconsistently proposed |

### 9.3 The transport conflation is the finding

Three different, non-interchangeable things are used as if equivalent:

1. **BLE MIDI** — a standard GATT MIDI service (`03B80E5A-…`) carrying MIDI byte streams including SysEx.
2. **A proprietary GATT service** — arbitrary characteristics; a bulk preset could be a `write`/`notify` payload.
3. **USB MIDI SysEx** — `0xF0…0xF7` over the USB-MIDI endpoint.

The in-scope documents slide between all three. `FLOW8_HARDWARE_DOMAIN_MODEL.md` §4.1 even states the correct principle ("BLE control … has zero control or telemetry capability" is said of A2DP; and "BLE … exclusively for telemetry and parameter synchronization") — then its own diagram labels the same link "Custom / BLE-MIDI".

**Consequence:** asserting "SysEx over BLE GATT" would justify designing a snapshot engine around a transport that may not carry SysEx at all (the gap analysis says **JSON**), and would justify assuming a BLE MIDI service exists when only a proprietary service may be present.

**Required correction:** strike the claim everywhere; replace with:
> **Bulk preset transfer: `UNKNOWN`.** No official documentation, no protocol evidence, no implementation. Three candidate transports exist (USB MIDI SysEx, BLE MIDI GATT, proprietary GATT JSON) and none has been captured. This is an **open investigation item**, not a resolved gap.

---

## 10. Test Results

### 10.1 Commands and actual results

| # | Command | Result |
|---|---|---|
| 1 | `python -m pytest tests/test_parameter_engine.py tests/test_hardware_midi_out.py tests/test_midi_out.py -v` | **FAILED TO RUN** — `C:\Python314\python.exe: No module named pytest`, exit **1**. pytest is not installed; the project uses `unittest`. Reported, not worked around silently. |
| 2 | `python -m unittest tests.test_parameter_engine tests.test_hardware_midi_out tests.test_midi_out -v` | **`Ran 28 tests in 1.138s` — `OK`, exit 0** |
| 3 | `python -m unittest discover -s tests -v` | **`Ran 50 tests in 1.124s` — `OK`, exit 0** |
| 4 | Read-only endpoint enumeration (`midiOutGetNumDevs`/`midiInGetNumDevs` + caps) | **2 MIDI OUT**: `0 'Microsoft GS Wavetable Synth'`, `1 'FLOW 8 MIDI OUT'`; **1 MIDI IN**: `0 'FLOW 8 MIDI IN'` |
| 5 | Read-only allowlist/state probe (no MIDI calls) | allowlist **97**; state records **98**; missing state records **none**; levels `{HARDWARE_SPECIFIED, HARDWARE_TESTED, PROTOCOL_VERIFIED}` |

Exit status was captured explicitly (`PIPESTATUS`) in both test runs; neither was masked by `tail`.

### 10.2 Reconciliation with `FLOW8_PHASE_C_TEST_RESULTS.md`

The claimed **50/50, 0 failures, 0 errors, 0 skips** is **reproduced exactly**. The documented per-file breakdown (12 / 6 / 9 / 10 / 13 = 50) matches the files present.

Two caveats:

- **The claim is true but weaker than presented.** "50/50 including Live Hardware Proof" — 6 of those 50 touch the device, and those 6 assert nothing beyond "WinMM returned 0" (§8.1). No test asserts level 2, 3, or 4.
- **The phrase "0 skips" is load-bearing.** The hardware module skips when no endpoint is found. On a machine without the mixer, 6 tests silently skip and the suite still reports `OK`. The hardware "proof" is therefore environment-dependent and would not be caught by a green build.

### 10.3 Byte-level coverage is 5 of 97 pairs

Tests that assert the exact WinMM DWORD:

| Test | Pairs asserted |
|---|---|
| `tests/test_midi_out.py:73-95` | `(1,7)`, `(1,5)`, `(1,10)`, `(8,7)` |
| `tests/test_parameter_engine.py:184-192` | `(1,1)`, `(8,7)` |

**Unique `(channel, CC)` pairs with a byte-level assertion: 5 of 97 (5.2%).**

- **F-10 (Medium).** Not byte-verified anywhere: gain CC 8, low cut CC 9, compressor CC 11, phantom CC 12, sends CC 14–17, EQ bands CC 2/3/4 on Ch 1, **all of Ch 2–7**, and **all of Ch 9–12**. The channel/CC binding for the entire bus layer — the exact surface where CC conflicts live (§6) — has **zero** byte-level tests.
- The tests that do cover those parameters assert `entry.raw_midi_sent` (an integer computed by the boundary) and `entry.success` — i.e. they verify the boundary's own arithmetic, not what reached WinMM.
- **Action:** add a single table-driven test asserting `midiOutShortMsg` DWORDs for all 97 allowlist entries. This is cheap and would have caught an off-by-one in the channel field.

### 10.4 Test-quality defects

- **F-19 (Low).** `tests/test_hardware_midi_out.py:18` — `if not self.engine.find_device_id() is not None:` is a double negative (`not (x is not None)`). It works only by accident and reads as its own opposite. Should be `if self.engine.find_device_id() is None:`.
- **F-14 (High).** No prior-state capture/restore; tests silence Main and Ch 1 and leave them there; hardware tests run by default in discovery. (§0.3)
- **F-20 (Low).** `test_hardware_parameter_dispatches` (`:48-86`) has **no assertions whatsoever**. It is a smoke test that passes if WinMM does not throw; it cannot fail on a wrong mapping. Presenting it as "hardware proof" is the root of the over-grading in §8.

### 10.5 Latency — what `<500 µs` actually measures

- **Mechanism:** `t0 = time.perf_counter()` at the top of `execute_command` (`command_boundary.py:106`), `elapsed_us = (time.perf_counter() - t0) * 1e6` at `:228`.
- **Therefore it includes:** allowlist dict lookup, unit conversion, the `midiOutShortMsg` call, and the state-store update plus listener fan-out.
- **It is:** host-side **function execution time**.
- **It is not:** USB transport latency, mixer processing/response latency, or audio round-trip latency.
- **Finding F-21 (High).** `FLOW8_PHASE_C_TEST_RESULTS.md` §3 states "Each hardware transaction completed in < 500 µs **over USB 2.0 WinMM short message interface**". That attributes a host-side stopwatch reading to a USB transport that was never measured. Two specific problems:
  1. `midiOutShortMsg` **queues** the message and returns; the measured interval ends before USB framing completes.
  2. **No test asserts any latency value.** `grep -rn 'latency' tests/` → **no matches**. The figure is not reproducible from the suite; `test_hardware_parameter_engine_dispatch` never reads `entry.latency_us`.
- **Also:** the hardware tests deliberately `time.sleep(0.05)` between every message (`:52-114`), so the achieved end-to-end pacing is ~20 commands/second, i.e. **50 000 µs**, not 500 µs. Any claim that ignores the sleeps misrepresents system behaviour by two orders of magnitude.
- **Action:** rename the field `host_dispatch_us`; delete "over USB 2.0"; never use "round-trip" unless an end-to-end audio measurement exists. If transport latency is wanted, it requires USBPcap; mixer response requires an inbound echo; audio RTT requires a loopback capture.

---

## 11. Required Corrections

Ordered by severity. **None requires re-architecting Phase C.**

### High

| ID | Correction | Files | Action |
|---|---|---|---|
| **F-01** | Do not write commanded state or a "sent" raw value after a failed dispatch | `command_boundary.py:216-254` | Move `set_commanded_value` after a successful send, or write `SyncStatus.FAILED`; set `raw_midi_sent=None` whenever `dispatched_to_hardware is False` |
| **F-04** | Downgrade over-assigned `HARDWARE_TESTED` | `state_model.py:102,115,128,141`; `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` §1–3 | Introduce `API_ACKNOWLEDGED`; re-grade the 4 parameters; remove every "Live Hardware Loopback" citation until a readback test exists; reconcile matrix vs code for `ch1.eq_low` |
| **F-14** | Stop hardware tests from mutating and silencing the mixer | `tests/test_hardware_midi_out.py` | Gate behind `FLOW8_HW_TESTS=1`; snapshot and restore prior values; default to skip |
| **F-18** | Strike the BLE/SysEx claim | `FLOW8_USB_MIDI_PROTOCOL.md:132`; `FLOW8_PARAMETER_VERIFICATION_MATRIX.md:65`; `FLOW8_SPECIFICATION_GAP_ANALYSIS.md:73`; `FLOW8_HARDWARE_DOMAIN_MODEL.md:146` | Reclassify bulk preset transfer as **UNKNOWN / open investigation**; remove "BLE-MIDI" from the GATT diagram label |
| **F-21** | Correct the latency claim | `FLOW8_PHASE_C_TEST_RESULTS.md` §3; `command_boundary.py:40` | Delete "over USB 2.0"; rename to host dispatch duration; state that transport/mixer/audio latency are unmeasured |

### Medium

| ID | Correction | Files | Action |
|---|---|---|---|
| **F-02** | Disambiguate strip index vs physical input number | `parameter_engine.py`; `domain_model.py:55,227-263`; `midi_constants.py:56-58` | Rename to `strip5_6`/`strip7_8`/`usb_bt`, or expose `physical_inputs` and require UI to resolve through it |
| **F-03** | Stereo balance is not distinguishable from pan | `parameter_engine.py:61,211`; `state_model.py:135,178` | Add `set_balance` to stereo input strips; stop writing `parameter_name="pan"` for balance parameters |
| **F-05** | `success=True` for undelivered commands | `command_boundary.py:224-226,244`; `tests/test_parameter_engine.py:158-169` | Rename to `accepted`; add an explicit outcome enum |
| **F-06** | Incorrect parameter counts and unimplemented-but-documented IDs | `FLOW8_PHASE_C_IMPLEMENTATION.md` §3.1; `FLOW8_PARAMETER_CATALOG.md` §2–3 | Fix 83 → **97**; add an "Implemented?" column; mark solo, limiter, GEQ, FX engine, snapshot, tap tempo as NOT IMPLEMENTED |
| **F-15** | Observed-state reconciliation is not implemented | `FLOW8_PARAMETER_VERIFICATION_MATRIX.md` §1; `flow8/midi_in.py` | State explicitly that no inbound CC → `param_id` mapping exists and `SYNCED`/`DIVERGENT` are unreachable |
| **F-16** | Sync would compare engineering units to raw integers | `state_model.py:352,387` | Compare `commanded_raw` vs `observed_raw`; treat engineering units as display only |
| **F-08** | No interlock on phantom writes | `parameter_engine.py:175` | Require UI-level confirmation; exclude phantom from automated runs |
| **M-01** | Chart contradicts the Ch 1–4 gate | `FLOW8_USB_MIDI_PROTOCOL.md` §2 vs §6 | Fix the exception column to "Ch 1–4 only" |
| **M-02** | Compressor on Ch 5/6 unresolved | `domain_model.py:234,247`; `parameter_engine.py:136` | Reclassify as `UNKNOWN` (capability specified, address unverified), not `N/A (REJECTED)`; remove the dead `has_compressor` clause |
| **M-03** | Chart still lists Hi-Z on Ch 3/4 | `FLOW8_USB_MIDI_PROTOCOL.md` §1.1 | Re-issue with a revision and the Hi-Z correction |
| **F-10** | Only 5/97 pairs byte-tested | `tests/test_midi_out.py` | Add a table-driven DWORD test over the full allowlist |

### Low

| ID | Correction | Action |
|---|---|---|
| **F-07** | Transport gate is a superset of the allowlist, undocumented; stale module docstrings (`midi_out.py:5`, `midi_constants.py:3`) | Comment the superset relationship; update docstrings to Phase C |
| **F-09** | Allowlist `min`/`max` never enforced | Enforce, or delete the fields |
| **F-11** | `channel_index` comment says 1..8, only 1–7 exist (`domain_model.py:55`) | Fix comment |
| **F-13** | `Flow8BusStrip.set_fader` conflates master fader and send master | Rename for `fx*` |
| **F-17** | `IMPLEMENTED` and `UNKNOWN` declared but never used | Split implementation status from evidence status |
| **F-19** | Double-negative skip guard (`test_hardware_midi_out.py:18`) | `if self.engine.find_device_id() is None:` |
| **F-20** | Assertion-free "hardware proof" test (`:48-86`) | Add assertions, or relabel as a smoke test |
| **M-04** | "VERIFIED" labels with no citation (`parameter_mapping.py:6-9,22,41,83,192,231`) | Replace with `CHART-MAPPED (uncited)` + per-function citation |
| **M-05** | `main.balance` untested at byte level | Covered by F-10 |

### One correction that is *not* a code change

**Obtain and retain the E0 artifact.** The entire `PROTOCOL_VERIFIED` layer rests on one uncited internal document. Until an official chart revision (or a captured inbound-MIDI trace from the mixer, which would establish semantics at E4) is attached to it, every `PROTOCOL_VERIFIED` grade in the matrix is **UNVERIFIED — internally asserted**. This single action would upgrade 92 parameters at once and is worth more than any code change in this list.

Recommended minimal E4 experiment (not performed in this audit, and outside its read-only mandate): move one physical control at a time on the mixer with `Flow8MidiIn` capturing, and correlate the received `(channel, CC)` with the control touched. That produces exactly the evidence the current suite lacks, and would validate or refute the chart in an afternoon.

---

## 12. Phase D Readiness Decision

### **CONDITIONALLY READY — cleared to start Phase D on the fader/mute/pan/PEQ/send surface only, after the High items are closed.**

**Cleared (architecturally sound, byte encoding proven):**

- The command pipeline, allowlist mechanism, and transport gate are sound and non-bypassable. Phase D can build on them without rework.
- Channel/CC assignment for the 97 implemented parameters is internally consistent across all four layers, and CC conflicts are genuinely resolved by channel addressing with correct status-byte arithmetic.
- Stereo pairs are correctly linked: no path exists to address one side of 5/6 or 7/8 independently.
- Send vs bus-master vs FX-engine addressing is properly separated.
- Verification levels are **not** auto-upgraded by dispatch — the most important invariant for a claims-sensitive system, and it holds in code.

**Blocked until fixed (must not be relied upon by Phase D):**

| Blocker | Why it blocks | Owner action |
|---|---|---|
| **F-02** strip-index naming | A Phase D UI that binds "strip N → `chN`" writes to the wrong physical inputs (ch6 → inputs 7/8) | Rename or expose `physical_inputs` **before** UI binding |
| **F-01** state written after failed send | Phase D's UI state will show values the mixer never received | Fix dispatch ordering |
| **F-05** `success` semantics | Phase D will branch on `.success` and treat offline as delivered | Rename/add outcome enum |
| **F-16** unit-mismatched sync | Bidirectional sync is Phase D-adjacent and would report permanent divergence | Store raw + engineering separately |
| **F-15** no inbound path | Any "reflect the physical mixer" feature is impossible today | Implement CC → `param_id` mapping and wire `set_observed_value` |
| **F-04** over-graded verification | Phase D inherits a matrix that overstates what is proven | Re-grade before Phase D consumes the matrix |
| **M-02** compressor on Ch 5/6 | Phase D cannot render a compressor for stereo pairs on a contradictory specification | Resolve to `UNKNOWN` or find the address |

**Explicitly out of scope for Phase D entry:** FX engine parameters (Ch 14/15), bus limiter and 9-band GEQ, solo, snapshot recall, tap tempo, BLE/SysEx, and audio engine. All are documented but unimplemented, and three of the six have no verified address at all.

**Do not present Phase C as "hardware verified".** The accurate statement is:

> Phase C implements 97 parameter addresses with correct MIDI byte encoding, validated against a single internal protocol chart. 5 of 97 have byte-level test coverage. No parameter has been confirmed by inbound feedback from the mixer, and none has been shown to change mixer state or audible output. Verification levels in the code correctly avoid auto-promotion; the levels **reported in documentation** overstate the evidence for four parameters and for every "Live Hardware Loopback" citation.

---

*End of audit. Read-only. No source file was modified, no new MIDI command was issued outside the test suite the brief required, no firmware was touched, and Phase D was not started.*
