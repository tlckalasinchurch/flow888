"""Phase 2 Playwright integration audit for the FLOW 8 v3 console. No hardware.

Real Flow8LanHub + Flow8Service in this process. MIDI OUT is the repo's fake_open_port
fixture (MagicMock driver). winmm midiOutOpen / midiInOpen / midiOutShortMsg / midiOutLongMsg
are replaced by counters that raise, BEFORE flow8 is imported; the run ends by asserting
every counter is 0. Library and show modes are in memory (paths None).

    python -I harness.py            # both viewports
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\00 - Projects\Flow888\flow888")
OUT = Path(__file__).resolve().parent / "evidence"
sys.path.insert(0, str(REPO))
for v in ("FLOW8_HW_TESTS", "FLOW8_HW_TESTS_MUTATE"):
    if os.environ.get(v):
        sys.exit(f"REFUSED: {v} is set")

# ---- hardware guard, before any flow8 import ----
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
from flow8.midi_constants import MIM_DATA  # noqa: E402
from flow8.service import Flow8Service  # noqa: E402
from tests._safety_helpers import fake_open_port  # noqa: E402

VIEWPORTS = {"desktop": {"width": 1366, "height": 768}, "ipad": {"width": 1024, "height": 768}}


def decode(dword):
    status, d1, d2 = dword & 0xFF, (dword >> 8) & 0xFF, (dword >> 16) & 0xFF
    kind = {0xB0: "CC", 0xC0: "PC"}.get(status & 0xF0, hex(status & 0xF0))
    return {"kind": kind, "ch": (status & 0x0F) + 1, "d1": d1, "d2": d2}


class Rig:
    def __init__(self):
        self.service = Flow8Service(auto_connect=False)
        _, self.driver = fake_open_port(self.service.midi_out)
        mi = self.service.midi_in
        mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True  # fake, no winmm
        self.service._connected = True
        mi.register_callback(self.service._on_midi_in_event)  # what connect() does; no port is opened
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
        self.port = self.hub.start()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log = []
        orig = self.hub.dispatch_action

        def recorder(msg):
            before = len(self.driver.midiOutShortMsg.call_args_list)
            code, res = orig(msg)
            calls = self.driver.midiOutShortMsg.call_args_list[before:]
            self.log.append({"t": round(time.monotonic(), 3), "msg": {k: v for k, v in msg.items() if k != "clientId"},
                             "code": code, "ok": res.get("ok", code == 200) if isinstance(res, dict) else None,
                             "error": res.get("error") if isinstance(res, dict) else None,
                             "midi": [decode(c.args[1]) for c in calls]})
            return code, res
        self.hub.dispatch_action = recorder

    def set_connected(self, up: bool):
        self.service.midi_out._is_open = up
        self.service._connected = up

    def mark(self):
        return len(self.log)

    def since(self, m, action=None):
        return [e for e in self.log[m:] if action is None or e["msg"].get("action") == action]

    def stop(self):
        self.hub.stop()


class Audit:
    def __init__(self, vp_name, page, rig, ctx):
        self.vp, self.page, self.rig, self.ctx = vp_name, page, rig, ctx
        self.dir = OUT / vp_name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.console, self.pageerrors, self.failed, self.http = [], [], [], []
        self.watch(page)

    def watch(self, page):
        page.on("console", lambda m: self.console.append({"type": m.type, "text": m.text}) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: self.pageerrors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed.append({"url": r.url, "err": r.failure}))
        page.on("response", lambda r: self.http.append({"url": r.url.replace(self.rig.base, ""), "status": r.status,
                                                         "method": r.request.method,
                                                         "body": r.request.post_data if r.request.method == "POST" else None}))

    def shot(self, name, page=None):
        p = self.dir / f"{name}.png"
        (page or self.page).screenshot(path=str(p), full_page=False)
        return str(p)

    def record(self, sid, title, status, expected, actual, evidence=None, extra=None):
        r = {"id": sid, "viewport": self.vp, "title": title, "status": status, "expected": expected,
             "actual": actual, "evidence": evidence or [], **(extra or {})}
        self.results.append(r)
        print(f"[{self.vp}] {sid} {status}: {title} | actual: {actual}", flush=True)

    # ---------- helpers ----------
    def goto_page(self, name):
        self.page.click(f'#rail button[data-page="{name}"]')
        self.page.wait_for_timeout(250)

    def ready(self):
        self.page.wait_for_function("document.querySelector('#link .tx') && document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)

    def drag(self, selector, dx=0, dy=0, steps=8, hold_ms=0, mid=None, nth=0):
        loc = self.page.locator(selector).nth(nth)
        box = None
        for _ in range(5):  # the page may re-render between locate and measure
            loc.wait_for(state="visible", timeout=5000)
            box = loc.bounding_box()
            if box:
                break
            self.page.wait_for_timeout(150)
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        for i in range(1, steps + 1):
            self.page.mouse.move(x + dx * i / steps / 2, y + dy * i / steps / 2)
            self.page.wait_for_timeout(30)
        if mid:
            mid()
        if hold_ms:
            self.page.wait_for_timeout(hold_ms)
        for i in range(1, steps + 1):
            self.page.mouse.move(x + dx / 2 + dx * i / steps / 2, y + dy / 2 + dy * i / steps / 2)
            self.page.wait_for_timeout(30)
        self.page.mouse.up()
        self.page.wait_for_timeout(400)

    def hold(self, selector, ms):
        box = self.page.locator(selector).bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.page.wait_for_timeout(ms)
        self.page.mouse.up()
        self.page.wait_for_timeout(300)

    def rerender_from_other_client(self):
        """What another device's command does: a state event, then this client's 120 ms reload."""
        self.rig.hub.broadcast({"type": "state"})
        self.page.wait_for_timeout(450)

    def overflow(self):
        return self.page.evaluate("[document.scrollingElement.scrollWidth, document.scrollingElement.clientWidth]")


# ================= S-tests =================
def s1(a: Audit):
    """Range input dragged while the page re-renders."""
    a.goto_page("mix")
    a.page.click('.bank .strip >> nth=0 >> .s-head')
    a.page.click('[data-proc="source"]')
    a.page.wait_for_timeout(200)
    # control: plain drag sends setLowCut
    m = a.rig.mark()
    a.drag("#lc", dx=120)
    control = a.rig.since(m, "setLowCut")
    # re-render from another client mid-drag
    m = a.rig.mark()
    ev = []
    a.drag("#lc", dx=-80, mid=lambda: (a.rerender_from_other_client(), ev.append(a.shot("S1_mid_drag_after_rerender"))))
    other = a.rig.since(m, "setLowCut")
    # 5 s periodic reload mid-drag (hold 6 s)
    m = a.rig.mark()
    a.drag("#lc", dx=100, hold_ms=6000)
    periodic = a.rig.since(m, "setLowCut")
    lc_val = a.page.eval_on_selector("#lc", "e => e.value")
    status = "VERIFIED PASS" if (control and other and periodic) else ("VERIFIED FAIL" if control else "BLOCKED")
    a.record("S1", "Range slider (LOW CUT) dragged while the page re-renders", status,
             "setLowCut sent on release in all three drags",
             f"plain drag sent {len(control)}; drag with other-client re-render sent {len(other)}; drag held 6 s (5 s reload) sent {len(periodic)}; slider now shows {lc_val}",
             ev, {"payloads": {"control": control, "otherClient": other, "periodic": periodic}})


def s2(a: Audit):
    a.goto_page("show")
    a.page.fill("#cue-name", "")
    a.page.type("#cue-name", "Worship set", delay=20)
    a.rerender_from_other_client()
    after_other = a.page.eval_on_selector("#cue-name", "e => e.value")
    a.page.fill("#cue-name", "")
    a.page.type("#cue-name", "Sermon", delay=20)
    a.page.wait_for_timeout(5600)
    after_periodic = a.page.eval_on_selector("#cue-name", "e => e.value")
    ev = [a.shot("S2_cue_name_after_reload")]
    ok = after_other == "Worship set" and after_periodic == "Sermon"
    a.record("S2", "Cue name being typed survives a re-render", "VERIFIED PASS" if ok else "VERIFIED FAIL",
             "the typed text stays", f"after other-client event: {after_other!r}; after 5.6 s idle: {after_periodic!r}", ev)


def s3(a: Audit):
    a.page.evaluate("localStorage.setItem('flow888.v3.groups', JSON.stringify([{name:'GROUP A',members:[]},{name:'GROUP B',members:[]},{name:'GROUP C',members:[]},{name:'GROUP D',members:[]}]))")
    a.page.reload(); a.ready()
    a.goto_page("mix")
    a.page.click('.grp[data-g="0"]')  # empty group: a tap opens the editor
    a.page.wait_for_selector(".grp-name", timeout=3000)
    a.page.click(".grp-name")
    a.page.keyboard.press("End")
    a.page.keyboard.type("X", delay=20)
    focused_before = a.page.evaluate("document.activeElement && document.activeElement.className")
    a.rerender_from_other_client()
    focused_after = a.page.evaluate("document.activeElement && document.activeElement.className")
    name_val = a.page.eval_on_selector(".grp-name", "e => e.value") if a.page.query_selector(".grp-name") else None
    ev = [a.shot("S3_group_name_focus")]
    ok = focused_after == "grp-name"
    a.record("S3", "Group-name input keeps focus across a re-render", "VERIFIED PASS" if ok else "VERIFIED FAIL",
             "focus stays in the name field", f"focus before: {focused_before!r}, after: {focused_after!r}; field value after: {name_val!r}", ev)
    if a.page.query_selector(".grp-done"):
        a.page.click(".grp-done")


def s4(a: Audit):
    a.page.evaluate("localStorage.setItem('flow888.v3.groups', JSON.stringify([{name:'GROUP A',members:[1,2]},{name:'GROUP B',members:[3]},{name:'GROUP C',members:[]},{name:'GROUP D',members:[]}]))")
    a.page.reload(); a.ready()
    a.goto_page("mix")
    a.rig.service.set_mute(1, False); a.rig.service.set_mute(2, False); a.rig.service.set_mute(3, False)
    a.rerender_from_other_client()
    m = a.rig.mark()
    a.page.click('.grp[data-g="0"]')
    a.page.wait_for_timeout(700)
    sent = a.rig.since(m)
    pressed = a.page.get_attribute('.grp[data-g="0"]', "aria-pressed")
    # reload and second device
    a.page.reload(); a.ready(); a.goto_page("mix")
    pressed_reload = a.page.get_attribute('.grp[data-g="0"]', "aria-pressed")
    p2 = a.ctx.new_page(); a.watch(p2)
    p2.add_init_script("localStorage.setItem('flow888.v3.groups', JSON.stringify([{name:'GROUP A',members:[1,2]},{name:'GROUP B',members:[3]},{name:'GROUP C',members:[]},{name:'GROUP D',members:[]}]))")
    p2.goto(a.rig.base + "/v3/"); p2.wait_for_timeout(1200)
    mute1 = a.rig.service.state_store.get_all_parameters().get("ch1.mute", {})
    # rejection: hub goes down after the session says ready
    a.rerender_from_other_client()
    a.rig.set_connected(False)
    m = a.rig.mark()
    a.page.click('.grp[data-g="1"]')
    a.page.wait_for_timeout(900)
    rejected = a.rig.since(m)
    pressed_b = a.page.get_attribute('.grp[data-g="1"]', "aria-pressed")
    ev = [a.shot("S4_group_B_after_rejection")]
    a.rig.set_connected(True)
    a.rerender_from_other_client(); a.page.wait_for_timeout(300)
    pressed_b_after = a.page.get_attribute('.grp[data-g="1"]', "aria-pressed")
    ev.append(a.shot("S4_group_B_after_reconnect"))
    p2.close()
    fail_bits = []
    if pressed_reload != "true":
        fail_bits.append("state lost on reload")
    if pressed_b_after == "true" and all(e["code"] != 200 for e in rejected if e["msg"].get("action") == "setMute"):
        fail_bits.append("group B shows ON although every mute was rejected")
    a.record("S4", "Mute group state: persistence, sharing, hub rejection", "VERIFIED FAIL" if fail_bits else "VERIFIED PASS",
             "group state matches the mixer: survives reload, rejected mutes do not leave the group ON",
             f"tap A sent {[ (e['msg'].get('action'), e['msg'].get('channel'), e['code']) for e in sent]}; A pressed={pressed}; after reload A pressed={pressed_reload}; ch1.mute in store={mute1.get('value', mute1)}; "
             f"tap B while hub down -> {[(e['msg'].get('action'), e['code']) for e in rejected]}; B pressed={pressed_b}; after reconnect B pressed={pressed_b_after}"
             + (f" -> {'; '.join(fail_bits)}" if fail_bits else ""), ev)


def s5(a: Audit):
    a.goto_page("output")
    m = a.rig.mark()
    a.page.focus(".geq-well >> nth=0")
    for _ in range(3):
        a.page.keyboard.press("ArrowUp")
    a.page.wait_for_timeout(500)
    geq = a.rig.since(m, "setBusGeq")
    role = a.page.get_attribute(".geq-well >> nth=0", "role")
    # control: EQ node keyboard on the Channel page
    a.goto_page("mix"); a.page.click('[data-proc="eq"]'); a.page.wait_for_timeout(200)
    m = a.rig.mark()
    a.page.focus(".eq-node >> nth=0"); a.page.keyboard.press("ArrowUp"); a.page.wait_for_timeout(500)
    eqk = a.rig.since(m, "setEqBand")
    ev = [a.shot("S5_eq_keyboard_control")]
    a.record("S5", "GEQ band operable from the keyboard", "VERIFIED PASS" if geq else ("VERIFIED FAIL" if eqk else "BLOCKED"),
             "ArrowUp on a focused GEQ band (role=slider) sends setBusGeq, as the EQ nodes do",
             f"GEQ role={role!r}, 3x ArrowUp sent {len(geq)} setBusGeq; control EQ node ArrowUp sent {len(eqk)} setEqBand", ev)


def lock_toggle(a: Audit):
    a.hold("#btn-lock", 950)


def s6(a: Audit):
    lock_toggle(a)
    locked = a.page.get_attribute("#btn-lock", "aria-pressed")
    a.goto_page("show")
    m = a.rig.mark()
    a.page.fill("#cue-name", "Locked save")
    a.page.click("#cue-add")
    a.page.wait_for_timeout(500)
    saves = a.rig.since(m, "librarySave")
    ev = [a.shot("S6_save_while_locked")]
    # control: a fader drag while locked sends nothing
    a.goto_page("mix")
    m = a.rig.mark()
    a.drag(".bank .strip .well", dy=-60)
    fader_locked = a.rig.since(m)
    lock_toggle(a)
    a.record("S6", "SAVE CURRENT MIX while the device is LOCKED", "VERIFIED FAIL" if saves else "VERIFIED PASS",
             "LOCK blocks every control on the device, including saving a cue",
             f"lock aria-pressed={locked}; librarySave sent {len(saves)} (code {[e['code'] for e in saves]}); control fader drag while locked sent {len(fader_locked)}", ev)


def s7(a: Audit):
    a.goto_page("mix"); a.page.click('[data-mix="main"] >> nth=0') if a.page.query_selector('.bus[data-mix="main"]') else None
    a.rig.set_connected(False)
    a.rerender_from_other_client(); a.page.wait_for_timeout(300)
    link = a.page.text_content("#link .tx")
    m = a.rig.mark()
    a.page.click(".bank .strip .s-mute")
    a.page.wait_for_timeout(600)
    mute = a.rig.since(m)
    m = a.rig.mark()
    a.drag(".bank .strip .well", dy=-50)
    fader = a.rig.since(m)
    ev = [a.shot("S7_mute_while_no_mixer")]
    toast = a.page.text_content("#toast")
    a.rig.set_connected(True); a.rerender_from_other_client()
    midi = sum(len(e["midi"]) for e in mute)
    a.record("S7", "Strip MUTE while the mixer is not connected",
             "VERIFIED FAIL" if mute else "VERIFIED PASS",
             "like every other control, MUTE sends nothing while the UI shows NO MIXER",
             f"link={link!r}; MUTE sent {[(e['msg'].get('action'), e['code']) for e in mute]} with {midi} MIDI messages; toast={toast!r}; control fader drag sent {len(fader)}",
             ev, {"severity_note": "hub rejects with 503 and no MIDI leaves; impact is a confusing error toast"})


def s8(a: Audit):
    lock_toggle(a)
    before = a.page.get_attribute("#btn-lock", "aria-pressed")
    a.page.reload(); a.ready()
    after = a.page.get_attribute("#btn-lock", "aria-pressed")
    ev = [a.shot("S8_lock_after_reload")]
    if after == "true":
        lock_toggle(a)
    a.record("S8", "LOCK survives a page reload", "VERIFIED PASS" if after == "true" else "VERIFIED FAIL",
             "a locked device stays locked after reload", f"before reload aria-pressed={before}; after reload={after}", ev)


def s9(a: Audit):
    p = a.ctx.new_page(); a.watch(p)
    p.goto("about:blank")
    p.goto(a.rig.base + "/v3/"); p.wait_for_timeout(800)
    p.click('#rail button[data-page="fx"]'); p.wait_for_timeout(300)
    p.go_back(); p.wait_for_timeout(500)
    url = p.url
    p.close()
    a.record("S9", "Browser Back after changing page", "VERIFIED PASS" if "/v3" in url else "VERIFIED FAIL",
             "Back returns to the previous console page", f"URL after Back: {url!r}")


# ================= payload audit =================
def payload_audit(a: Audit):
    rows = []

    def check(label, fn, action, expect):
        m = a.rig.mark()
        fn()
        a.page.wait_for_timeout(350)
        got = a.rig.since(m)
        hits = [e for e in got if e["msg"].get("action") == action]
        last = hits[-1] if hits else None
        ok_midi = bool(last) and last["code"] == 200 and expect(last)
        rows.append({"control": label, "action": action, "requests": len(hits),
                     "payload": last and last["msg"], "code": last and last["code"],
                     "midi": last and last["midi"], "status": "VERIFIED PASS" if ok_midi else "VERIFIED FAIL"})

    def cc(e, ch, ccn, n=1):
        v = e["msg"].get("value")
        ms = [x for x in e["midi"] if x["kind"] == "CC" and x["ch"] == ch and x["d1"] == ccn]
        return len(ms) >= n and (isinstance(v, bool) or v is None or ms[-1]["d2"] == v)

    a.goto_page("mix")
    a.page.click('.bus[data-mix="main"]'); a.page.wait_for_timeout(200)
    a.page.click('.bank .strip >> nth=0 >> .s-head')
    check("MIX bank fader CH1 (MAIN)", lambda: a.drag(".bank .strip .well", dy=-70), "setFader", lambda e: cc(e, 1, 7))
    check("MIX strip MUTE CH2", lambda: a.page.click(".bank .strip >> nth=1 >> .s-mute"), "setMute",
          lambda e: any(x["ch"] == 2 and x["d1"] == 5 and x["d2"] in (0, 127) for x in e["midi"]))
    check("MIX master fader MAIN", lambda: a.drag(".mstrip .well", dy=-50), "setFader", lambda e: cc(e, 8, 7))
    a.page.click('[data-proc="eq"]'); a.page.wait_for_timeout(200)
    check("MIX EQ node LOW CH1", lambda: a.drag(".eq-node >> nth=0", dy=-40), "setEqBand", lambda e: cc(e, 1, 1))
    check("MIX EQ FLAT (two taps)", lambda: (a.page.click("#eq-flat"), a.page.wait_for_timeout(150), a.page.click("#eq-flat")), "resetEqFlat",
          lambda e: sum(1 for x in e["midi"] if x["ch"] == 1 and x["d1"] in (1, 2, 3, 4) and x["d2"] == 64) == 4)
    a.page.click('[data-proc="monsend"]'); a.page.wait_for_timeout(200)
    check("MIX MON SEND cell CH1→MON1", lambda: a.drag(".pv .cell >> nth=0", dx=80), "setSend", lambda e: cc(e, 1, 14))
    a.page.click('.bus[data-mix="mon1"]'); a.page.wait_for_timeout(250)
    check("MIX master fader MON1", lambda: a.drag(".mstrip .well", dy=-40), "setBusFader", lambda e: cc(e, 9, 7))
    check("MIX bank fader CH1 on MON1 (send)", lambda: a.drag(".bank .strip .well", dy=-40), "setSend", lambda e: cc(e, 1, 14))
    a.page.click('.bus[data-mix="main"]'); a.page.wait_for_timeout(200)
    a.page.click('[data-proc="source"]'); a.page.wait_for_timeout(200)
    check("SOURCE LOW CUT CH1 (keyboard)", lambda: (a.page.focus("#lc"), a.page.keyboard.press("ArrowRight")), "setLowCut", lambda e: cc(e, 1, 9))
    a.page.click('[data-proc="comp"]'); a.page.wait_for_timeout(200)
    check("COMP CH1 (keyboard)", lambda: (a.page.focus("#cp"), a.page.keyboard.press("ArrowRight")), "setCompressor", lambda e: cc(e, 1, 11))
    a.goto_page("output")
    check("OUTPUT GEQ band 1 MAIN", lambda: a.drag(".geq-well >> nth=0", dy=-40), "setBusGeq", lambda e: cc(e, 8, 11))
    check("OUTPUT LIMITER MAIN (keyboard)", lambda: (a.page.focus("#lim"), a.page.keyboard.press("ArrowLeft")), "setBusLimiter", lambda e: cc(e, 8, 8))
    a.page.click('.mixes [data-mix="mon2"]'); a.page.wait_for_timeout(200)
    check("OUTPUT GEQ band 9 MON2", lambda: a.drag(".geq-well >> nth=8", dy=-40), "setBusGeq", lambda e: cc(e, 10, 19))
    a.goto_page("fx")
    check("FX1 preset 3", lambda: a.page.click('[data-fx="fx1"][data-p="3"]'), "setFxPreset",
          lambda e: any(x["kind"] == "PC" and x["ch"] == 13 and x["d1"] == 3 for x in e["midi"]))
    check("FX2 PARAM1 (keyboard)", lambda: (a.page.focus("#fx2-p1"), a.page.keyboard.press("ArrowRight")), "setFxParam", lambda e: cc(e, 14, 1))
    check("FX1 VARIANT B", lambda: a.page.click('[data-v="fx1:1"]'), "setFxParam",
          lambda e: any(x["ch"] == 13 and x["d1"] == 2 and x["d2"] == 127 for x in e["midi"]))
    a.goto_page("stage")
    check("MY MON CH1→MON1 strip", lambda: a.drag(".others .strip .well", dy=-40), "setSend", lambda e: cc(e, 1, 14))
    check("MY MON master MON1", lambda: a.drag(".others .strip.master .well", dy=-40), "setBusFader", lambda e: cc(e, 9, 7))
    a.goto_page("mix")
    check("MUTE ALL (hold 0.7 s)", lambda: a.hold("#btn-muteall", 700), "muteAll",
          lambda e: sorted({x["ch"] for x in e["midi"] if x["d1"] == 5}) == [1, 2, 3, 4, 5, 6, 7])
    check("MUTE ALL again (unmute)", lambda: a.hold("#btn-muteall", 700), "muteAll",
          lambda e: sorted({x["ch"] for x in e["midi"] if x["d1"] == 5}) == [1, 2, 3, 4, 5, 6, 7])
    check("UNDO", lambda: a.page.click("#btn-undo"), "undo", lambda e: len(e["midi"]) >= 1)
    check("REDO", lambda: a.page.click("#btn-redo"), "redo", lambda e: len(e["midi"]) >= 1)
    a.page.click('#to-channel'); a.page.wait_for_timeout(300)
    if a.page.query_selector(".preset"):
        check("CHANNEL preset (two taps)", lambda: (a.page.click(".preset >> nth=0"), a.page.wait_for_timeout(200), a.page.click(".preset >> nth=0")),
              "applyPreset", lambda e: any(x["ch"] == 1 for x in e["midi"]))
    # every MIDI message ever sent stays inside the verified map; nothing on channel 16; no +48V/gain
    allm = [x for e in a.rig.log for x in e["midi"]]
    bad = [x for x in allm if x["ch"] in (15, 16) or (x["kind"] == "CC" and x["d1"] in (8, 12) and x["ch"] <= 4 and x["ch"] <= 7 and x["d1"] == 12)
           or (x["kind"] == "CC" and x["d1"] == 8 and x["ch"] <= 4)]
    return rows, {"midiMessages": len(allm), "outsideMapOrForbidden": bad}


def regression(a: Audit):
    out = []
    # inbound hardware move -> UI shows LIV
    a.goto_page("mix"); a.page.click('.bus[data-mix="main"]'); a.page.wait_for_timeout(200)
    a.rig.service.midi_in._internal_c_callback(None, MIM_DATA, 0, 0xB0 | (7 << 8) | (90 << 16), 0)
    a.page.wait_for_timeout(700)
    prov = a.page.text_content(".bank .strip >> nth=0 >> .prov")
    read = a.page.text_content(".bank .strip >> nth=0 >> .s-read")
    out.append({"check": "Hardware fader move (ch1 CC7=90) shows as LIV with the new value", "status": "VERIFIED PASS" if prov == "LIV" else "VERIFIED FAIL",
                "actual": f"provenance={prov!r}, readout={read!r}"})
    # meters render then fall back
    a.rig.hub.publish_meters({"ch1": {"peak": -6.0, "rms": -12.0}, "main": {"peak": -3.0, "rms": -9.0}})
    a.page.wait_for_timeout(300)
    clip_live = a.page.eval_on_selector('.meter[data-sid="ch1"] .lvl', "e => e.style.getPropertyValue('--clip')")
    a.page.wait_for_timeout(2700)
    clip_stale = a.page.eval_on_selector('.meter[data-sid="ch1"] .lvl', "e => e.style.getPropertyValue('--clip')")
    out.append({"check": "Meter shows a frame, then falls to zero 2 s after the feed stops",
                "status": "VERIFIED PASS" if clip_live not in ("", "100%") and clip_stale == "100%" else "VERIFIED FAIL",
                "actual": f"--clip live={clip_live!r}, after 3 s={clip_stale!r}", "note": "rendering only; synthetic levels, no audio"})
    # disconnect -> offline note and NO MIXER; reconnect -> CONNECTED
    a.rig.set_connected(False); a.rerender_from_other_client(); a.page.wait_for_timeout(300)
    t_off = a.page.text_content("#link .tx"); note = bool(a.page.query_selector(".offline-note"))
    sh = a.shot("REG_offline")
    a.rig.set_connected(True); a.rerender_from_other_client(); a.page.wait_for_timeout(300)
    t_on = a.page.text_content("#link .tx")
    out.append({"check": "Mixer disconnect shows NO MIXER + offline note; reconnect shows CONNECTED",
                "status": "VERIFIED PASS" if (t_off == "NO MIXER" and note and t_on == "CONNECTED") else "VERIFIED FAIL",
                "actual": f"off={t_off!r} note={note} on={t_on!r}", "evidence": [sh]})
    # hub unreachable -> NO HOST PC (stop SSE by blocking requests)
    a.page.route("**/api/**", lambda r: r.abort())
    a.page.wait_for_timeout(5600)
    t_hub = a.page.text_content("#link .tx")
    a.page.unroute("**/api/**")
    a.page.wait_for_timeout(5600)
    t_hub_back = a.page.text_content("#link .tx")
    out.append({"check": "Host PC unreachable shows NO HOST PC; recovers when reachable", "status": "VERIFIED PASS" if t_hub == "NO HOST PC" and t_hub_back == "CONNECTED" else "VERIFIED FAIL",
                "actual": f"blocked={t_hub!r}, restored={t_hub_back!r}", "note": "SSE already open is not cut by route(); the 5 s session poll is"})
    # gain / +48V cannot be sent from the page
    codes = []
    for body in ({"action": "setGain", "channel": 1, "value": 64}, {"action": "setPhantom", "channel": 1, "value": True}):
        r = a.page.request.post(a.rig.base + "/api/action", data=json.dumps(body), headers={"Content-Type": "application/json"})
        codes.append(r.status)
    out.append({"check": "Gain and +48V POSTed directly are refused by the hub (403) and send no MIDI",
                "status": "VERIFIED PASS" if codes == [403, 403] and not [e for e in a.rig.log if e["msg"].get("action") in ("setGain", "setPhantom") and e["midi"]] else "VERIFIED FAIL",
                "actual": f"HTTP {codes}"})
    # bottom controls reachable (stage scrolls) on this viewport
    a.goto_page("mix"); a.page.wait_for_timeout(200)
    st = a.page.evaluate("(() => { const s = document.querySelector('#stage'); const m = document.querySelector('.bank .strip .s-mute'); const r = m.getBoundingClientRect(); return {sh: s.scrollHeight, ch: s.clientHeight, oy: getComputedStyle(s).overflowY, muteBottom: Math.round(r.bottom), vh: innerHeight}; })()")
    a.page.locator(".bank .strip .s-mute").first.scroll_into_view_if_needed()
    vis = a.page.evaluate("(() => { const r = document.querySelector('.bank .strip .s-mute').getBoundingClientRect(); return r.bottom <= innerHeight && r.top >= 0; })()")
    out.append({"check": "Strip MUTE fully reachable on the Mix page", "status": "VERIFIED PASS" if vis else "VERIFIED FAIL",
                "actual": f"stage {st}; after scroll fully visible={vis}", "evidence": [a.shot("REG_mute_reach")]})
    # every page: render, no horizontal overflow, screenshot
    for pg in ("mix", "fx", "stage", "show", "output", "safety"):
        a.goto_page(pg); a.page.wait_for_timeout(250)
        sw, cw = a.overflow()
        out.append({"check": f"Page {pg} renders without horizontal overflow", "status": "VERIFIED PASS" if sw <= cw else "VERIFIED FAIL",
                    "actual": f"scrollWidth={sw} clientWidth={cw}", "evidence": [a.shot(f"PAGE_{pg}")]})
    for pg, sel in (("sends", "#all-sends"), ("channel", "#to-channel")):
        a.goto_page("mix")
        if pg == "sends":
            a.page.click('[data-proc="fxsend"]'); a.page.wait_for_timeout(150)
        a.page.click(sel); a.page.wait_for_timeout(300)
        sw, cw = a.overflow()
        out.append({"check": f"Secondary page {pg} renders without horizontal overflow", "status": "VERIFIED PASS" if sw <= cw else "VERIFIED FAIL",
                    "actual": f"scrollWidth={sw} clientWidth={cw}", "evidence": [a.shot(f"PAGE_{pg}")]})
    return out


def run_viewport(pw, name, size):
    rig = Rig()
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport=size, device_scale_factor=1)
    page = ctx.new_page()
    a = Audit(name, page, rig, ctx)
    page.goto(rig.base + "/v3/")
    a.ready()
    page.evaluate("localStorage.clear()"); page.reload(); a.ready()
    report = {"viewport": name, "size": size}
    for fn in (s1, s2, s3, s4, s5, s6, s7, s8, s9):
        try:
            fn(a)
        except Exception as exc:  # environment/harness error: recorded apart from app defects
            a.record(fn.__name__.upper(), "harness error", "BLOCKED", "-", f"{type(exc).__name__}: {exc}",
                     [a.shot(f"{fn.__name__}_blocked")], {"trace": traceback.format_exc()[-1500:]})
            try:
                page.mouse.up(); page.reload(); a.ready()
            except Exception:
                pass
    try:
        page.reload(); a.ready()
        report["payloads"], report["midiSummary"] = payload_audit(a)
    except Exception as exc:
        report["payloadError"] = traceback.format_exc()[-2000:]
        a.shot("payload_blocked")
    try:
        page.reload(); a.ready()
        report["regression"] = regression(a)
    except Exception:
        report["regressionError"] = traceback.format_exc()[-2000:]
        a.shot("regression_blocked")
    report["sTests"] = a.results
    report["console"] = a.console
    report["pageErrors"] = a.pageerrors
    report["requestFailed"] = a.failed
    report["httpErrors"] = [h for h in a.http if h["status"] >= 400]
    report["requests"] = {"total": len(a.http), "byMethod": {m: sum(1 for h in a.http if h["method"] == m) for m in {h["method"] for h in a.http}}}
    report["hubLog"] = rig.log
    report["fakeDriverCalls"] = len(rig.driver.midiOutShortMsg.call_args_list)
    ctx.close(); browser.close(); rig.stop()
    return report


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        for name, size in VIEWPORTS.items():
            reports.append(run_viewport(pw, name, size))
    summary = {"physicalMidiCalls": PHYSICAL, "physicalMidiCallCount": len(PHYSICAL), "reports": reports}
    (OUT / "phase2_report.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("PHYSICAL MIDI CALLS:", len(PHYSICAL))
    return 0 if not PHYSICAL else 2


if __name__ == "__main__":
    sys.exit(main())
