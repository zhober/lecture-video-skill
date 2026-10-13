"""Draw the highlight ring each step will get in the video onto that step's page render, for checking.

usage: python3 focus_preview.py p13 [p17 ...]      (run render.py pages first so pNN_focus.json is fresh)
writes out/focus/<pid>_s<N>.png (ring in orange, its pixel box printed) and out/focus/<pid>_sheet.png
Same logic and the same ring drawing as build.py: beat "focus" overrides, else cluster_focus over the step's
data-focus / newly shown elements; no ring for beats with "hl": false or when only the fallback box is available.
A beat's "ring_at" phrase (the ring waits for the narration to reach it) is shown in the label.
"""

import importlib.util, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
build = importlib.util.module_from_spec(spec)
sys.argv, argv = [sys.argv[0]], sys.argv[1:]
spec.loader.exec_module(build)

OUT = ROOT / "out" / "focus"
OUT.mkdir(parents=True, exist_ok=True)
script = build.load_script()
font = ImageFont.truetype(build.SUB_FONT, 26, index=build.SUB_FONT_INDEX)
for pid in argv:
    page = next(p for p in script["pages"] if p["id"] == pid)
    fj = build.load_focus(pid)
    tiles = []
    for b in page["beats"]:
        st = b.get("step", 1)
        focus = b.get("focus") or build.cluster_focus(fj.get(str(st))) or build.DEFAULT_FOCUS
        ring = b.get("hl", True) and focus != build.DEFAULT_FOCUS
        im = Image.open(ROOT / "out" / "pages" / f"{pid}_s{st}.png").convert("RGB")
        d = ImageDraw.Draw(im)
        if ring:
            x0, y0, x1, y1 = focus
            hx, hy, layers = build.highlight_layers(focus)
            im.paste(layers[-1], (hx, hy), layers[-1])
            label = f"step {st}  ring {focus}  area {(x1 - x0) * (y1 - y0) / (1808 * 710):.0%}"
            if b.get("ring_at"):
                label += f"  at「{b['ring_at']}」"
        else:
            label = f"step {st}  (no ring)"
        d.rectangle((0, 1000, 1920, 1080), fill=(43, 45, 66))
        d.text((20, 1008), label, font=font, fill=(255, 255, 255))
        d.text((20, 1044), b["text"][:70], font=font, fill=(242, 190, 54))
        im.save(OUT / f"{pid}_s{st}.png")
        tiles.append(im.resize((960, 540)))
        print(pid, st, "ring" if ring else "none", focus)
    sheet = Image.new("RGB", (1920, 540 * ((len(tiles) + 1) // 2)), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * 960, (i // 2) * 540))
    sheet.save(OUT / f"{pid}_sheet.png")
