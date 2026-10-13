"""Write the narration transcript (Markdown) with per-page timestamps from a video timeline.

usage: python3 make_docs.py TIMELINE.json OUT.md
"""

import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def mmss(t):
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def main(tl_path, out):
    script = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
    tl = json.loads(Path(tl_path).read_text(encoding="utf-8"))
    starts = {}
    for t0, t1, pid, step, *_ in tl["segments"]:
        starts.setdefault(pid, [t0, t1])
        starts[pid][1] = t1
    lines = [f"# {script.get('title', '教学视频')} —— 视频逐字稿", "",
             f"{script.get('subtitle', '')}全片时长 {mmss(tl['total'])}。", ""]
    chapter = None
    for n, page in enumerate(script["pages"], 1):
        pid = page["id"]
        ch = page.get("chapter") or "开场"
        if ch != chapter:
            lines += [f"## {ch}", ""]
            chapter = ch
        t0, t1 = starts.get(pid, [0, 0])
        lines += [f"### {n}. {page.get('title', '')}　`{mmss(t0)}–{mmss(t1)}`", ""]
        for b in page["beats"]:
            lines.append(b["text"])
            lines.append("")
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
