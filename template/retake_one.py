"""Put a single-sentence re-take in place of one new sentence, leaving every other clip as it is
(re-running cut_new_takes.py would cut all sentences again and lose hand-made cuts such as sentence 7's).
usage: python3 retake_one.py N [take.wav] [--round vN]   default round v3, default take 配音/豆包_补录<round>/第N句.wav
       -> cache/clips_<round>/<md5>.wav and that round's check.json entry N, checked with both ASR models.
The take holds only that sentence, so it is trimmed at its voice edges rather than aligned by characters (the
alignment cuts short when the take reads a tts_say spelling, e.g. digits as Chinese numerals). The ends get short
fades: web-TTS exports may start on a non-zero sample or stop right at the last vowel."""
import difflib, hashlib, json, re, sys, wave
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent
sys.argv, argv = [sys.argv[0]], sys.argv[1:]
import patch_sentences as ps
from faster_whisper import WhisperModel
import zhconv

RND = "v3"
if "--round" in argv:
    i = argv.index("--round"); RND = argv[i + 1]; del argv[i:i + 2]
OUT = ROOT / "cache" / f"clips_{RND}"
n = int(argv[0])
take = Path(argv[1]) if len(argv) > 1 else ROOT.parent / "配音" / f"豆包_补录{RND}" / f"第{n}句.wav"
chk = json.loads((OUT / "check.json").read_text())
r = next(x for x in chk if x["n"] == n)
s = r["text"]
said = s
for k, v in ps.SAY.items():          # the text as the take reads it
    said = said.replace(k, v)

pcm = ps.to_wav(take, OUT / "take_one.wav")
v0, v1 = ps.voice_edges(pcm)
a0, a1 = max(0, int((v0 - 0.04) * ps.SR)), min(len(pcm), int((v1 + 0.06) * ps.SR))
clip = pcm[a0:a1].astype(np.float64)
fi, fo = min(int(0.03 * ps.SR), int((v0 * ps.SR - a0) * 0.8)), int(0.015 * ps.SR)
if fi > 0:
    clip[:fi] *= np.linspace(0, 1, fi)
clip[-fo:] *= np.linspace(1, 0, fo)
clip = clip.astype(np.int16)
f = OUT / f"{hashlib.md5(s.encode()).hexdigest()[:12]}.wav"
with wave.open(str(f), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(ps.SR); w.writeframes(clip.tobytes())

norm = lambda t: re.sub(r"[^一-鿿A-Za-z0-9]", "", zhconv.convert(t, "zh-cn")).lower()
a = clip.astype(np.float32) / 32768
a16 = np.interp(np.arange(0, len(a), ps.SR / 16000), np.arange(len(a)), a).astype(np.float32)
hyp, rat, lenr = {}, {}, {}
for name, path in (("turbo", ps.TURBO), ("small", "small")):
    m = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=10)
    segs, _ = m.transcribe(a16, language="zh", beam_size=5, condition_on_previous_text=False,
                           initial_prompt="以下是普通话的生物信息学课程讲解。")
    hyp[name] = zhconv.convert("".join(x.text for x in segs), "zh-cn")
    # the ASR may write numbers either way, so score against both spellings
    rat[name] = max(difflib.SequenceMatcher(None, norm(t), norm(hyp[name]), autojunk=False).ratio() for t in (s, said))
    lenr[name] = len(norm(hyp[name])) / max(1, len(norm(s)))
ok = not (min(rat.values()) < 0.8 and max(rat.values()) < 0.9) and min(lenr.values()) < 1.25
r.update({"wav": str(f), "dur": round(len(clip) / ps.SR, 2), "ratio": rat, "len": lenr, "asr": hyp, "ok": ok,
          "manual": f"single-sentence retake {take.name}, trimmed at voice edges {v0:.2f}-{v1:.2f} s"})
(OUT / "check.json").write_text(json.dumps(chk, ensure_ascii=False, indent=1))
print(f"{n:2d} {'ok ' if ok else 'BAD'} {len(clip) / ps.SR:5.2f}s T={rat['turbo']:.2f} S={rat['small']:.2f}  {s}\n"
      f"      T: {hyp['turbo']}\n      S: {hyp['small']}\n  -> {f}")
