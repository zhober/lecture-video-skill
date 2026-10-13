"""Write the narration as paste-ready text for a web TTS platform (default 豆包语音合成 2.0).

usage: python3 make_tts_inputs.py [NAME] [LIMIT_BYTES]
  NAME   folder label, default 豆包 -> ../配音脚本/豆包_试听.txt, 豆包_全文.txt, 豆包_分段/第NN段.txt
  LIMIT  max UTF-8 bytes per 分段 part (default 1450; a 1.4 KB paste went through the 豆包 console in one piece)

script.json keys used: "tts_instruction" (first line of every file, e.g. <整体情绪：平静，语气：大学老师讲课…>),
"tts_say" (TTS-only rewording, subtitles unchanged), "watch_terms" (terms the 试听 sample must contain).
The user generates audio and saves it as ../配音/NAME/第NN段.wav (or 全文.wav); align_external.py takes it from there."""
import re, shutil, sys
from pathlib import Path
import build

ROOT = Path(__file__).resolve().parent
NAME = sys.argv[1] if len(sys.argv) > 1 else "豆包"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 1450
D = ROOT.parent / "配音脚本"
D.mkdir(exist_ok=True)

sc = build.load_script()
INSTR = sc.get("tts_instruction", "")
SAY = sc.get("tts_say", {})
head = INSTR + "\n" if INSTR else ""


def say(t):
    for k, v in SAY.items():
        t = t.replace(k, v)
    return t


pages = [say("".join(b["text"] for b in p["beats"])) for p in sc["pages"]]
sents = [say(s) for p in sc["pages"] for b in p["beats"] for s in build.sentences(b["text"])]

# 试听: the sentences densest in English terms, plus one sentence for every watch_term
terms = sc.get("watch_terms", [])
pick = sorted(range(len(sents)), key=lambda i: -len(re.findall(r"[A-Za-z][A-Za-z0-9\-]*", sents[i])))[:15]
for t in terms:
    hit = next((i for i, s in enumerate(sents) if t in s), None)
    if hit is not None and hit not in pick:
        pick.append(hit)
(D / f"{NAME}_试听.txt").write_text(head + "\n".join(sents[i] for i in sorted(pick)), encoding="utf-8")
(D / f"{NAME}_全文.txt").write_text(head + "\n\n".join(pages), encoding="utf-8")

parts, cur = [], []
for t in pages:
    if cur and len("\n\n".join(cur + [t]).encode()) > LIMIT:
        parts.append(cur); cur = []
    cur.append(t)
parts.append(cur)
sub = D / f"{NAME}_分段"
shutil.rmtree(sub, ignore_errors=True); sub.mkdir()
for i, c in enumerate(parts, 1):
    (sub / f"第{i:02d}段.txt").write_text(head + "\n\n".join(c), encoding="utf-8")
print(f"试听 {len(pick)} 句; 全文 {sum(len(p) for p in pages)} 字; 分段 {len(parts)} 段, bytes:",
      [len("\n\n".join(c).encode()) for c in parts])
print("wrote", D)
