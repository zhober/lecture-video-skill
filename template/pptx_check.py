"""Check an exported PPTX against what PowerPoint really draws.

  python3 pptx_check.py render  out/x.pptx        # PowerPoint -> out/x.pdf -> out/x_real/sNN.png  (opens PowerPoint briefly)
  python3 pptx_check.py measure out/x.pptx [--calibrate]
        compares every text box's intended baseline/left (out/x.pptx.boxes.json, written by export_pptx.py)
        with where PowerPoint put the glyphs in its PDF export; --calibrate stores the baseline factors
        in cache/pptx_calibration.json for the next export
  python3 pptx_check.py sheet   out/x.pptx N [M ...]   # side-by-side: Chrome reference | PowerPoint | difference

PowerPoint is sandboxed: it can save next to the deck in this project, not into /tmp or other apps' folders.
"""

import json, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def paths(pptx):
    pptx = Path(pptx).resolve()
    return pptx, pptx.with_suffix(".pdf"), pptx.parent / (pptx.stem + "_real"), Path(str(pptx) + ".boxes.json")


def render(pptx):
    pptx, pdf, pngdir, _ = paths(pptx)
    if pdf.exists():
        pdf.unlink()
    osa = f'''
with timeout of 300 seconds
tell application "Microsoft PowerPoint"
  open (POSIX file "{pptx}")
  delay 3
  save active presentation in (POSIX file "{pdf}") as save as PDF
  close active presentation saving no
end tell
end timeout'''
    subprocess.run(["osascript", "-e", osa], check=True, capture_output=True)
    import pymupdf
    pngdir.mkdir(exist_ok=True)
    for f in pngdir.glob("s*.png"):
        f.unlink()
    d = pymupdf.open(str(pdf))
    for i, p in enumerate(d):
        z = 1920 / p.rect.width
        p.get_pixmap(matrix=pymupdf.Matrix(z, z)).save(str(pngdir / f"s{i + 1:02d}.png"))
    print("rendered", d.page_count, "slides ->", pngdir)


def pdf_chars(pdf):
    import pymupdf
    d = pymupdf.open(str(pdf))
    out = []
    for p in d:
        z = 1920 / p.rect.width
        chars = []
        for b in p.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    for c in s["chars"]:
                        if c["c"].strip():
                            chars.append((c["c"], c["origin"][0] * z, c["origin"][1] * z, s["size"] * z, s["font"], c["bbox"][2] * z))
        out.append(chars)
    return out


def measure(pptx, calibrate=False):
    pptx, pdf, _, bj = paths(pptx)
    rec = json.loads(bj.read_text())
    pages = pdf_chars(pdf)
    stats = {"sans": [], "mono": []}
    per_size, ends, per_char = {}, [], {}
    bad, missing, n = [], [], 0
    for sl in rec:
        chars = pages[sl["slide"] - 1]
        for bx in sl["boxes"]:
            t = bx["text"].strip()
            if not t:
                continue
            n += 1
            # leading spaces shift the first glyph right in both renderers, so match on the first visible char
            lead = len(bx["text"]) - len(bx["text"].lstrip())
            seq = [c for c in t.replace(" ", "")][:4]
            best = None
            for i, c in enumerate(chars):
                if c[0] != seq[0] or abs(c[2] - bx["base"]) > 60 or abs(c[1] - bx["left"]) > 200 + lead * bx["size"]:
                    continue
                follow = [x[0] for x in chars[i:i + len(seq)]]
                score = sum(a == b for a, b in zip(follow, seq))
                dist = abs(c[2] - bx["base"]) + abs(c[1] - bx["left"]) / 4
                key = (-score, dist)
                if best is None or key < best[0]:
                    best = (key, c)
            if best is None or -best[0][0] < min(2, len(seq)):
                missing.append((sl["slide"], sl["pid"], t[:30]))
                continue
            c = best[1]
            dy = c[2] - bx["base"]
            stats[bx["kind"]].append(dy / bx["size"])
            per_size.setdefault(bx["kind"], {}).setdefault(round(bx["size"], 1), []).append(dy)
            # end of line: last visible char's right edge vs Chrome's right edge
            i0 = chars.index(c)
            tail = [x for x in chars[i0:i0 + len(t.replace(" ", ""))]]
            if len(tail) == len(t.replace(" ", "")) and "".join(x[0] for x in tail) == t.replace(" ", "") and len(tail) > 8:
                ends.append((tail[-1][5] - bx["right"], sl["slide"], sl["pid"], t[:30]))
                per_char.setdefault(bx["kind"], {}).setdefault(round(bx["size"], 1), []).append((tail[-1][5] - bx["right"]) / len(bx["text"]))
            if lead == 0:
                dx = c[1] - bx["left"]
            else:
                dx = 0.0
            if abs(dy) > 2 or abs(dx) > 3:
                bad.append((sl["slide"], sl["pid"], round(dx, 1), round(dy, 1), t[:30]))
    print(f"{n} boxes; not found in PDF: {len(missing)}; off by >2 px vertically or >3 px horizontally: {len(bad)}")
    for k, v in stats.items():
        if v:
            print(f"  {k}: median dy/size {statistics.median(v):+.4f}  (n={len(v)})")
    for m in missing[:40]:
        print("  missing", m)
    for b in bad[:60]:
        print("  off", b)
    if ends:
        ev = [e[0] for e in ends]
        print(f"  line ends vs Chrome (n={len(ev)}): median {statistics.median(ev):+.2f} px, worst {max(ev, key=abs):+.2f}")
        for e in sorted(ends, key=lambda e: -abs(e[0]))[:8]:
            print("   ", round(e[0], 1), e[1:])
    for k, d in per_size.items():
        print(" ", k, " ".join(f"{sz}:{statistics.median(v):+.1f}" for sz, v in sorted(d.items())))
    if calibrate:
        f = ROOT / "cache" / "pptx_calibration.json"
        cal = json.loads(f.read_text()) if f.exists() else {}
        for k, d in per_size.items():
            tab = cal.setdefault(k, {})
            for sz, v in d.items():
                tab[str(sz)] = round(tab.get(str(sz), 0.0) + statistics.median(v), 2)
        for k, d in per_char.items():
            tab = cal.setdefault(k + "_w", {})
            for sz, v in d.items():
                tab[str(sz)] = round(tab.get(str(sz), 0.0) + statistics.median(v), 4)
        f.write_text(json.dumps(cal))
        print("calibration updated:", f)


def sheet(pptx, slides):
    from PIL import Image, ImageChops, ImageOps
    pptx, _, pngdir, bj = paths(pptx)
    rec = {r["slide"]: r for r in json.loads(bj.read_text())}
    rows = []
    for s in slides:
        r = rec[s]
        ref = Image.open(ROOT / "out" / "pptx" / f"{r['pid']}_s{r['step']}_ref.png").convert("RGB")
        ppt = Image.open(pngdir / f"s{s:02d}.png").convert("RGB").resize(ref.size)
        diff = ImageOps.invert(ImageChops.difference(ref, ppt).convert("L").point(lambda v: 255 if v > 60 else v * 3)).convert("RGB")
        row = Image.new("RGB", (2880, 540), "white")
        for i, im in enumerate((ref, ppt, diff)):
            row.paste(im.resize((960, 540)), (i * 960, 0))
        rows.append(row)
    out = Image.new("RGB", (2880, 540 * len(rows)), "white")
    for i, r in enumerate(rows):
        out.paste(r, (0, i * 540))
    dst = pngdir / f"sheet_{'_'.join(map(str, slides))}.png"
    out.save(dst)
    print(dst)


if __name__ == "__main__":
    cmd, f = sys.argv[1], sys.argv[2]
    if cmd == "render":
        render(f)
    elif cmd == "measure":
        measure(f, "--calibrate" in sys.argv)
    elif cmd == "sheet":
        sheet(f, [int(x) for x in sys.argv[3:]])
