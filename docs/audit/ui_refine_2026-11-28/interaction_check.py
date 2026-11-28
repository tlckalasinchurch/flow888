"""Interaction check after the 2026-11-28 refinement. Same no-hardware rig as ui_harness.py.

1. Keyboard: Tab-focused CH 5/6 fader (UNSYNCED) + ArrowUp -> readout and badge become SNT,
   one setFader ch5 value 1 reaches the boundary, focus ring is visible.
2. Pointer drag on CH 2 fader -> readout follows, setFader ch2 sent inside one gesture.
3. Hover (mouse viewport): a process item's border turns to --ink-3; a selected item keeps --sel.
4. EQ keyboard on band 2 -> setEqBand low_mid, axis labels are 12 px HTML.
5. Touch tap on mute group A (empty) opens the editor (unchanged behaviour).
"""
import json
import sys
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_harness as H  # noqa: E402  (installs the winmm guard first)


def main():
    s = H.Flow8Service(auto_connect=False)
    H.fake_open_port(s.midi_out)
    mi = s.midi_in
    mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
    s._connected = True
    hub = H.Flow8LanHub(s, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
    port = hub.start()
    H.seed(hub, s, cues=False)
    log = []
    orig = hub.dispatch_action

    def rec(msg):
        code, res = orig(msg)
        log.append({k: v for k, v in msg.items() if k != "clientId"} | {"_code": code})
        return code, res
    hub.dispatch_action = rec
    out = {}
    try:
        with H.sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            pg.add_init_script("localStorage.setItem('flow888.v3.proc', JSON.stringify('eq'));")
            pg.goto(f"http://127.0.0.1:{port}/v3/")
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
            pg.wait_for_timeout(300)

            # 1 keyboard
            strip = pg.locator(".ws .bank .strip").nth(4)
            well = strip.locator(".well")
            well.focus()
            pg.keyboard.press("Tab"); pg.keyboard.press("Shift+Tab")  # real keyboard focus -> :focus-visible
            n0 = len(log)
            pg.keyboard.press("ArrowUp")
            pg.wait_for_timeout(250)
            out["kbd_read"] = strip.locator(".s-read").inner_text().replace("\n", " ")
            out["kbd_badge_class"] = strip.locator(".s-read .prov").get_attribute("class")
            out["kbd_sent"] = [x for x in log[n0:] if x.get("action") == "setFader"]
            out["focus_outline"] = pg.evaluate("getComputedStyle(document.activeElement).outlineStyle + ' ' + getComputedStyle(document.activeElement).outlineColor")

            # 2 pointer drag on CH 2
            pg.wait_for_timeout(400)
            w2 = pg.locator(".ws .bank .strip").nth(1).locator(".well")
            bb = w2.bounding_box()
            n0 = len(log)
            x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] * 0.6
            pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, y - 30, steps=6); pg.mouse.up()
            pg.wait_for_timeout(500)
            out["drag_actions"] = [x["action"] for x in log[n0:]]
            out["drag_read"] = pg.locator(".ws .bank .strip").nth(1).locator(".s-read").inner_text().replace("\n", " ")

            # 3 hover
            item = pg.locator('.proc .item[data-proc="comp"]')
            item.hover(); pg.wait_for_timeout(100)
            out["hover_border"] = item.evaluate("e => getComputedStyle(e).borderTopColor")
            sel = pg.locator('.proc .item[data-proc="eq"]')
            sel.hover(); pg.wait_for_timeout(100)
            out["hover_selected_border"] = sel.evaluate("e => getComputedStyle(e).borderTopColor")

            # 4 EQ keyboard + axis
            node = pg.locator('.eq-node[data-k="1"]')
            node.focus(); n0 = len(log)
            pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(300)
            out["eq_sent"] = [x for x in log[n0:] if x.get("action") == "setEqBand"]
            out["axis_font"] = pg.evaluate("[...document.querySelectorAll('.eq-axis .ax')].map(e => getComputedStyle(e).fontSize)")
            pg.close()

            # 5 touch: tap empty group A opens its editor
            ctx = b.new_context(viewport={"width": 1024, "height": 768}, has_touch=True)
            tp = ctx.new_page()
            tp.goto(f"http://127.0.0.1:{port}/v3/")
            tp.wait_for_selector('.grp[data-g="0"]')
            bx = tp.locator('.grp[data-g="0"]').bounding_box()
            out["grp_box"] = [round(bx["width"]), round(bx["height"])]
            tp.locator('.grp[data-g="0"]').tap(); tp.wait_for_timeout(300)
            out["grp_editor_open"] = tp.locator(".grp-edit").count() == 1
            ctx.close()
            b.close()
    finally:
        hub.stop()
    out["physical"] = H.PHYSICAL
    (Path(__file__).resolve().parent / "interaction_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    assert not H.PHYSICAL


if __name__ == "__main__":
    main()
