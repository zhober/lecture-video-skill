"""Cut the 补录 takes (配音/豆包_补录v3/*.wav, natural order) into the new sentences listed in
cache/clips_v2/new_lines.json and check each clip with two ASR models.
usage: python3 cut_new_takes.py [take_dir]      -> cache/clips_v3/<md5>.wav + cache/clips_v3/check.json"""
import difflib, hashlib, json, re, sys, wave
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent
sys.argv, argv = [sys.argv[0]], sys.argv[1:]
import patch_sentences as ps
from faster_whisper import WhisperModel
import zhconv

TAKES = Path(argv[0]) if argv else ROOT.parent / "配音" / "豆包_补录v3"
OUT = ROOT / "cache" / "clips_v3"; OUT.mkdir(parents=True, exist_ok=True)
plan = json.loads((ROOT / "cache" / "clips_v2" / "new_lines.json").read_text())
sents = [s for pl in plan for s in pl["sentences"]]
files = sorted([f for f in TAKES.iterdir() if f.suffix.lower() == ".wav" and not re.match(r"第\d+句", f.stem)], key=ps.nat)
pcm = np.concatenate([np.concatenate([ps.to_wav(f, OUT / f"take{i}.wav"), np.zeros(int(0.5 * ps.SR), np.int16)]) for i, f in enumerate(files)])
turbo = WhisperModel(ps.TURBO, device="cpu", compute_type="int8", cpu_threads=10)
clips = ps.cut_lines(turbo, pcm, sents)
# single-sentence overrides: 第N句.wav replaces sentence N
for f in TAKES.glob("第*句.wav"):
    n = int(re.match(r"第(\d+)句", f.stem).group(1)) - 1
    clips[n] = ps.cut_lines(turbo, ps.to_wav(f, OUT / "take_one.wav"), [sents[n]])[0]
small = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=10)
norm = lambda t: re.sub(r"[^一-鿿A-Za-z0-9]", "", zhconv.convert(t, "zh-cn")).lower()
res = []
for i, (s, (clip, r)) in enumerate(zip(sents, clips), 1):
    if clip is None:
        res.append({"n": i, "text": s, "ok": False, "why": "not found"}); print(i, "NOT FOUND", s); continue
    h = hashlib.md5(s.encode()).hexdigest()[:12]
    f = OUT / f"{h}.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(ps.SR); w.writeframes(clip.tobytes())
    a = clip.astype(np.float32) / 32768
    a16 = np.interp(np.arange(0, len(a), ps.SR / 16000), np.arange(len(a)), a).astype(np.float32)
    hyp = {}
    for name, m in (("turbo", turbo), ("small", small)):
        segs, _ = m.transcribe(a16, language="zh", beam_size=5, condition_on_previous_text=False,
                               initial_prompt="以下是普通话的生物信息学课程讲解。")
        hyp[name] = zhconv.convert("".join(x.text for x in segs), "zh-cn")
    rat = {k: difflib.SequenceMatcher(None, norm(s), norm(v), autojunk=False).ratio() for k, v in hyp.items()}
    lenr = {k: len(norm(v)) / max(1, len(norm(s))) for k, v in hyp.items()}
    ok = not (min(rat.values()) < 0.8 and max(rat.values()) < 0.9) and min(lenr.values()) < 1.25
    res.append({"n": i, "text": s, "wav": str(f), "dur": round(len(clip) / ps.SR, 2), "ratio": rat, "len": lenr, "asr": hyp, "ok": ok})
    print(f"{i:2d} {'ok ' if ok else 'BAD'} {len(clip)/ps.SR:5.1f}s T={rat['turbo']:.2f} S={rat['small']:.2f}  {s}\n      T: {hyp['turbo']}\n      S: {hyp['small']}")
(OUT / "check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
