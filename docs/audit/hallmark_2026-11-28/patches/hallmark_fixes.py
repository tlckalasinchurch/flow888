import os
import re
os.chdir(r"C:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888\flow8\web_ui\v3")

# ---------------- CSS ----------------
p = 'v3.css'
c = open(p, 'rb').read().decode('utf-8')


def C(a, b, n=1):
    global c
    assert c.count(a) == n, (c.count(a), a[:70])
    c = c.replace(a, b)


STAMP = ("/* Hallmark · checked: 2026-11-28 · genre: modern-minimal (inferred) · shape: app screen\n"
         " * fixed: 73 (stale fader geometry), 40, 39a, 49a, 34, 48 (literals; night palette moved to a :root theme block), 67 (tracking capped at 0.04em), F3, F23\n"
         " * kept by owner decision, reported not waived (Floor): 67 uppercase hardware labels (rev 7 reference, mixer silkscreen) · 48 none left\n"
         " * built: the project · redesign: polish · v2.0.0 */\n")
c = STAMP + c

# Night palette is a declared theme block on :root (the script sets data-theme), not a body class.
C("/* Night: one hue, red, at low luminance. Kept as variables so every state still differs by weight and form. */\nbody.night {",
  "/* Night: one hue, red, at low luminance. Kept as variables so every state still differs by weight and form.\n   Declared on :root[data-theme] so it is a theme block; body.night still scopes the few component overrides. */\n:root[data-theme=\"night\"] {")
# Literal colours left outside the tokens.
C("  --font: \"Barlow Condensed\",",
  "  --shadow-float: 0 8px 24px rgba(0, 0, 0, 0.5); --shadow-cap: inset 0 -2px 0 rgba(0, 0, 0, 0.25); --mask-on: #000; --on-red: #08090A;\n  --font: \"Barlow Condensed\",")
C("box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); }", "box-shadow: var(--shadow-float); }")
C("box-shadow: inset 0 -2px 0 rgba(0,0,0,0.25); }", "box-shadow: var(--shadow-cap); }")
C("-webkit-mask: repeating-linear-gradient(0deg, #000 0 4px, transparent 4px 6px); mask: repeating-linear-gradient(0deg, #000 0 4px, transparent 4px 6px);",
  "-webkit-mask: repeating-linear-gradient(0deg, var(--mask-on) 0 4px, transparent 4px 6px); mask: repeating-linear-gradient(0deg, var(--mask-on) 0 4px, transparent 4px 6px);")
# 40: white on red MUTED was 3.92:1.
C('.s-mute[aria-pressed="true"] { background: var(--red); border-color: var(--red); color: #fff; }',
  '.s-mute[aria-pressed="true"] { background: var(--red); border-color: var(--red); color: var(--on-red); }')
# 34: the app shell clips, it never scrolls the page.
C("body { overflow: hidden; -webkit-user-select: none;", "html, body { overflow: clip; }\nbody { -webkit-user-select: none;")
# 39a: three disabled channels.
C(".go:disabled { opacity: 0.5; cursor: default; }",
  ".go:disabled { opacity: 0.5; cursor: not-allowed; color: var(--ink-3); border-color: var(--line); background: var(--panel); }")
# 67: uppercase stays (hardware labels); tracking capped at 0.04em. The brand tagline is part of the wordmark.
n0 = len(re.findall(r"letter-spacing: 0\.(0[5-9]|1[0-9])em", c))
c = re.sub(r"(?<!\.brand small \{ font-size: 12px; font-weight: 700; color: var\(--ink-3\); )letter-spacing: 0\.(0[5-9]|1[0-3])em", "letter-spacing: 0.04em", c)
print("tracking capped:", n0, "->", len(re.findall(r"letter-spacing: 0\.(0[5-9]|1[0-9])em", c)))
c += '''/* Hallmark pass: labels never wrap on a 320 px phone; heads balance. */
.tabs button, .proc .item, .mixes button, .bus b { white-space: nowrap; }
h1, h2 { text-wrap: balance; }
'''
open(p, 'wb').write(c.encode('utf-8'))

# ---------------- JS ----------------
N = '\r\n'
p = 'v3.js'
s = open(p, 'rb').read().decode('utf-8')


def R(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)


# 73: a fader repaints whenever its well changes size (window resize before the debounced render,
# a late web-font swap, the offline banner). One shared observer, emptied on every render.
R("  function fader(get, cmd, label, id) {",
  "  // A fader repaints whenever its well changes size (resize before the debounced render, a late" + N
  + "  // font swap, the offline banner); before this, caps kept stale positions until the next render." + N
  + "  const faderSizes = typeof ResizeObserver === 'function' ? new ResizeObserver((es) => es.forEach((e) => e.target.paint && e.target.paint())) : null;" + N
  + "  function fader(get, cmd, label, id) {")
R("    requestAnimationFrame(paint);" + N + "    return wrap;",
  "    wrap.paint = paint;" + N + "    if (faderSizes) faderSizes.observe(wrap);" + N + "    requestAnimationFrame(paint);" + N + "    return wrap;")
R("    stage.innerHTML = '<div class=\"page\"></div>';",
  "    if (faderSizes) faderSizes.disconnect(); // the old wells are about to go" + N + "    stage.innerHTML = '<div class=\"page\"></div>';")
R("  const applyNight = () => { document.body.classList.toggle('night', ui.night);",
  "  const applyNight = () => { document.body.classList.toggle('night', ui.night); if (ui.night) document.documentElement.setAttribute('data-theme', 'night'); else document.documentElement.removeAttribute('data-theme');")
assert s.count('\r\n') == s.count('\n')
open(p, 'wb').write(s.encode('utf-8'))

# ---------------- HTML ----------------
p = 'index.html'
h = open(p, 'rb').read().decode('utf-8')
a = '<title>FLOW 888</title>'
assert h.count(a) == 1
h = h.replace(a, a + '\n<meta name="description" content="FLOW 888 live console for the Behringer FLOW 8 mixer: faders, mutes, EQ, sends, FX and cues over the venue network." />')
open(p, 'wb').write(h.encode('utf-8'))
print('ok')
