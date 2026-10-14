"""Assemble per-page narration for the current script.json from sentence clips:
reused sentences from cache/clips_v2 (cut from the approved 豆包 audio), new ones from the 补录 rounds
cache/clips_v3, clips_v4, … (cut_new_takes.py --round vN; a later round wins for the same sentence).
An approved re-take in a round also replaces a reused cache/clips_v2 clip of the same sentence.
Writes cache/external/<pid>.wav and cache/external/align.json directly (exact sentence spans, no ASR
alignment needed). New clips are loudness-matched to the reused ones.
usage: python3 assemble_v3.py [--allow-bad]"""
import hashlib, json, re, statistics, sys, wave
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent
allow_bad = "--allow-bad" in sys.argv
sys.argv = [sys.argv[0]]
import patch_sentences as ps
import build

SR = build.SR
GAP = 0.3                      # base silence between sentences; script.json "pace" widens it at build time
key = lambda t: re.sub(r'[\s，。、；：！？,.;:!?“”"（）()]', '', t)
old = json.loads((ROOT / "cache/clips_v2/index.json").read_text())
chk = {}
for cj in sorted((ROOT / "cache").glob("clips_v*/check.json"), key=lambda p: int(p.parent.name[7:])):
    chk.update({r["text"]: r for r in json.loads(cj.read_text())})
read = lambda f: build.read_wav(f)
ref_lufs = statistics.median(ps.lufs(read(v["wav"])) for v in list(old.values())[:60])
out = ROOT / "cache" / "external"; out.mkdir(parents=True, exist_ok=True)
align, missing = {}, []
for page in build.load_script()["pages"]:
    pcs, spans, t = [], [], 0.0
    for s in [s for b in page["beats"] for s in build.sentences(b["text"])]:
        if key(s) in old and not (s in chk and chk[s].get("ok") and "wav" in chk[s]):
            o = old[key(s)]; clip = read(o["wav"]); a0, a1 = o["speech"]
        else:
            r = chk.get(s)
            if not r or "wav" not in r or (not r["ok"] and not allow_bad):
                missing.append((page["id"], s)); continue
            clip = read(r["wav"])
            clip = np.clip(clip.astype(np.float64) * 10 ** ((ref_lufs - ps.lufs(clip)) / 20), -32768, 32767).astype(np.int16)
            v0, v1 = ps.voice_edges(clip); a0, a1 = v0, v1
        if pcs:
            pcs.append(np.zeros(int(GAP * SR), np.int16)); t += GAP
        spans.append([t + a0, t + a1]); pcs.append(clip); t += len(clip) / SR
    pcm = np.concatenate(pcs)
    f = out / f"{page['id']}.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    align[page["id"]] = {"wav": str(f), "sentences": spans}
(out / "align.json").write_text(json.dumps(align, ensure_ascii=False, indent=1))
print(f"{len(align)} pages assembled, ref loudness {ref_lufs:.1f} LUFS")
for m in missing:
    print("MISSING / not ok:", m)
