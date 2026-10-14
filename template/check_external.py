"""Check externally generated narration parts (第01段.wav ...) against script.json before building the video:
which sentences each part covers, missing / extra / misread text, English-term hits, spoken length of script.json "watch_terms", and per-part
pace, pitch, loudness, pauses. usage: python3 check_external.py DIR [whisper-model-or-path]
Writes cache/external/check.json and prints a report."""
import difflib, json, re, sys
from pathlib import Path
import numpy as np
import build
from align_external import to_wav, norm_chars, _cut_points

ROOT = Path(__file__).resolve().parent
if __name__ == "__main__":
    SRC = Path(sys.argv[1])
    MODEL = sys.argv[2] if len(sys.argv) > 2 else "small"
    CACHE = ROOT / "cache" / "external" / "check" / SRC.name   # per source folder: patched copies share file names
    CACHE.mkdir(parents=True, exist_ok=True)
EN = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")


def nat(p):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.stem)]


def asr_words(model, pcm):
    """[(word, t0, t1)] over ≤25 s windows cut at quiet frames"""
    a = pcm.astype(np.float32) / 32768
    a16 = np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / build.SR)), np.arange(len(a)), a).astype(np.float32)
    out = []
    pts = _cut_points(a16, 16000)
    for s0, s1 in zip(pts[:-1], pts[1:]):
        segs, _ = model.transcribe(a16[s0:s1], language="zh", beam_size=5, word_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=False,
                                   initial_prompt="以下是普通话的生物信息学课程讲解。")
        off = s0 / 16000
        out += [(w.word, off + w.start, off + w.end) for s in segs for w in s.words]
    return out


def silences(pcm, min_sil=0.2):
    hop = int(0.02 * build.SR)
    fr = pcm[: len(pcm) // hop * hop].astype(np.float32).reshape(-1, hop)
    rms = np.sqrt((fr ** 2).mean(1)) + 1e-6
    thr = max(np.percentile(rms, 20) * 2.5, rms.max() * 0.02)
    sil = rms < thr
    runs, i = [], 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]:
                j += 1
            if (j - i) * 0.02 >= min_sil or i == 0 or j == len(sil):
                runs.append((i * 0.02, j * 0.02))
            i = j
        else:
            i += 1
    return runs


def audio_stats(path, pcm):
    import parselmouth, pyloudnorm
    a = pcm.astype(np.float64) / 32768
    dur = len(a) / build.SR
    runs = silences(pcm)
    lead = runs[0][1] if runs and runs[0][0] == 0 else 0.0
    trail = dur - runs[-1][0] if runs and abs(runs[-1][1] - dur) < 0.05 else 0.0
    inner = [r1 - r0 for r0, r1 in runs if r0 > 0 and abs(r1 - dur) >= 0.05]
    snd = parselmouth.Sound(a, sampling_frequency=build.SR)
    f0 = snd.to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=500).selected_array["frequency"]
    f0 = f0[f0 > 0]
    st = 12 * np.log2(f0 / np.median(f0)) if len(f0) else np.zeros(1)
    return {"dur": round(dur, 2), "lead": round(lead, 2), "trail": round(trail, 2),
            "max_pause": round(max(inner, default=0), 2), "pauses_gt1s": sum(p > 1.0 for p in inner),
            "speech_time": round(dur - lead - trail - sum(inner), 2),
            "f0_med": round(float(np.median(f0)), 1) if len(f0) else 0, "f0_range_st": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2),
            "lufs": round(float(pyloudnorm.Meter(build.SR).integrated_loudness(a)), 1),
            "peak": round(float(np.abs(a).max()), 3), "clip": int((np.abs(a) > 0.995).sum())}


def main():
    from faster_whisper import WhisperModel
    model = None
    parts = sorted([p for p in SRC.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")], key=nat)
    tag = Path(MODEL).name
    hyp, stats = [], []  # hyp: (char, part, t)
    words_by_part = []
    for k, f in enumerate(parts):
        pcm = to_wav(f, CACHE / f"part{k:02d}.wav")
        cj = CACHE / f"{f.stem}.{tag}.json"
        if cj.exists() and json.loads(cj.read_text())["mtime"] == f.stat().st_mtime:
            words = json.loads(cj.read_text())["words"]
        else:
            model = model or WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=10)
            words = asr_words(model, pcm)
            cj.write_text(json.dumps({"mtime": f.stat().st_mtime, "words": words}, ensure_ascii=False))
        words_by_part.append(words)
        for w, t0, t1 in words:
            cs = norm_chars(w)
            for i, c in enumerate(cs):
                hyp.append((c, k, t0 + (t1 - t0) * (i + 0.5) / max(1, len(cs))))
        s = audio_stats(f, pcm); s["file"] = f.name; stats.append(s)
        print(f"{f.name}: {s['dur']}s  asr {len(words)} words", flush=True)

    script = build.load_script()
    sents = [(p["id"], s) for p in script["pages"] for b in p["beats"] for s in build.sentences(b["text"])]
    ref, owner = [], []
    for k, (_, s) in enumerate(sents):
        cs = norm_chars(s); ref += cs; owner += [k] * len(cs)
    m = difflib.SequenceMatcher(None, ref, [c for c, _, _ in hyp], autojunk=False)
    hit = [None] * len(ref)
    for a, b, n in m.get_matching_blocks():
        for i in range(n):
            hit[a + i] = b + i
    # per sentence: match ratio, parts, the ASR text between neighbours' anchors
    rows = []
    for k, (pid, s) in enumerate(sents):
        idx = [i for i, o in enumerate(owner) if o == k]
        got = [hit[i] for i in idx if hit[i] is not None]
        lo = max([hit[i] for i in range(idx[0]) if hit[i] is not None], default=-1) + 1
        hi = min([hit[i] for i in range(idx[-1] + 1, len(ref)) if hit[i] is not None], default=len(hyp))
        region = hyp[lo:hi]
        asr = "".join(c for c, _, _ in region)
        prts = sorted({p for _, p, _ in region})
        terms = EN.findall(s)
        miss = [t for t in terms if "".join(norm_chars(t)) not in asr]
        rows.append({"pid": pid, "k": k, "text": s, "asr": asr, "ratio": round(len(got) / max(1, len(idx)), 3),
                     "parts": prts, "t": [round(region[0][2], 2), round(region[-1][2], 2)] if region else None,
                     "miss_terms": miss})
    # unmatched hyp runs (extra speech: instruction read aloud, repeats, ad-libs)
    used = set(h for h in hit if h is not None)
    extra, run = [], []
    for j in range(len(hyp) + 1):
        if j < len(hyp) and j not in used:
            run.append(j)
        else:
            if len(run) >= 4:
                extra.append({"part": hyp[run[0]][1], "t": round(hyp[run[0]][2], 2), "text": "".join(hyp[i][0] for i in run)})
            run = []
    # watch_terms (script.json): spoken duration of tricky terms; letter-by-letter reading is ~2x longer
    terms = [t.lower() for t in build.load_script().get("watch_terms", [])]
    atac = []
    for words, f in zip(words_by_part, parts):
        for w, t0, t1 in words:
            if any(t in w.lower().replace(" ", "") for t in terms):
                atac.append({"file": f.name, "word": w, "t": round(t0, 2), "dur": round(t1 - t0, 2)})
    # which script pages does each part cover
    for k, s in enumerate(stats):
        ps = [r for r in rows if r["parts"] and r["parts"][0] == k]
        s["pages"] = sorted({r["pid"] for r in ps}, key=lambda x: (int(re.match(r"p(\d+)", x).group(1)), x))
        s["script_chars"] = sum(len(norm_chars(r["text"])) for r in ps)
        s["cps"] = round(s["script_chars"] / max(0.1, s["speech_time"]), 2)
    json.dump({"stats": stats, "rows": rows, "extra": extra, "watch": atac}, open(CACHE / f"check.{tag}.json", "w"), ensure_ascii=False, indent=1)

    print("\n== per part ==")
    cps = np.array([s["cps"] for s in stats]); f0 = np.array([s["f0_med"] for s in stats])
    for s in stats:
        flag = []
        if abs(s["cps"] - np.median(cps)) > 0.12 * np.median(cps): flag.append("语速偏离")
        if abs(12 * np.log2(s["f0_med"] / np.median(f0))) > 1.5: flag.append("音高偏离")
        if s["max_pause"] > 1.2: flag.append("长停顿")
        if s["clip"]: flag.append("削波")
        print(f"{s['file'][:22]:24s} {s['dur']:6.1f}s cps {s['cps']:.2f} f0 {s['f0_med']:6.1f} rng {s['f0_range_st']:5.1f}st "
              f"{s['lufs']:6.1f}LUFS pk {s['peak']:.2f} lead {s['lead']:.2f} trail {s['trail']:.2f} maxpause {s['max_pause']:.2f} "
              f"pages {','.join(s['pages'])} {' '.join(flag)}")
    print("\n== sentences with ratio < 0.85 or missing terms ==")
    for r in rows:
        if r["ratio"] < 0.85 or r["miss_terms"]:
            print(f"[{r['pid']} #{r['k']} part {r['parts']} t {r['t']}] ratio {r['ratio']} miss {r['miss_terms']}\n  稿: {r['text']}\n  识: {r['asr']}")
    print("\n== extra speech not in script ==")
    for e in extra:
        print(f"  part {e['part']} @{e['t']}: {e['text']}")
    print("\n== watch_terms ==")
    for a in atac:
        print(f"  {a['file'][:10]} @{a['t']:.1f} {a['word']!r} {a['dur']}s")


if __name__ == "__main__":
    main()
