"""Focus-visible check: Tab through every focusable control of each page, day and night, at 1180x820.

For each focused element it reads the computed outline (style, width, colour) and the background
behind it, and computes the outline-to-background contrast (WCAG 1.4.11 / 2.4.13 need 3:1 and a
visible indicator). Real Tab key presses, so :focus-visible applies. Uses the rig on 8855.
    python -I focus_check.py  -> focus_check.json
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = ["mix", "fx", "stage", "show", "output", "safety"]
JS = r"""
() => {
  const e = document.activeElement; if (!e || e === document.body) return null;
  const s = getComputedStyle(e);
  const rgb = (c) => (c.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  let bgEl = e.parentElement, bg = 'rgb(0,0,0)';
  while (bgEl) { const c = getComputedStyle(bgEl).backgroundColor; const a = rgb(c); if (a.length >= 3 && (a.length < 4 || a[3] > 0.5)) { bg = c; break; } bgEl = bgEl.parentElement; }
  const o = rgb(s.outlineColor); const b = rgb(bg);
  const L1 = lum(o), L2 = lum(b); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
  return { el: (e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0]) + ' ' + (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 18),
           style: s.outlineStyle, width: parseFloat(s.outlineWidth), ratio: Math.round(ratio * 100) / 100 };
}
"""


def main():
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for theme in ("day", "night"):
            for page in PAGES:
                pg = b.new_page(viewport={"width": 1180, "height": 820})
                pg.add_init_script(f"localStorage.setItem('flow888.v3.page', JSON.stringify('{page}'));"
                                   f"localStorage.setItem('flow888.v3.night', JSON.stringify({str(theme == 'night').lower()}));")
                pg.goto("http://127.0.0.1:8855/v3/")
                pg.wait_for_function("document.querySelector('#link .tx').textContent === 'CONNECTED'", timeout=8000)
                pg.wait_for_timeout(400)
                seen, bad = [], []
                for _ in range(70):
                    pg.keyboard.press("Tab")
                    r = pg.evaluate(JS)
                    if not r:
                        continue
                    if seen and r["el"] == seen[0]:
                        break
                    seen.append(r["el"])
                    if r["style"] == "none" or r["width"] < 2 or r["ratio"] < 3:
                        bad.append(r)
                out[f"{theme}/{page}"] = {"focusable_reached": len(seen), "failures": bad}
                pg.close()
        b.close()
    Path(__file__).resolve().parent.joinpath("focus_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in out.items():
        print(k, v["focusable_reached"], "reached,", len(v["failures"]), "failures", v["failures"][:3])


if __name__ == "__main__":
    main()
