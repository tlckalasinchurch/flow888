---
target: web console
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\Administrator\\Desktop\\00 - Projects\\Flow888\\flow888\\flow8\\web_ui\\index.html"
target_fingerprint: "sha256:91abaae3c53f48f80f2ad421ed0e23449466a7d133af19d626a1608904f04a7b"
target_path: "C:\\Users\\Administrator\\Desktop\\00 - Projects\\Flow888\\flow888\\flow8\\web_ui\\index.html"
timestamp: 2026-11-19T14-05-06Z
slug: flow8-web-ui-index-html
---
Method: dual-agent (A: design review, source-only · B: detector + headless Chromium)

Design Health Score 24/40 (Acceptable, 60%). H1 2, H2 3, H3 3, H4 2, H5 2, H6 3, H7 2, H8 2, H9 3, H10 2.

Design specificity: information model authored (provenance, dashed unknown curves, lock chips, hold-to-confirm); visual surface is a generic bevelled pro-audio skin that contradicts DESIGN.md (Flat-At-Rest, No-Blur).

Detector (flow8/web_ui): 189 findings, 5 warnings (cramped-padding, tiny-text, dark-glow, 2 side-tab false positives) and 184 advisories (color 80, font-size 69, radius 35).

Priority issues
- [P1] UNSYNCED strips render invented values as readings (app.js:907, readout "-inf dB" in LED green). Fix: harden.
- [P1] MUTE ALL one-tap, no end-state chip, scrolls off-screen on phone (index.html:70, app.js:2876). Fix: harden.
- [P2] Touch/legibility: 35 of 63 targets under 44px on coarse pointer; 63% of text is 11px or smaller; text-muted 4.41:1 on elevated. Fix: adapt.
- [P2] 9 dead controls, 22 topbar controls, 10 tabs; 5 of 8 cognitive-load items fail. Fix: distill.
- [P2] CSS gradients/glows contradict DESIGN.md; cyan means four things. Fix: quieter.

Personas: Alex (no global shortcuts), Sam (aria-hidden focusable bus tabs, lang=th on English, provenance by colour only), Casey (MUTE ALL off-screen, targets under 44px).
