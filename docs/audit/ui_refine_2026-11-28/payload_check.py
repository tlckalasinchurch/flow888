"""MIDI payload record for a fixed UI interaction script, to diff before/after a UI change. No hardware.

Drives the real v3 page (keyboard, mouse, touch) against the in-process hub with the fake MIDI OUT
driver, and records every hub action and every MIDI short message the boundary let through, decoded.
    python -I payload_check.py <label>      -> payload_<label>.json
"""
import json
import sys
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_harness as H  # noqa: E402  (installs the winmm guard first)


def decode(dword):
    status, d1, d2 = dword & 0xFF, (dword >> 8) & 0xFF, (dword >> 16) & 0xFF
    return f"{ {0xB0: 'CC', 0xC0: 'PC'}.get(status & 0xF0, hex(status & 0xF0)) } ch{(status & 0x0F) + 1} {d1} {d2}"


def main(label):
    s = H.Flow8Service(auto_connect=False)
    _, drv = H.fake_open_port(s.midi_out)
    mi = s.midi_in
    mi._is_open, mi._handle, mi._is_listening = True, wintypes.HANDLE(0x5678), True
    s._connected = True
    hub = H.Flow8LanHub(s, host="127.0.0.1", port=0, library_path=None, show_modes_path=None)
    port = hub.start()
    H.seed(hub, s, cues=False)
    log = []
    orig = hub.dispatch_action

    def rec(msg):
        before = len(drv.midiOutShortMsg.call_args_list)
        code, res = orig(msg)
        midi = [decode(c.args[1]) for c in drv.midiOutShortMsg.call_args_list[before:]]
        log.append({"msg": {k: v for k, v in msg.items() if k != "clientId"}, "code": code, "midi": midi})
        return code, res
    hub.dispatch_action = rec
    base = f"http://127.0.0.1:{port}/v3/"
    try:
        with H.sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            pg.add_init_script("localStorage.clear(); localStorage.setItem('flow888.v3.proc', JSON.stringify('eq'));")
            pg.goto(base)
            pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
            pg.wait_for_timeout(400)
            step = lambda: pg.wait_for_timeout(450)  # noqa: E731
            # keyboard: CH 2 fader x2, EQ band 1 x2
            pg.focus(".ws .bank .strip:nth-child(2) .well"); pg.keyboard.press("ArrowUp"); step(); pg.keyboard.press("ArrowUp"); step()
            pg.focus('.eq-node[data-k="0"]'); pg.keyboard.press("ArrowDown"); step(); pg.keyboard.press("ArrowDown"); step()
            # mouse: drag CH 4 fader down
            bb = pg.locator(".ws .bank .strip:nth-child(4) .well").bounding_box()
            x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] * 0.3
            pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, y + 40, steps=4); pg.mouse.up(); step()
            # mouse: strip MUTE on CH 2 (known unmuted? unknown -> mutes), then again
            pg.click(".ws .bank .strip:nth-child(2) .s-mute"); step()
            pg.click(".ws .bank .strip:nth-child(2) .s-mute"); step()
            # MON SEND cell keyboard
            pg.click('[data-proc="monsend"]'); step()
            pg.focus('.sends1 .cell[data-m="mon2"]'); pg.keyboard.press("ArrowRight"); step()
            # FX preset + variant
            pg.click('[data-page="fx"]'); step()
            pg.click('[data-fx="fx2"][data-p="5"]'); step()
            pg.click('[data-v="fx2:1"]'); step()
            # OUTPUT GEQ keyboard
            pg.click('[data-page="output"]'); step()
            pg.focus("#geq-4"); pg.keyboard.press("ArrowUp"); step()
            pg.close()
            # touch: tap CH 3 MUTE at iPad size
            ctx = b.new_context(viewport={"width": 1024, "height": 768}, has_touch=True)
            tp = ctx.new_page()
            tp.add_init_script("localStorage.setItem('flow888.v3.page', JSON.stringify('mix'));")
            tp.goto(base); tp.wait_for_selector(".ws .bank .s-mute"); tp.wait_for_timeout(400)
            tp.locator(".ws .bank .strip:nth-child(3) .s-mute").tap(); tp.wait_for_timeout(450)
            ctx.close(); b.close()
    finally:
        hub.stop()
    seq = [x for x in log if x["msg"].get("action") not in ("beginGesture", "endGesture")]
    out = {"label": label, "physical": H.PHYSICAL, "actions": seq}
    Path(__file__).resolve().parent.joinpath(f"payload_{label}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(label, len(seq), "commands,", sum(len(x["midi"]) for x in seq), "MIDI messages; physical", len(H.PHYSICAL))
    assert not H.PHYSICAL


if __name__ == "__main__":
    main(sys.argv[1])
