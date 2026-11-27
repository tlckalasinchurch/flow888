"""UI refinement evidence harness for the FLOW 888 v3 console. No hardware.

Real Flow8LanHub + Flow8Service in this process; MIDI OUT is the repo's fake_open_port fixture.
winmm midiOutOpen / midiInOpen / midiOutShortMsg / midiOutLongMsg are replaced by counters that
raise BEFORE flow8 is imported; the run ends by asserting every counter is 0.

For every page x viewport it saves a screenshot and a metrics record:
  - document / stage horizontal overflow
  - text clipped by its own box (scrollWidth > clientWidth with overflow hidden)
  - visible text under 12 px
  - interactive targets under 44 px (touch viewports) / 24 px (all)
  - text contrast via the ux-ui-audit probe-core.js (contrast block only)
  - page errors

    python -I ui_harness.py before|after
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888")
HERE = Path(__file__).resolve().parent
PROBE = Path(r"C:\Users\Administrator\.claude\plugins\synced\faa6276a-0e3b-4d93-8244-fdcebe4ea899_2dad8a69-6719-4022-86e1-bb692ac6541e\0d07a0ac-4262-4453-bbc9-01ee3cc8d90f\scripts\probe-core.js")
sys.path.insert(0, str(REPO))
for v in ("FLOW8_HW_TESTS", "FLOW8_HW_TESTS_MUTATE"):
    if os.environ.get(v):
        sys.exit(f"REFUSED: {v} is set")

PHYSICAL = []
_winmm = ctypes.windll.winmm


def _deny(name):
    def f(*_a, **_k):
        PHYSICAL.append(name)
        raise AssertionError(f"physical MIDI call attempted: {name}")
    return f


for _n in ("midiOutOpen", "midiInOpen", "midiOutShortMsg", "midiOutLongMsg"):
    setattr(_winmm, _n, _deny(_n))

from playwright.sync_api import sync_playwright  # noqa: E402

from flow8.lan_hub import Flow8LanHub  # noqa: E402
from flow8.service import Flow8Service  # noqa: E402
from tests._safety_helpers import fake_open_port  # noqa: E402

VIEWPORTS = {
    "1440": {"width": 1440, "height": 900, "touch": False},
    "1180": {"width": 1180, "height": 820, "touch": True},
    "1024": {"width": 1024, "height": 768, "touch": True},
    "768": {"width": 768, "height": 1024, "touch": True},
    "390": {"width": 390, "height": 844, "touch": True},
}
# (name, localStorage page, localStorage proc)
PAGES = [
    ("mix-eq", "mix", "eq"), ("mix-source", "mix", "source"), ("mix-comp", "mix", "comp"),
    ("mix-fxsend", "mix", "fxsend"), ("sends", "sends", "eq"), ("channel", "channel", "eq"),
    ("fx", "fx", "eq"), ("stage", "stage", "eq"), ("show", "show", "eq"),
    ("output", "output", "eq"), ("safety", "safety", "eq"),
    ("night-mix-eq", "mix", "eq"), ("night-show", "show", "eq"), ("night-output", "output", "eq"),
]

METRICS_JS = r"""
(touch) => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const name = (el) => (el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')) + ' "' + (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24) + '"';
  const out = { docOverflowX: document.documentElement.scrollWidth - innerWidth, stageOverflowX: 0, clipped: [], small: [], targets44: [], targets24: [] };
  const st = document.querySelector('#stage'); if (st) out.stageOverflowX = st.scrollWidth - st.clientWidth;
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue;
    const s = getComputedStyle(el);
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (ownText && parseFloat(s.fontSize) < 12 && !el.closest('svg')) out.small.push(name(el) + ' ' + s.fontSize);
    if (ownText && (s.overflow === 'hidden' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1) out.clipped.push(name(el));
  }
  for (const el of document.querySelectorAll('button, [role=slider], [role=button], input, a[href], select')) {
    if (!vis(el) || el.closest('[hidden]')) continue;
    const r = el.getBoundingClientRect();
    if (el.type === 'range') continue; // native range: the 44 px row height is the target
    if (touch && (r.width < 44 || r.height < 44)) out.targets44.push(name(el) + ` ${Math.round(r.width)}x${Math.round(r.height)}`);
    if (r.width < 24 || r.height < 24) out.targets24.push(name(el) + ` ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  return out;
}
"""


def seed(hub, service, cues=True):
    """A realistic mid-soundcheck state: some values COMMANDED, the rest left UNSYNCED."""
    d = hub.dispatch_action
    for ch, v in ((1, 101), (2, 96), (3, 88), (4, 101)):
        d({"action": "setFader", "channel": ch, "value": v})
    d({"action": "setFader", "channel": 8, "value": 101})
    d({"action": "setMute", "channel": 3, "value": True})
    d({"action": "setMute", "channel": 1, "value": False})
    for band, raw in (("low", 58), ("low_mid", 70), ("hi_mid", 72), ("hi", 64)):
        d({"action": "setEqBand", "channel": 1, "band": band, "value": raw, "unit": "raw"})
    d({"action": "setSend", "channel": 1, "target": "mon1", "value": 90, "unit": "raw"})
    d({"action": "setLowCut", "channel": 1, "value": 30, "unit": "raw"})
    d({"action": "setCompressor", "channel": 1, "value": 40, "unit": "raw"})
    d({"action": "setBusGeq", "bus": "main", "band": 3, "value": 58})
    d({"action": "setFxPreset", "engine": "fx1", "value": 9})
    if cues:
        d({"action": "librarySave", "name": "Worship set"})
        d({"action": "librarySave", "name": "Sermon"})


def main(label):
    out = HERE / label
    out.mkdir(parents=True, exist_ok=True)
    service = Flow8Service(auto_connect=False)
    _, driver = fake_open_port(service.midi_out)
    mi = service.midi_in
    mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
    service._connected = True
    hub = Flow8LanHub(service, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
    port = hub.start()
    base = f"http://127.0.0.1:{port}/v3/"
    seed(hub, service)
    probe = PROBE.read_text(encoding="utf-8")
    report = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for vname, vp in VIEWPORTS.items():
                ctx = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]}, has_touch=vp["touch"], is_mobile=False)
                for pname, page_key, proc in PAGES + [("mix-offline", "mix", "eq")]:
                    if pname == "mix-offline":
                        service.midi_out._is_open = False
                        service._connected = False
                        service.reconcile_connection()  # the real unplug path: every value back to UNSYNCED
                    pg = ctx.new_page()
                    errors = []
                    pg.on("pageerror", lambda e: errors.append(str(e)))
                    pg.add_init_script(f"localStorage.setItem('flow888.v3.page', JSON.stringify('{page_key}'));"
                                       f"localStorage.setItem('flow888.v3.proc', JSON.stringify('{proc}'));"
                                       f"localStorage.setItem('flow888.v3.night', JSON.stringify({str(pname.startswith('night')).lower()}));")
                    pg.goto(base)
                    pg.wait_for_selector(".page > *", timeout=8000)
                    pg.wait_for_timeout(500)
                    pg.screenshot(path=str(out / f"{vname}-{pname}.png"))
                    m = pg.evaluate(METRICS_JS, vp["touch"])
                    try:
                        core = json.loads(pg.evaluate(probe))
                        con = core.get("contrast") or {}
                        m["contrastFails"] = (con.get("failures") or con.get("fails") or [])[:15]
                        m["contrastSummary"] = {k: v for k, v in con.items() if not isinstance(v, list)}
                    except Exception as exc:  # the probe is a lead list; record and carry on
                        m["probeError"] = str(exc)[:200]
                    m["errors"] = errors
                    report[f"{vname}/{pname}"] = m
                    pg.close()
                    if pname == "mix-offline":
                        service.midi_out._is_open = True
                        service._connected = True
                        seed(hub, service, cues=False)  # values are UNSYNCED after a reconnect; re-send for the next viewport
                ctx.close()
            browser.close()
    finally:
        hub.stop()
    report["_physicalMidiCalls"] = PHYSICAL
    (out / "metrics.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    assert not PHYSICAL, PHYSICAL
    print("OK", label, len(report) - 1, "captures; physical MIDI calls:", len(PHYSICAL))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "before")
