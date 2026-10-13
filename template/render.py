"""Render page steps and mascot sprites to PNG with a single headless Chrome.

usage:
  python3 render.py mascots
  python3 render.py pages p01 p02 ...      # renders every step listed in script.json
  python3 render.py sheet p01 p02 ...      # contact sheet of rendered steps (for review)
"""

import json, os, sys
from pathlib import Path
import os
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
POSES = ["idle", "wave", "point", "sign", "magnifier", "thumbs", "think", "cheer"]

def init_script():
    """globals every page sees before its own scripts run (progress-bar labels from script.json)"""
    steps = json.loads((ROOT / "script.json").read_text(encoding="utf-8")).get("progress_steps", [])
    return f"window.PROGRESS_STEPS = {json.dumps(steps, ensure_ascii=False)};"


def load_script():
    return json.loads((ROOT / "script.json").read_text(encoding="utf-8"))


def page_steps(script, pid):
    page = next(p for p in script["pages"] if p["id"] == pid)
    return sorted({b.get("step", 1) for b in page["beats"]})


def mascot_name(pose, blink, flip, sign=None):
    import hashlib
    return f"{pose}_{blink}_{flip}" + (f"_{hashlib.md5(sign.encode()).hexdigest()[:8]}" if sign else "")


def render_mascots(browser):
    import urllib.parse
    d = OUT / "mascot"
    d.mkdir(parents=True, exist_ok=True)
    pg = browser.new_page(viewport={"width": 480, "height": 480})
    combos = {(pose, None) for pose in POSES}
    for page in load_script()["pages"]:
        for beat in page["beats"]:
            if beat.get("sign"):
                combos.add((beat.get("pose", "sign"), beat["sign"]))
    for pose, sign in sorted(combos, key=str):
        for blink in (0, 1):
            for flip in (0, 1):
                f = d / f"{mascot_name(pose, blink, flip, sign)}.png"
                if f.exists():
                    continue
                url = f"file://{ROOT}/assets/mascot.html?pose={pose}&blink={blink}&flip={flip}"
                if sign:
                    url += "&sign=" + urllib.parse.quote(sign)
                pg.goto(url)
                pg.wait_for_selector("body[data-ready='1']")
                pg.evaluate("document.fonts.ready")
                pg.screenshot(path=str(f), omit_background=True)
    pg.close()


FOCUS_JS = """(step) => {
  const forced = [...document.querySelectorAll('[data-focus]')].filter(e => e.dataset.focus.split(',').map(Number).includes(step));
  // priority: explicit data-focus for this step > code tokens highlighted at this step (data-hl) > newly shown elements
  const hls = [...document.querySelectorAll('[data-hl]')].filter(e => e.classList.contains('hl'));
  let els = forced.length ? forced : (hls.length ? hls : [...document.querySelectorAll('[data-s="' + step + '"]')].filter(e => e.classList.contains('on')));
  if (!els.length) els = [...document.querySelectorAll('.card, svg, .code, .note, img')].filter(e => !e.closest('.header') && !e.closest('.ptitle') && !e.closest('[data-s]'));
  const rects = [];
  els.forEach(e => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return;
    rects.push([Math.max(0, r.left), Math.max(0, r.top), Math.min(1920, r.right), Math.min(1080, r.bottom)].map(Math.round)); });
  if (!rects.length) return [[160, 220, 1760, 900]];
  return rects;
}"""


def render_pages(browser, pids):
    script = load_script()
    pg = browser.new_page(viewport={"width": 1920, "height": 1080})
    pg.add_init_script(init_script())
    for pid in pids:
        d = OUT / "pages"
        d.mkdir(parents=True, exist_ok=True)
        focus = {}
        for s in page_steps(script, pid):
            pg.goto(f"file://{ROOT}/pages/{pid}.html?step={s}")
            pg.wait_for_selector("body[data-ready='1']")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(60)
            pg.screenshot(path=str(d / f"{pid}_s{s}.png"))
            focus[str(s)] = pg.evaluate(FOCUS_JS, s)
            print("rendered", pid, s, flush=True)
        (d / f"{pid}_focus.json").write_text(json.dumps(focus))
    pg.close()


def sheet(pids):
    from PIL import Image
    script = load_script()
    ims = []
    for pid in pids:
        for s in page_steps(script, pid):
            ims.append(Image.open(OUT / "pages" / f"{pid}_s{s}.png").convert("RGB"))
    w, h = 960, 540
    cols = 2
    rows = (len(ims) + cols - 1) // cols
    sh = Image.new("RGB", (w * cols, h * rows), "white")
    for i, im in enumerate(ims):
        sh.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sh.save(OUT / "sheet.png")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "sheet":
        sheet(sys.argv[2:])
        sys.exit()
    with sync_playwright() as p:
        b = p.chromium.launch(channel=os.environ.get("LECTURE_BROWSER_CHANNEL", "chrome") or None, headless=True)
        if cmd == "mascots":
            render_mascots(b)
        elif cmd == "pages":
            render_pages(b, sys.argv[2:])
        b.close()
