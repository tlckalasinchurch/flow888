# FLOW 888 v3 — Hallmark AI-slop audit and polish (2026-11-28)

## 1. Installation
- `npx -y skills add nutlope/hallmark -g -y`: **installed** for Claude Code (`~/.agents/skills/hallmark`, symlinked into `~/.claude/skills`), Hallmark **v2.0.0**. Lock entry: source `Nutlope/hallmark` (github). The run reported one failure for an unrelated target ("PromptScript does not support global skill installation"); Claude Code is unaffected.
- A copy was already installed (2026-11-13); the command refreshed it from the same source.
- Commands, verified from `SKILL.md` and `references/redesign.md`: `<prompt>` (build), `redesign <path>` (full / restyle / polish depth), `audit <path>` (report only). Tooling: `scripts/sloplint.mjs` (`--genre`, `--scope page|component|app`, `--render`, `--url`, `--before`, `--kept`), `scripts/theme.mjs` (deal, draw, scaffold, photos, log).
- The render tier needs `puppeteer-core`. It was installed into the session scratchpad only (not the project) and used with the Playwright Chromium (`HALLMARK_PUPPETEER`, `CHROME_PATH`). No project dependency was added.

## 2. Baseline (`sloplint --scope app --render --before`)
**74 FAIL · 88 REFLEX · 12 WARN** (`before.txt`, `before_console.txt`, screenshots in `before_url/`). Genre inferred: modern-minimal (a professional tool); scope: app screen.

| Gate | Count | Finding | Classification |
|---|---|---|---|
| 73 | 1 | Fader caps painted over channel names; at 1280×800 caps sat under the wells and the scale labels piled at the top (`before_url/…1280x800.png`) | **Genuine UX defect**: `fader().paint()` measured the well once; a resize, font swap or the offline banner left caps stale until the next 5 s render |
| 40 | 1 | White on red MUTED, 3.92:1 | **Genuine** (contrast) |
| 39a | 1 | GO button disabled by opacity alone | **Genuine** (state) |
| 49a | 3 | `MY MON`, `MON SEND` wrap at 320 px (URL render) | **Genuine** (responsive). `MUTE ALL` at 375 came from the CSS-less disk render: **false positive** |
| 34 | 2 | `overflow: hidden` on body | **Genuine** (Floor: `clip`). 320 px scroll on the disk render: **false positive** (no stylesheet loaded) |
| 48 | 49 | Colour literals outside tokens: 44 in the night palette (`body.night` is not a recognised theme block), plus shadows, a mask and `#fff` | **Visual consistency**: fixed by moving night to `:root[data-theme="night"]` and tokenising the rest |
| 67 | 17 | Uppercase / tracked labels | **Intentional hardware convention** (mixer silkscreen, rev 7 reference, your instruction). Tracking past 0.04em capped; the uppercase stays |
| 24b | 85 | Spacing off the 4 px scale | **Intentional**: DESIGN.md's own scale is 4/6/14/16. Reported as NOTE under the polish stamp |
| 62 | 1 | Unknown slider thumb hidden "until a script shows it" | **False positive**: an unknown-value state (Unknown-Reads-Unknown), not a reveal; the whole console renders from its script |
| 72 | 1 | Cramped `.btn` text | **False positive**: measured on the disk render without CSS |
| 38iii | 1 | `.page-head h1 i` set apart | **Intentional**: the Thai page name beside the English one (bilingual heading), not an accent word |
| 39b | 1 | Strip head 57 px tall | **Intentional**: two-line channel head (number and name) |
| 41 | 5 | Dark panels set no text colour | **False positive**: text inherits `--ink` from body in both themes (contrast measured 0 failures) |
| F3, F23 | 2 | No `text-wrap: balance`; no meta description | **Finish**: fixed |
| F7, F19, F24 | 3 | One well recipe; 4 weights; border plus shadow on the menu | **Answered** in the stamp (console wells, bundled font files, the one floating menu) |
| render | 1 | "Fallback font" | **False positive**: the disk render cannot resolve `/v3/v3.css`; the URL render loads the fonts |

## 3. Files changed (UI only)
- `flow8/web_ui/v3/v3.js`: one shared `ResizeObserver` repaints each fader when its well changes size, emptied on every render (73); night mode also sets `data-theme="night"` on `<html>`.
- `flow8/web_ui/v3/v3.css`: Hallmark check stamp plus answers; night palette on `:root[data-theme="night"]`; tokens `--shadow-float`, `--shadow-cap`, `--mask-on`, `--on-red`; `overflow: clip`; MUTED ink; GO disabled state; tracking capped at 0.04em on 11 rules; nowrap on tabs, processor items, mix buttons and mix names; `text-wrap: balance` on headings.
- `flow8/web_ui/v3/index.html`: meta description.
- No test, Python, MIDI, transport, BLE, safety or hub file was touched (modification times: every backend and existing test file is unchanged since 2026-11-27 21:32 or earlier).

## 4. After (`sloplint --scope app --render`, live URL)
**15 FAIL · 2 REFLEX · 0 WARN · 3 ANSWERED · 5 DISMISSED · 85 NOTE** (`final_console.txt`, `after_url/`).

The 15 FAILs left are 14 × gate 67 (uppercase hardware labels, kept on your instruction; Hallmark rejects Floor waivers, so they stay on the record) and 1 × gate 62 (false positive, above). The 2 REFLEX are 38iii and 39b (intentional, above). Before → after: **74 → 15 FAIL, 88 → 2 REFLEX, 12 → 0 WARN.**

## 5. Verification
| Check | Result | Status |
|---|---|---|
| MIDI payloads (`ui_refine_2026-11-28/payload_check.py`): keyboard, mouse drag, mute toggle ×2, send cell, FX preset and variant, GEQ, touch mute | 12 commands → 12 MIDI messages, **identical before and after** (and deterministic across two baseline runs); 0 physical calls | TEST VERIFIED |
| Full suite `tools.run_tests_no_hw` | 533 ran, **528 passed, 0 failed**, 5 hardware skips, 0 physical port opens | TEST VERIFIED |
| 75 captures (1440, 1180, 1024, 768, 390; day and night) | contrast failures **0** (night 0), text < 12 px 0, page errors 0; stage overflow only on 390 SENDS (deliberate sideways scroll) | VISUAL VERIFIED |
| Fader geometry at 1280×800 (Hallmark render) | caps in their wells, scales spread (`after_url/…1280x800.png`) | VISUAL VERIFIED |
| Interaction | keyboard step `-69.3 SNT`; drag `beginGesture, setFader×2, endGesture`; hover border `#92999C`, selected keeps teal; touch tap on a group 84×44 opens the editor | TEST VERIFIED |
| Hardware | No FLOW 8 connected | **NOT VERIFIED** |
