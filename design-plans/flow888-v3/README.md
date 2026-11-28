# FLOW 888 v3: clickable prototype

Status: PROTOTYPE, mock data only. No network code, no MIDI: it cannot reach a mixer.
Open: serve the repository root (`python -m http.server 8866 --bind 127.0.0.1`) and go to
`http://127.0.0.1:8866/design-plans/flow888-v3/index.html`. Built for iPad landscape (1180x820);
works at iPad portrait and phone width.

## Decisions taken without the owner (change any of them)
- The host PC stays the hub (USB MIDI, safety layer, undo, provenance). The new UI is iPad-first.
- No safety lock is lifted. Gain, +48V, mixer snapshots, reset, FX mute and tap tempo stay locked.
- No code or artwork copied from other apps. Only ideas and protocol facts.
- Anything not proven on this mixer is shown as "awaiting hardware test", not as a control.
- Visual world: the owner-approved Night Console tokens (`DESIGN.md`), no glows, no glass.

## What is in it, and where the idea came from
| Page | Feature | Source of the idea |
|---|---|---|
| Mix | Mix selector MAIN / MON 1 / MON 2 / FX 1 / FX 2 (faders show sends) | FLOW 8 Web Remote, ReFlo+, Mixing Station |
| Mix | 4 mute groups, a channel stays muted while any group holds it | ReFlo+ |
| Mix | Relative fader drag (no jump), FINE = quarter travel | Web Remote, ReFlo+ |
| Mix | Provenance on every value: LIVE / SENT / UNKNOWN, unknown = `--` and dashed cap | FLOW 888 (own) |
| Sends | Every channel x every mix in one grid, drag sideways | ReFlo+ sends matrix, Mixing Station routing matrix |
| Channel | EQ graph, gain dots at the manufacturer's fixed centres | ReFlo+, FLOW app complaint "EQ hard to use live" |
| Channel | Presets with a one-line "why"; never level, gain or +48V | CueAir preset notes |
| Output | 9-band GEQ, limiter, delay calculator (calculates only) | ReFlo+ |
| FX | 16 preset names per engine, param 1, variant A/B | Web Remote chart (names as the FLOW app shows them) |
| Show | Cue list with NOW / NEXT, GO opens the change plan, scope chips | CueAir scene cards, theatre cue software |
| My Mon | Musician view: "I am …", own channel first and big, one monitor mix | Allen & Heath Qu-You / ME |
| Safety | Every lock with its reason; open questions marked for test | FLOW 888 (own) |
| Global | NIGHT red-only theme, hold-to LOCK and hold-to MUTE ALL (inputs only, restores) | ReFlo+, existing FLOW 888 |

## Open questions that block real features
1. FX MIDI channels: manual 13/14 vs tested third-party chart 14/15. One controlled test.
2. EQ frequency / Q over CC 21-24 / 31-34: claimed by two apps, contradicts PR #14. One controlled test.
3. Meters over Bluetooth (ReFlo+ says 5 output slots): not used; meters stay on USB audio.
4. Licence: FLOW 8 Web Remote is GPL-3.0, ReFlo+ is closed. Do not copy code from either.

## Next step after the owner reviews this
Pick which pages to wire to the real hub API (`/api/session`, `/api/action`, SSE), page by page,
keeping `Flow8CommandBoundary` as the only path to the mixer.
