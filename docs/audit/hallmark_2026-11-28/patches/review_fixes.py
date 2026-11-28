import os
os.chdir(r"C:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888\flow8\web_ui\v3")
N = '\r\n'
p = 'v3.js'
s = open(p, 'rb').read().decode('utf-8')


def R(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)


R("shape: 'shelf', c: 'var(--eq)' }," + N + "    { key: 'low_mid'", "shape: 'shelf', c: 'var(--band-1)' }," + N + "    { key: 'low_mid'")
R("label: '300 Hz', shape: 'peak', c: 'var(--eq)' }", "label: '300 Hz', shape: 'peak', c: 'var(--band-2)' }")
R("label: '1.5 kHz', shape: 'peak', c: 'var(--eq)' }", "label: '1.5 kHz', shape: 'peak', c: 'var(--band-3)' }")
R("label: '20 kHz', shape: 'shelf', c: 'var(--eq)' }", "label: '20 kHz', shape: 'shelf', c: 'var(--band-4)' }")
R('<div class="bands">${EQ_BANDS.map((b, k) => `<div class="band">', '<div class="bands">${EQ_BANDS.map((b, k) => `<div class="band" style="--bc:${b.c}">')
R('fill="none" stroke="var(--sel)" stroke-width="3" vector-effect', 'fill="none" stroke="var(--eq)" stroke-width="3" vector-effect')
R("const DB = [-12, -6, 0, 6, 12]; const HZ = [100, 1000, 10000];",
  "const DB = [-12, -6, 0, 6, 12]; const HZ = [100, 1000, 10000];" + N
  + "    const MINOR = [30, 40, 50, 60, 70, 80, 90, 200, 300, 400, 500, 600, 700, 800, 900, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000];" + N
  + "    const LABEL = [50, 100, 200, 500, 1000, 2000, 5000, 10000];")
R("+ HZ.map((hz) => `<line y1=\"0\" y2=\"${H}\" x1=\"${xOf(hz)}\" x2=\"${xOf(hz)}\" stroke=\"var(--line)\" vector-effect=\"non-scaling-stroke\"/>`).join('');",
  "+ HZ.map((hz) => `<line y1=\"0\" y2=\"${H}\" x1=\"${xOf(hz)}\" x2=\"${xOf(hz)}\" stroke=\"var(--line-2)\" vector-effect=\"non-scaling-stroke\"/>`).join('')" + N
  + "      + MINOR.map((hz) => `<line y1=\"0\" y2=\"${H}\" x1=\"${xOf(hz)}\" x2=\"${xOf(hz)}\" stroke=\"var(--line)\" stroke-width=\"0.6\" vector-effect=\"non-scaling-stroke\"/>`).join('');")
R("+ HZ.map((hz) => `<span class=\"ax hz\" style=\"left:${(xOf(hz) / W) * 100}%\">${hz >= 1000 ? `${hz / 1000}k` : hz}</span>`).join('');",
  "+ LABEL.map((hz) => `<span class=\"ax hz${HZ.includes(hz) ? '' : ' minor'}\" style=\"left:${(xOf(hz) / W) * 100}%\">${hz >= 1000 ? `${hz / 1000}k` : hz}</span>`).join('');")
R("""    return known(x.prov) ? `${dbText(x.value)} dB` : `<span class="prov UNSYNCED">UNK</span>`;""",
  """    const badge = (p) => `<span class="prov ${p}" title="${PROV_TIP[p] || ''}">${PROV[p] || p}</span>`;""" + N
  + """    if (known(x.prov)) return `${dbText(x.value)} dB ${badge(x.prov)}`;""" + N
  + """    // An FX mix whose level is unknown shows the preset it holds, when that is known (blueprint rev 7).""" + N
  + """    const fx = m.id.startsWith('fx') && session && (session.fxEngines || {})[m.id];""" + N
  + """    if (fx && known(fx.presetProvenance)) return `${esc(FX_NAMES[m.id][fx.preset - 1] || String(fx.preset))} ${badge(fx.presetProvenance)}`;""" + N
  + """    return badge('UNSYNCED');""")
R("""<span class="bar-fill" style="width:${known(x.prov) ? (x.value / 127) * 100 : 0}%"></span><span>${known(x.prov) ? dbText(x.value) : '--'}</span></div>`;""",
  """<span class="bar-fill" style="width:${known(x.prov) ? (x.value / 127) * 100 : 0}%"></span><b class="prov ${x.prov}" title="${PROV_TIP[x.prov] || ''}">${PROV[x.prov] || x.prov}</b><span>${known(x.prov) ? dbText(x.value) : '--'}</span></div>`;""")
R("""const show = (v) => { cell.classList.remove('unk'); cell.querySelector('.bar-fill').style.width""",
  """const show = (v) => { cell.classList.remove('unk'); const pb = cell.querySelector('.prov'); pb.className = 'prov COMMANDED'; pb.textContent = PROV.COMMANDED; cell.querySelector('.bar-fill').style.width""")
R("stereoLink: 'Stereo link' };", "stereoLink: 'Stereo link', outputPad: 'Output pads', footswitch: 'Foot switch mode', hwSnapshots: 'Mixer memory snapshots' };")
R("`${m.unsetCount} step(s) NOT SET`", "`${m.unsetCount} step${m.unsetCount === 1 ? '' : 's'} NOT SET`")
assert s.count('\r\n') == s.count('\n')
open(p, 'wb').write(s.encode('utf-8'))

p = 'v3.css'
c = open(p, 'rb').read().decode('utf-8')


def C(a, b):
    global c
    assert c.count(a) == 1, (c.count(a), a[:60])
    c = c.replace(a, b)


C("  --eq: #39C9DB;\n", "  --eq: #39C9DB;\n  /* Per-band EQ hues (blueprint rev 7, 0d): only on the EQ graph and the band cards. */\n  --band-1: #46D16A; --band-2: #3B9BF0; --band-3: #B46CE0; --band-4: #E6B83F;\n")
C("--sel-tint: #2A0605; --eq: #FF5A4E;", "--sel-tint: #2A0605; --eq: #FF5A4E; --band-1: #FF7A6E; --band-2: #FF7A6E; --band-3: #FF7A6E; --band-4: #FF7A6E;")
C("border-radius: 50%; border: 2px solid var(--eq); background: var(--raised);", "border-radius: 50%; border: 2px solid var(--bc, var(--eq)); background: var(--raised);")
C("border-radius: 3px; border: 1px solid var(--eq); font-style: normal;", "border-radius: 3px; border: 1px solid var(--bc, var(--eq)); color: var(--bc, var(--ink)); font-style: normal;")
C("background: var(--well); box-shadow: inset 0 3px 0 var(--eq); }", "background: var(--well); box-shadow: inset 0 3px 0 var(--bc, var(--eq)); }")
C(".cuecard.next { border-style: dashed; border-color: var(--line-2); }", ".cuecard.next { border-color: var(--line-2); } /* dashed means unknown in this app; NEXT is a known position */")
c += '''/* Review fixes (pass 2). Unknown slider: no thumb and a dashed edge, so its parked position never reads as a setting. */
input[type="range"].unk-range::-webkit-slider-thumb { visibility: hidden; }
input[type="range"].unk-range::-moz-range-thumb { visibility: hidden; }
input[type="range"].unk-range { outline: 1px dashed var(--ink-3); outline-offset: -18px; border-radius: 2px; }
.knob path { stroke: var(--bc, var(--eq)); }
@media (max-width: 1100px) { .eq-axis .hz.minor { display: none; } }
/* Send cell provenance badge, right-aligned inside the cell. */
.cell .prov { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 12px; z-index: 1; }
.bus small .prov { margin-left: 4px; }
/* Night: selection is an outline on a tint, so the one solid red fill left means MUTED. */
body.night .proc .item[aria-pressed="true"], body.night .tabx, body.night .chrow button[aria-pressed="true"] { background: var(--sel-tint); color: var(--ink); border: 1px solid var(--sel); }
body.night .proc .item[aria-pressed="true"] .ic { color: var(--sel); }
'''
open(p, 'wb').write(c.encode('utf-8'))
print('ok')
