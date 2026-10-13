"""Check subtitle/audio sync of a built video: transcribe SRT cue windows and compare with the cue text.

usage: python3 sync_check.py NAME [N_RANDOM] [KEYWORD ...]
  reads out/NAME.srt and out/NAME.wav; checks N_RANDOM random cues (default 30) plus every cue containing a KEYWORD
  (use the first words of patched sentences). Expect mean >= 0.9 and nothing below 0.6; low cues are usually
  ASR spelling of English terms, so read them rather than trusting the number."""
import difflib, os, random, sys
import numpy as np
import build
from align_external import norm_chars

name = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
keys = sys.argv[3:]
model_path = os.environ.get("LECTURE_ASR_MODEL", "large-v3-turbo")


def ts(x):
    h, m, s = x.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


cues = []
for block in (build.OUT / f"{name}.srt").read_text(encoding="utf-8").strip().split("\n\n"):
    L = block.split("\n")
    a, b = L[1].split(" --> ")
    cues.append((ts(a), ts(b), "".join(L[2:])))
pcm = build.read_wav(build.OUT / f"{name}.wav").astype(np.float32) / 32768
a16 = np.interp(np.linspace(0, len(pcm) - 1, int(len(pcm) * 16000 / build.SR)), np.arange(len(pcm)), pcm).astype(np.float32)

from faster_whisper import WhisperModel
m = WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=10)
marked = {i for i, c in enumerate(cues) if any(k in c[2] for k in keys)}
random.seed(7)
pick = sorted(marked | set(random.sample(range(len(cues)), min(n, len(cues)))))
rs = []
for i in pick:
    t0, t1, txt = cues[i]
    seg, _ = m.transcribe(a16[int(t0 * 16000):int(t1 * 16000)], language="zh", beam_size=3, condition_on_previous_text=False)
    hyp = "".join(s.text for s in seg)
    r = difflib.SequenceMatcher(None, norm_chars(txt), norm_chars(hyp)).ratio()
    rs.append(r)
    print(f"{'*' if i in marked else ' '} {t0:7.1f}-{t1:7.1f} r={r:.2f} | {txt} | {hyp}")
print(f"mean {np.mean(rs):.3f}  n {len(rs)}  below 0.6: {sum(r < 0.6 for r in rs)}  ({len(cues)} cues, model {os.path.basename(model_path)})")
