"""Align externally generated narration audio (per page P01.mp3 ... or one 全文 file) to script sentences.
Writes cache/external/align.json: {pid: {"wav": path, "sentences": [[t0, t1], ...]}} (times within that page's wav)."""
import difflib, json, re, subprocess, sys, wave
from pathlib import Path
import numpy as np
import build
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "配音"
CACHE = ROOT / "cache" / "external"
CACHE.mkdir(parents=True, exist_ok=True)


def norm_chars(s):
    return [c for c in s.lower() if re.match(r"[\w一-鿿]", c) and c != "_"]


def to_wav(src, dst):
    subprocess.run([build.FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(build.SR), str(dst)], check=True)
    with wave.open(str(dst)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def _cut_points(a, sr, max_len=25.0):
    """split points at the quietest 20 ms frame near every max_len window end"""
    hop = int(0.02 * sr)
    fr = a[: len(a) // hop * hop].reshape(-1, hop)
    rms = np.sqrt((fr ** 2).mean(1))
    pts, start = [0], 0
    n = len(rms)
    while (n - start) * 0.02 > max_len:
        lo, hi = start + int((max_len - 8) / 0.02), start + int(max_len / 0.02)
        k = lo + int(np.argmin(rms[lo:hi]))
        pts.append(k * hop); start = k
    pts.append(len(a))
    return pts


def char_times(model, pcm):
    a = pcm.astype(np.float32) / 32768
    a16 = np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / build.SR)), np.arange(len(a)), a).astype(np.float32)
    chars, times = [], []
    pts = _cut_points(a16, 16000)
    for s0, s1 in zip(pts[:-1], pts[1:]):
        segs, _ = model.transcribe(a16[s0:s1], language="zh", beam_size=5, word_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=False,
                                   initial_prompt="以下是普通话的生物信息学课程讲解。")
        off = s0 / 16000
        for s in segs:
            for w in s.words:
                cs = norm_chars(w.word)
                for i, c in enumerate(cs):
                    chars.append(c)
                    times.append(off + w.start + (w.end - w.start) * (i + 0.5) / max(1, len(cs)))
    return chars, times


def align(sentences, chars, times, total):
    ref, owner = [], []
    for k, s in enumerate(sentences):
        cs = norm_chars(s)
        ref += cs; owner += [k] * len(cs)
    m = difflib.SequenceMatcher(None, ref, chars, autojunk=False)
    t_of = [None] * len(ref)
    for a, b, n in m.get_matching_blocks():
        for i in range(n):
            t_of[a + i] = times[b + i]
    known = [i for i, t in enumerate(t_of) if t is not None]
    coverage = len(known) / max(1, len(ref))
    if not known:
        raise RuntimeError("alignment failed")
    for i in range(len(ref)):  # interpolate gaps
        if t_of[i] is None:
            lo = max([k for k in known if k < i], default=None); hi = min([k for k in known if k > i], default=None)
            if lo is None: t_of[i] = t_of[hi]
            elif hi is None: t_of[i] = t_of[lo]
            else: t_of[i] = t_of[lo] + (t_of[hi] - t_of[lo]) * (i - lo) / (hi - lo)
    spans = []
    for k in range(len(sentences)):
        idx = [i for i, o in enumerate(owner) if o == k]
        spans.append([max(0.0, t_of[idx[0]] - 0.12), min(total, t_of[idx[-1]] + 0.25)])
    for k in range(1, len(spans)):  # keep order / no overlap
        if spans[k][0] < spans[k - 1][1]:
            mid = (spans[k][0] + spans[k - 1][1]) / 2
            spans[k - 1][1] = spans[k][0] = mid
    return spans, coverage


def snap_to_silence(spans, pcm, win=0.8, min_sil=0.12):
    """Move sentence starts/ends to the nearest edge of a silent run (20 ms frames)."""
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
            if (j - i) * 0.02 >= min_sil:
                runs.append((i * 0.02, j * 0.02))
            i = j
        else:
            i += 1
    out = []
    for s0, s1 in spans:
        ends = [r0 for r0, r1 in runs if abs(r0 - s1) <= win]
        starts = [r1 for r0, r1 in runs if abs(r1 - s0) <= win]
        n1 = min(ends, key=lambda x: abs(x - s1)) if ends else s1
        n0 = min(starts, key=lambda x: abs(x - s0)) if starts else s0
        if n1 - n0 < 0.3:
            n0, n1 = s0, s1
        out.append([max(0.0, n0 - 0.03), n1 + 0.05])
    for k in range(1, len(out)):
        if out[k][0] < out[k - 1][1]:
            mid = (out[k][0] + out[k - 1][1]) / 2
            out[k - 1][1] = out[k][0] = mid
    return out


def prep_part(pcm, edge=0.15, max_pause=1.0, keep=0.8, lufs=-20.0):
    """one externally generated part: trim lead/trail silence to `edge`, shorten pauses > max_pause to `keep`,
    normalise loudness so parts made in separate sessions match"""
    import pyloudnorm
    hop = int(0.02 * build.SR)
    fr = pcm[: len(pcm) // hop * hop].astype(np.float32).reshape(-1, hop)
    rms = np.sqrt((fr ** 2).mean(1)) + 1e-6
    loud = np.where(rms >= max(np.percentile(rms, 20) * 2.5, rms.max() * 0.02))[0]
    if not len(loud):
        return pcm
    a = pcm[max(0, loud[0] * hop - int(edge * build.SR)): (loud[-1] + 1) * hop + int(edge * build.SR)]
    out, prev = [], 0
    gaps = np.diff(loud) - 1  # silent frames between voiced frames
    lead = max(0, loud[0] * hop - int(edge * build.SR))
    for i in np.where(gaps * 0.02 > max_pause)[0]:
        g0, g1 = (loud[i] + 1) * hop - lead, loud[i + 1] * hop - lead
        half = int(keep * build.SR / 2)
        out += [a[prev:g0 + half], a[g1 - half:g1]]; prev = g1
    a = np.concatenate(out + [a[prev:]]).astype(np.float64) / 32768
    gain = 10 ** ((lufs - pyloudnorm.Meter(build.SR).integrated_loudness(a)) / 20)
    gain = min(gain, 0.97 / max(1e-6, np.abs(a).max()))
    return np.clip(a * gain * 32768, -32768, 32767).astype(np.int16)


def main():
    script = build.load_script()
    pages = script["pages"]
    cov = SRC / "coverage.json"
    if cov.exists():
        keep = set(json.loads(cov.read_text())["pages"])
        pages = [p for p in pages if p["id"] in keep]
        print("restricting to", len(pages), "covered pages")
    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=10)
    files = {p.stem.upper(): p for p in SRC.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")}
    result = {}
    whole = next((v for k, v in files.items() if k in ("全文", "ALL", "FULL")), None)
    per_page = any(f"P{n:02d}" in files for n in range(1, len(pages) + 1))
    if not whole and not per_page and files:   # several parts (e.g. 第1段..第4段): concatenate in natural order
        def nat(p): return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.stem)]
        parts = sorted(files.values(), key=nat)
        print("concatenating parts:", [p.name for p in parts])
        pcs = []
        for i, f in enumerate(parts):
            pcs += [prep_part(to_wav(f, CACHE / f"part{i}.wav")), np.zeros(int(0.45 * build.SR), np.int16)]
        cat = np.concatenate(pcs)
        with wave.open(str(CACHE / "parts_concat.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(build.SR); w.writeframes(cat.tobytes())
        whole = CACHE / "parts_concat.wav"
    if whole and not per_page:
        pcm = to_wav(whole, CACHE / "whole.wav")
        chars, times = char_times(model, pcm)
        sents = [(p["id"], s) for p in pages for b in p["beats"] for s in build.sentences(b["text"])]
        spans, cov = align([s for _, s in sents], chars, times, len(pcm) / build.SR)
        spans = snap_to_silence(spans, pcm)
        print("whole-file alignment coverage", round(cov, 3))
        for pid in dict.fromkeys(p for p, _ in sents):  # cut per page
            ks = [i for i, (p, _) in enumerate(sents) if p == pid]
            a0, a1 = max(0, spans[ks[0]][0] - 0.2), spans[ks[-1]][1] + 0.2
            seg = pcm[int(a0 * build.SR):int(a1 * build.SR)]
            out = CACHE / f"{pid}.wav"
            with wave.open(str(out), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(build.SR); w.writeframes(seg.tobytes())
            result[pid] = {"wav": str(out), "sentences": [[spans[i][0] - a0, spans[i][1] - a0] for i in ks]}
    else:
        for n, p in enumerate(pages, 1):
            key = f"P{n:02d}"
            if key not in files:
                print("missing", key); continue
            pcm = to_wav(files[key], CACHE / f"{p['id']}.wav")
            chars, times = char_times(model, pcm)
            sents = [s for b in p["beats"] for s in build.sentences(b["text"])]
            spans, cov = align(sents, chars, times, len(pcm) / build.SR)
            spans = snap_to_silence(spans, pcm)
            print(key, p["id"], f"{len(pcm)/build.SR:.1f}s", "coverage", round(cov, 3), flush=True)
            result[p["id"]] = {"wav": str(CACHE / f"{p['id']}.wav"), "sentences": spans}
    (CACHE / "align.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print("aligned pages:", len(result))


if __name__ == "__main__":
    main()
