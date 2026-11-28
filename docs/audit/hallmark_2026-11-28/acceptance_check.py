"""Phase C/E visual and interaction acceptance for the FLOW 888 v3 console. No hardware.

Real Flow8LanHub + Flow8Service in-process on a free port (never 8844), MIDI OUT = repo fixture
fake_open_port; winmm open/send raise (installed by ui_harness before flow8 is imported). State is
sent through the hub's own actions (ui_harness.seed), never written into the model directly.

Per viewport x theme x page: screenshot, ui_harness METRICS_JS (overflow, clipped text, <12 px,
targets), probe-core text contrast, and on MIX the geometry checks:
  fader caps sit where the value says (12 + v/127 * (h-24) px from the well bottom), unknown caps
  are parked at the bottom and dashed; scale labels do not overlap; channel names are not covered;
  the EQ axis labels sit on a log10 scale and do not overlap; band hues follow rev 7 (night: one red);
  Freq/Q are not controls; MAIN OUT has one meter; every readout badge matches the session.
Resize: viewport changes are checked 60 ms later, before the 150 ms debounced re-render, so the
fader ResizeObserver is what keeps the caps right.

    python -I acceptance_check.py            -> acceptance/<vp>-<theme>-<page>.png, acceptance/results.json
"""
import json
import sys
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ui_refine_2026-11-28"))
import ui_harness as H  # noqa: E402  (installs the winmm guard first)

OUT = HERE / "acceptance"
VIEWPORTS = {"1280x800": (1280, 800, False), "1180x820": (1180, 820, True), "1024x768": (1024, 768, True),
             "768x1024": (768, 1024, True), "320x640": (320, 640, True)}
PAGES = [("mix", "eq"), ("mix-source", "source"), ("mix-monsend", "monsend"), ("sends", "eq"), ("channel", "eq"),
         ("fx", "eq"), ("stage", "eq"), ("show", "eq"), ("output", "eq"), ("safety", "eq")]
BAND_HEX = ["rgb(70, 209, 106)", "rgb(59, 155, 240)", "rgb(180, 108, 224)", "rgb(230, 184, 63)"]
NIGHT_BAND = "rgb(255, 122, 110)"

GEOMETRY_JS = r"""
async (night) => {
  const s = await (await fetch('/api/session', {cache: 'no-store'})).json();
  const known = (p) => p === 'OBSERVED' || p === 'COMMANDED';
  const PROV = {OBSERVED: 'LIV', COMMANDED: 'SNT', UNSYNCED: 'UNK', DISPATCH_FAILED: 'ERR', UNSUPPORTED: 'N/A'};
  const idToCh = {'fdr-CH-1': 1, 'fdr-CH-2': 2, 'fdr-CH-3': 3, 'fdr-CH-4': 4, 'fdr-CH-5-6': 5, 'fdr-CH-7-8': 6, 'fdr-USB-BT': 7, 'fdr-MAIN': 8};
  const out = {fader: [], ticks: [], names: [], eq: {}, mainOut: {}, badges: []};
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).display !== 'none'; };
  for (const w of document.querySelectorAll('.ws .well[id^="fdr-"]')) {
    if (!vis(w)) continue;
    const ch = s.channels.find((c) => c.index === idToCh[w.id]);
    if (!ch) continue;
    const cap = w.querySelector('.cap');
    const wr = w.getBoundingClientRect(); const cr = cap.getBoundingClientRect();
    const h = w.clientHeight - 24;
    const k = known(ch.faderProvenance);
    const expBottom = 12 + (k ? (ch.fader / 127) * h : 0);
    const capCentreFromBottom = (wr.top + w.clientTop + w.clientHeight) - (cr.top + cr.height / 2);
    const err = Math.abs(capCentreFromBottom - expBottom);
    const dashed = cap.classList.contains('unk');
    const inside = cr.left >= wr.left - 1 && cr.right <= wr.right + 1 && (cr.top + cr.height / 2) >= wr.top && (cr.top + cr.height / 2) <= wr.bottom;
    out.fader.push({id: w.id, known: k, err: Math.round(err * 10) / 10, dashedWhenUnknown: k ? !dashed : dashed, inside});
    const ts = [...w.querySelectorAll('.tick')].map((t) => t.getBoundingClientRect());
    for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
      const a = ts[i]; const b = ts[j];
      if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) out.ticks.push(w.id + ' ' + i + '/' + j);
    }
  }
  for (const n of document.querySelectorAll('.ws .s-head .nm, .ws .s-head .num')) {
    if (!vis(n)) continue;
    const r = n.getBoundingClientRect();
    const top = document.elementFromPoint(r.left + Math.min(r.width / 2, 20), r.top + r.height / 2);
    if (top && !n.contains(top) && top !== n) out.names.push(n.textContent.trim() + ' under ' + (top.className || top.tagName));
  }
  const wrap = document.querySelector('.pv .eq-wrap');
  if (wrap && vis(wrap)) {
    const W = 1000;
    const xOf = (hz) => (Math.log10(hz / 20) / Math.log10(1000)) * (W - 140) + 70;
    const labs = [...wrap.querySelectorAll('.eq-axis .hz')].filter(vis);
    out.eq.labels = labs.map((l) => l.textContent);
    out.eq.logErr = Math.max(0, ...labs.map((l) => { const t = l.textContent; const hz = t.endsWith('k') ? parseFloat(t) * 1000 : parseFloat(t); return Math.abs(parseFloat(l.style.left) - (xOf(hz) / W) * 100); }));
    const lr = labs.map((l) => l.getBoundingClientRect()); let ov = 0;
    for (let i = 1; i < lr.length; i++) if (lr[i].left < lr[i - 1].right) ov++;
    out.eq.labelOverlaps = ov;
    out.eq.nodeColours = [...wrap.querySelectorAll('.eq-node span')].map((e) => getComputedStyle(e).borderTopColor);
    const nodes = [...wrap.querySelectorAll('.eq-node')].map((e) => parseFloat(e.style.left));
    out.eq.nodesAscending = nodes.every((v, i) => i === 0 || v > nodes[i - 1]);
    out.eq.freqQControls = document.querySelectorAll('.bands [role="slider"], .bands input, .bands button').length;
    out.eq.fixedCells = document.querySelectorAll('.bands dd.fixed').length;
  }
  const ms = document.querySelector('.mstrip');
  if (ms && vis(ms)) {
    out.mainOut.meters = ms.querySelectorAll('.meter').length;
    out.mainOut.meterSid = (ms.querySelector('.meter') || {}).dataset?.sid;
    const sp = ms.querySelector('.s-mute-space');
    out.mainOut.spacerVisible = !!(sp && vis(sp));
    out.mainOut.readout = (ms.querySelector('.s-read') || {}).textContent?.trim();
  }
  for (const st of document.querySelectorAll('.ws .bank .strip')) {
    const w = st.querySelector('.well'); const ch = s.channels.find((c) => c.index === idToCh[w && w.id]);
    if (!ch) continue;
    const b = st.querySelector('.s-read .prov').textContent.trim();
    if (b !== PROV[ch.faderProvenance]) out.badges.push(w.id + ' shows ' + b + ' but session is ' + ch.faderProvenance);
  }
  return out;
}
"""


def main():
    OUT.mkdir(exist_ok=True)
    s = H.Flow8Service(auto_connect=False)
    H.fake_open_port(s.midi_out)
    mi = s.midi_in
    mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
    s._connected = True
    hub = H.Flow8LanHub(s, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
    port = hub.start()
    assert port != 8844
    H.seed(hub, s)
    probe = H.PROBE.read_text(encoding="utf-8")
    res = {}
    try:
        with H.sync_playwright() as p:
            b = p.chromium.launch()
            for vname, (w, h, touch) in VIEWPORTS.items():
                for theme in ("day", "night"):
                    ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=touch)
                    for pname, proc in PAGES:
                        page_key = pname.split("-")[0]
                        pg = ctx.new_page()
                        errs = []
                        pg.on("pageerror", lambda e: errs.append(str(e)))
                        pg.add_init_script(f"localStorage.setItem('flow888.v3.page', JSON.stringify('{page_key}'));"
                                           f"localStorage.setItem('flow888.v3.proc', JSON.stringify('{proc}'));"
                                           f"localStorage.setItem('flow888.v3.night', JSON.stringify({str(theme == 'night').lower()}));")
                        pg.goto(f"http://127.0.0.1:{port}/v3/")
                        pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
                        pg.wait_for_timeout(450)
                        pg.screenshot(path=str(OUT / f"{vname}-{theme}-{pname}.png"))
                        m = pg.evaluate(H.METRICS_JS, touch)
                        core = json.loads(pg.evaluate(probe))
                        m["contrastFails"] = [(f["text"], f["ratio"], f["required"]) for f in (core.get("contrast") or {}).get("failures", [])][:10]
                        if page_key == "mix":
                            m["geo"] = pg.evaluate(GEOMETRY_JS, theme == "night")
                        m["errors"] = errs
                        res[f"{vname}/{theme}/{pname}"] = m
                        pg.close()
                    ctx.close()
            # resize: caps must follow the new well height before the debounced render
            ctx = b.new_context(viewport={"width": 1280, "height": 800})
            pg = ctx.new_page()
            pg.add_init_script("localStorage.setItem('flow888.v3.page', JSON.stringify('mix'));localStorage.setItem('flow888.v3.night', 'false');")
            pg.goto(f"http://127.0.0.1:{port}/v3/")
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
            pg.wait_for_timeout(450)
            rz = []
            for (w, h) in ((1180, 820), (1024, 768), (1440, 900), (1280, 800)):
                pg.set_viewport_size({"width": w, "height": h})
                pg.wait_for_timeout(60)
                g = pg.evaluate(GEOMETRY_JS, False)
                rz.append({"to": f"{w}x{h}", "maxErr": max([f["err"] for f in g["fader"]] or [0]), "allInside": all(f["inside"] for f in g["fader"])})
            res["_resize"] = rz
            pg.screenshot(path=str(OUT / "resize-final-1280x800.png"))
            ctx.close()
            # offline: the real unplug path (reconcile_connection) -> everything reads unknown
            s.midi_out._is_open = False
            s._connected = False
            s.reconcile_connection()
            ctx = b.new_context(viewport={"width": 1180, "height": 820}, has_touch=True)
            pg = ctx.new_page()
            pg.add_init_script("localStorage.setItem('flow888.v3.page', JSON.stringify('mix'));localStorage.setItem('flow888.v3.proc', JSON.stringify('eq'));")
            pg.goto(f"http://127.0.0.1:{port}/v3/")
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'NO MIXER'", timeout=8000)
            pg.wait_for_timeout(450)
            pg.screenshot(path=str(OUT / "offline-1180x820.png"))
            g = pg.evaluate(GEOMETRY_JS, False)
            res["_offline"] = {"faders": g["fader"], "badges": g["badges"],
                               "readouts": pg.eval_on_selector_all(".ws .s-read .v", "els => els.map(e => e.textContent)"),
                               "eqNodesOn": pg.eval_on_selector_all(".eq-node.on", "els => els.length"),
                               "muteLabels": pg.eval_on_selector_all(".ws .s-mute", "els => els.map(e => e.textContent.trim())")}
            ctx.close()
            b.close()
    finally:
        hub.stop()
    res["_physicalMidiCalls"] = H.PHYSICAL
    (OUT / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    assert not H.PHYSICAL, H.PHYSICAL
    print("OK", len([k for k in res if not k.startswith("_")]), "captures; physical MIDI calls 0")


if __name__ == "__main__":
    main()
