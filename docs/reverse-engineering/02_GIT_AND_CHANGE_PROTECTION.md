# Phase 0: Git and Change Protection Protocol

**Document ID:** `02_GIT_AND_CHANGE_PROTECTION`  
**Repository:** `flow888`  
**Policy Enforcement:** STRICT NON-DESTRUCTIVE ENGINEERING

---

## 1. Safety Policies

To prevent regression, data loss, or destabilization of the verified Behringer FLOW 8 mixer codebase, all operations adhere to the following mandatory rules:

1. **Working Tree Isolation:**
   - The primary branch `main` at commit `cc8a59b` represents the verified baseline passing all 303 unit/integration tests.
   - Any speculative or exploratory code must be developed on a dedicated feature branch or staged safely without breaking `main`.
2. **Original Reference Immutability:**
   - The source file `C:\Users\Administrator\Downloads\03 - Software & Installers\CueAir.dmg` (SHA-256: `1D0F9E0DD87A38877204592FC08DC72E6AA76A62C76E85E98021B6A6CDEA41EC`) is treated as strictly read-only.
   - All extractions must target an isolated temporary inspection directory (e.g. `c:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888\cueair_extracted` or inside `.gemini/antigravity/brain`).
3. **No Blind Overwriting:**
   - No existing business logic file (`flow8/*.py`) may be overwritten without inspecting its existing functions and tests first.
   - All new features (e.g. CueAir-inspired workflow enhancements, metering, advanced FX routing) must extend existing interfaces and maintain backward compatibility.
4. **Mandatory Test Verification:**
   - After any modification to the application codebase, the full test suite (`python -m unittest discover -s tests -p "test_*.py"`) must be executed.
   - Zero test regressions are tolerated (all 303 baseline tests must remain green).
5. **Traceable Commit Log:**
   - Every substantive change will be documented in structured commits with explicit rationale, affected components, and test results.

---

## 2. Baseline Verification Checkpoint

```
Branch: main
Head: cc8a59b (feat(ui): scene snapshot bar and thread-safe header connection controls (UI.2-T5))
Working Tree: Clean (untracked rea_setup_output.json only)
Test Suite: 303 tests ran, 298 passed, 5 skipped (hardware-only), 0 failed
CueAir SHA256: 1D0F9E0DD87A38877204592FC08DC72E6AA76A62C76E85E98021B6A6CDEA41EC
```
