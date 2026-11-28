"""Phase E interaction and regression checks for the FLOW 888 v3 console. No hardware.

Same rig as ui_harness.py (winmm open/send raise; fake MIDI OUT; real hub and command boundary).
Every browser POST to /api/action is captured from the page, and every hub dispatch with the MIDI
it produced is captured at the hub, so "nothing sent" is checked at both ends.

  1. one keypress / one click -> exactly one command (no duplicates)
  2. a mouse drag -> one gesture, throttled sends, final value once
  3. UNDO / REDO -> the hub's undo/redo with the MIDI that restores / re-applies the value
  4. LOCKED: fader key, fader drag, strip MUTE, group, EQ node, GEQ -> no request at all
  5. NO MIXER (real reconcile_connection path): the same controls -> no request at all
  6. after reconnect without new commands, every value still reads unknown

    python -I interaction_e.py  -> interaction_e.json
"""
import json
import sys
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ui_refine_2026-11-28"))
import ui_harness as H  # noqa: E402


def decode(d):
    st, d1, d2 = d & 0xFF, (d >> 8) & 0xFF, (d >> 16) & 0xFF
    return f"{ {0xB0: 'CC', 0xC0: 'PC'}.get(st & 0xF0, hex(st & 0xF0)) } ch{(st & 0x0F) + 1} {d1} {d2}"


def main():
    s = H.Flow8Service(auto_connect=False)
    _, drv = H.fake_open_port(s.midi_out)
    mi = s.midi_in
    mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
    s._connected = True
    hub = H.Flow8LanHub(s, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
    port = hub.start()
    assert port != 8844
    H.seed(hub, s, cues=False)
    hublog = []
    orig = hub.dispatch_action

    def rec(msg):
        n = len(drv.midiOutShortMsg.call_args_list)
        code, res = orig(msg)
        hublog.append({"action": msg.get("action"), "code": code,
                       "midi": [decode(c.args[1]) for c in drv.midiOutShortMsg.call_args_list[n:]]})
        return code, res
    hub.dispatch_action = rec
    out = {}
    try:
        with H.sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1180, "height": 820})
            posts = []
            pg.on("request", lambda r: posts.append(json.loads(r.post_data or "{}").get("action")) if r.url.endswith("/api/action") else None)
            pg.add_init_script("localStorage.clear(); localStorage.setItem('flow888.v3.proc', JSON.stringify('eq'));")
            pg.goto(f"http://127.0.0.1:{port}/v3/")
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
            pg.wait_for_timeout(500)
            wait = lambda ms=500: pg.wait_for_timeout(ms)  # noqa: E731

            def window(fn):
                a, h = len(posts), len(hublog)
                fn()
                wait(600)
                return [x for x in posts[a:] if x not in ("beginGesture", "endGesture")], hublog[h:]

            fader2 = ".ws .bank .strip:nth-child(2) .well"
            # 1 single actions
            pb, hb = window(lambda: (pg.focus(fader2), pg.keyboard.press("ArrowUp")))
            out["one_key"] = {"posts": pb, "hub": hb}
            pb, hb = window(lambda: pg.click(".ws .bank .strip:nth-child(4) .s-mute"))
            out["one_click_mute"] = {"posts": pb, "hub": hb}
            # 2 drag
            bb = pg.locator(".ws .bank .strip:nth-child(1) .well").bounding_box()
            x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] * 0.3

            def drag():
                pg.mouse.move(x, y); pg.mouse.down()
                for i in range(10):
                    pg.mouse.move(x, y + 4 * (i + 1)); pg.wait_for_timeout(30)
                pg.mouse.up()
            a, h = len(posts), len(hublog)
            drag(); wait(700)
            out["drag"] = {"posts": posts[a:], "hub_actions": [e["action"] for e in hublog[h:]]}
            # 3 undo / redo of the last change (the drag)
            pb, hb = window(lambda: pg.click("#btn-undo"))
            out["undo"] = hb
            pb, hb = window(lambda: pg.click("#btn-redo"))
            out["redo"] = hb

            def try_all():
                pg.focus(fader2); pg.keyboard.press("ArrowUp")
                b2 = pg.locator(fader2).bounding_box()
                pg.mouse.move(b2["x"] + b2["width"] / 2, b2["y"] + 60); pg.mouse.down(); pg.mouse.move(b2["x"] + b2["width"] / 2, b2["y"] + 20, steps=4); pg.mouse.up()
                pg.click(".ws .bank .strip:nth-child(2) .s-mute", force=True)
                pg.focus('.eq-node[data-k="0"]'); pg.keyboard.press("ArrowUp")

            # 4 LOCKED (hold LOCK 0.8 s from the keyboard, as a user would)
            pg.focus("#btn-lock"); pg.keyboard.down("Space"); wait(1000); pg.keyboard.up("Space"); wait(400)
            out["locked_pressed"] = pg.get_attribute("#btn-lock", "aria-pressed")
            pb, hb = window(try_all)
            out["locked"] = {"posts": pb, "hub": hb}
            pg.focus("#btn-lock"); pg.keyboard.down("Space"); wait(1000); pg.keyboard.up("Space"); wait(400)
            out["unlocked_pressed"] = pg.get_attribute("#btn-lock", "aria-pressed")
            # 5 NO MIXER, through the real unplug path
            s.midi_out._is_open = False
            s._connected = False
            s.reconcile_connection()
            pg.reload()
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'NO MIXER'", timeout=8000)
            wait(400)
            pb, hb = window(try_all)
            out["offline"] = {"posts": pb, "hub": hb, "readouts": pg.eval_on_selector_all(".ws .s-read .v", "e => e.map(x => x.textContent)")}
            # 6 reconnect with no new commands: still unknown (a driver link is not a reading)
            s.midi_out._is_open = True
            s._connected = True
            pg.reload()
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
            wait(400)
            out["after_reconnect"] = {"readouts": pg.eval_on_selector_all(".ws .s-read .v", "e => e.map(x => x.textContent)"),
                                      "badges": pg.eval_on_selector_all(".ws .s-read .prov", "e => e.map(x => x.textContent)"),
                                      "mutes": pg.eval_on_selector_all(".ws .s-mute", "e => e.map(x => x.textContent.trim())")}
            b.close()
    finally:
        hub.stop()
    out["physical"] = H.PHYSICAL
    (HERE / "interaction_e.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    assert not H.PHYSICAL


if __name__ == "__main__":
    main()
