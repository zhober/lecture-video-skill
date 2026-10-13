"""Replace badly read sentences inside externally generated parts with separately regenerated takes.

  python3 patch_sentences.py prepare 5,24,34,35,36-37,41-42   one text line per token (a run of consecutive sentences);
                                                              also split into 配音脚本/<NAME>_补句_N.txt, one per paste
  python3 patch_sentences.py apply                            splice takes into the parts -> 配音/豆包_修补/

Sentence numbers K are check_external.py's global indices (script order, split on 。！？；).
Takes: 配音/豆包_补句/补句.wav holds all lines; 第N行.wav, if present, overrides line N.
Cuts happen only in the pauses around a replaced run: everything between the last kept sentence before it and
the first kept sentence after it (including any garbled insert) is replaced by the takes, with fresh pauses."""
import difflib, json, os, re, shutil, sys, wave
from pathlib import Path
import numpy as np
import build
from align_external import to_wav, norm_chars
from check_external import asr_words, nat

ROOT = Path(__file__).resolve().parent
VO = ROOT.parent / "配音"
NAME = os.environ.get("VOICE_DIR", "豆包")      # 配音/<NAME>/ holds the parts as the user saved them
SRC = VO / NAME
OUT = VO / f"{NAME}_修补"
TAKES = VO / f"{NAME}_补句"
CHECK = ROOT / "cache" / "external" / "check"
PLAN = ROOT / "cache" / "external" / "patch_plan.json"
TXT = ROOT.parent / "配音脚本" / f"{NAME}_补句.txt"
TURBO = os.environ.get("LECTURE_ASR_MODEL", "large-v3-turbo")
ASR_MODEL = TURBO


def asr_tag():
    """prefer the turbo check of SRC, fall back to the small one"""
    for tag in (Path(TURBO).name, "small"):
        if (CHECK / SRC.name / f"check.{tag}.json").exists():
            return tag
    raise SystemExit(f"run check_external.py on {SRC} first")
_CFG = build.load_script()
INSTR = _CFG.get("tts_instruction", "")
SAY = _CFG.get("tts_say", {})     # TTS-only rewording of phrases the platform keeps misreading (subtitles unchanged)
SR = build.SR
AUDIO = (".wav", ".mp3", ".m4a")


def sentences():
    return [s for p in build.load_script()["pages"] for b in p["beats"] for s in build.sentences(b["text"])]


def ownership():
    """sentence index -> part file name, from the turbo check of SRC"""
    chk = json.loads((CHECK / SRC.name / f"check.{asr_tag()}.json").read_text())
    files = [s["file"] for s in chk["stats"]]
    own = [r["parts"][0] if r["parts"] else None for r in chk["rows"]]
    for i in range(len(own)):
        if own[i] is None:
            own[i] = own[i - 1]
    return [files[o] for o in own]


def char_seq(words):
    out = []
    for w, t0, t1 in words:
        cs = norm_chars(w)
        for i, c in enumerate(cs):
            out.append((c, t0 + (t1 - t0) * i / len(cs), t0 + (t1 - t0) * (i + 1) / len(cs)))
    return out


def anchor_times(texts, chars):
    """per text: (first matched char start, last matched char end, matched fraction) or None"""
    ref, owner = [], []
    for k, t in enumerate(texts):
        cs = norm_chars(t); ref += cs; owner += [k] * len(cs)
    m = difflib.SequenceMatcher(None, ref, [c for c, _, _ in chars], autojunk=False)
    got = [[] for _ in texts]
    for a, b, n in m.get_matching_blocks():
        for i in range(n):
            got[owner[a + i]].append(b + i)
    res = []
    for k, g in enumerate(got):
        if not g:
            res.append(None); continue
        # stray single-char matches inside garbled audio: keep only the densest cluster of matched positions
        g = sorted(g); clusters = [[g[0]]]
        for x in g[1:]:
            (clusters[-1].append(x) if x - clusters[-1][-1] <= 6 else clusters.append([x]))
        c = max(clusters, key=len)
        res.append((chars[c[0]][1], chars[c[-1]][2], len(g) / max(1, len(norm_chars(texts[k])))))
    return res


def frame_rms(pcm):
    hop = int(0.02 * SR)
    fr = pcm[: len(pcm) // hop * hop].astype(np.float32).reshape(-1, hop)
    rms = np.sqrt((fr ** 2).mean(1)) + 1e-6
    return rms, max(np.percentile(rms, 20) * 2.5, rms.max() * 0.02)


def silent_runs(pcm, min_sil=0.12):
    rms, thr = frame_rms(pcm)
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
    return runs


def voice_edges(pcm):
    rms, thr = frame_rms(pcm)
    loud = np.where(rms >= thr)[0]
    return loud[0] * 0.02, (loud[-1] + 1) * 0.02


def lufs(pcm):
    import pyloudnorm
    return pyloudnorm.Meter(SR).integrated_loudness(pcm.astype(np.float64) / 32768)


def gap(sentence):
    return np.zeros(int((0.5 if sentence[-1] in "。！？" else 0.3) * SR), np.int16)


def prepare(spec):
    sents, own = sentences(), ownership()
    plan = []
    for tok in spec.split(","):
        internal = tok.startswith("@")          # take cut from an earlier generation, not sent to the platform
        a, _, b = tok.lstrip("@").partition("-")
        ks = list(range(int(a), int(b or a) + 1))
        assert len({own[k] for k in ks}) == 1, f"{tok} spans two parts"
        text = "".join(sents[k] for k in ks)
        say = text
        for x, y in SAY.items():
            say = say.replace(x, y)
        plan.append({"part": own[ks[0]], "ks": ks, "text": text, "say": say, "internal": internal})
    assert all(not p["internal"] for p in plan[:sum(not p["internal"] for p in plan)]), "put @ tokens last"
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    lines = [p["say"] for p in plan if not p["internal"]]
    TXT.write_text((INSTR + "\n" if INSTR else "") + "\n".join(lines))
    for i, p in enumerate(plan, 1):
        print(f"第{i}行 {'(内部)' if p['internal'] else ''} {p['part'][:12]}  #{p['ks']}  {p['say']}")
    print("wrote", TXT)
    # one file per console paste (the web console takes ~1.4 KB at once); takes are joined in natural order,
    # so the user saves them as 补句1.wav, 补句2.wav ... (the hand-over is a 豆包 prompt naming these files)
    for old_chunk in TXT.parent.glob(f"{NAME}_补句_*.txt"):
        old_chunk.unlink()
    chunks, cur = [], []
    for ln in lines:
        if cur and len("\n".join([INSTR] + cur + [ln]).encode()) > 1400:
            chunks.append(cur); cur = []
        cur.append(ln)
    if cur:
        chunks.append(cur)
    first = 1
    for j, c in enumerate(chunks, 1):
        f = TXT.parent / f"{NAME}_补句_{j}.txt"
        f.write_text((INSTR + "\n" if INSTR else "") + "\n".join(c) + "\n")
        print(f"wrote {f.name}: 第{first}–{first + len(c) - 1}行 -> save as 配音/{NAME}_补句/补句{j}.wav")
        first += len(c)


def cut_lines(model, pcm, texts):
    """cut one take file into its lines at the pauses around each line's matched chars"""
    chars = char_seq(asr_words(model, pcm))
    anc = anchor_times(texts, chars)
    runs = silent_runs(pcm, 0.15)
    clips = []
    for i, a in enumerate(anc):
        if a is None:
            clips.append((None, 0.0)); continue
        lo = anc[i - 1][1] if i and anc[i - 1] else 0.0
        hi = anc[i + 1][0] if i + 1 < len(anc) and anc[i + 1] else len(pcm) / SR
        s0 = max([r1 for r0, r1 in runs if r1 >= lo and r0 < a[0] - 0.02 and r1 <= a[0] + 0.45] or [max(lo, a[0] - 0.15)])
        s1 = min([r0 for r0, r1 in runs if r0 <= hi and r1 > a[1] + 0.02 and r0 >= a[1] - 0.6] or [min(hi, a[1] + 0.2)])
        seg = [c for c, t0, _ in chars if s0 - 0.05 <= t0 <= s1 + 0.05]
        r = difflib.SequenceMatcher(None, norm_chars(texts[i]), seg, autojunk=False).ratio()
        clips.append((pcm[int(max(0, s0 - 0.04) * SR):int((s1 + 0.06) * SR)], r))
    return clips


def apply():
    from faster_whisper import WhisperModel
    plan = json.loads(PLAN.read_text())
    model = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8", cpu_threads=10)
    files = sorted([p for p in TAKES.iterdir() if p.suffix.lower() in AUDIO], key=nat)
    takes = [(None, 0.0)] * len(plan)
    main = [f for f in files if not re.match(r"第\d+行", f.stem)]
    if main:
        pcm = np.concatenate([np.concatenate([to_wav(f, CHECK / f"take{i}.wav"), np.zeros(int(0.5 * SR), np.int16)])
                              for i, f in enumerate(main)])
        takes = cut_lines(model, pcm, [p["text"] for p in plan])
    for f in files:
        m = re.match(r"第(\d+)行", f.stem)
        if m:
            n = int(m.group(1)) - 1
            takes[n] = cut_lines(model, to_wav(f, CHECK / "take_line.wav"), [plan[n]["text"]])[0]
    for i, (clip, r) in enumerate(takes, 1):
        flag = "" if clip is not None and r >= 0.85 else "   <<< 这一行需要重录"
        print(f"第{i}行  {0 if clip is None else len(clip) / SR:5.2f}s  识别吻合 {r:.2f}{flag}  {plan[i - 1]['text'][:28]}")

    sents, own = sentences(), ownership()
    shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir()
    for f in sorted([p for p in SRC.iterdir() if p.suffix.lower() in AUDIO], key=nat):
        jobs = sorted([(p, t) for p, (t, _) in zip(plan, takes) if p["part"] == f.name and t is not None],
                      key=lambda x: x[0]["ks"][0])
        if not jobs:
            shutil.copy2(f, OUT / f.name); continue
        pcm = to_wav(f, CHECK / "patch_src.wav")
        words = json.loads((CHECK / SRC.name / f"{f.stem}.{asr_tag()}.json").read_text())["words"]
        ks = [k for k in range(len(sents)) if own[k] == f.name]
        anc = dict(zip(ks, anchor_times([sents[k] for k in ks], char_seq(words))))
        replaced = {k for p, _ in jobs for k in p["ks"]}
        runs, (v0, v1), ref = silent_runs(pcm), voice_edges(pcm), lufs(pcm)
        # consecutive replaced groups form one edit region
        regions = []
        for p, t in jobs:
            if regions and p["ks"][0] == regions[-1][-1][0]["ks"][-1] + 1:
                regions[-1].append((p, t))
            else:
                regions.append([(p, t)])
        edits = []
        for reg in regions:
            g0, g1 = reg[0][0]["ks"][0], reg[-1][0]["ks"][-1]
            prev = next((anc[k] for k in range(g0 - 1, ks[0] - 1, -1) if k not in replaced and anc.get(k) and anc[k][2] > 0.5), None)
            nxt = next((anc[k] for k in range(g1 + 1, ks[-1] + 1) if k not in replaced and anc.get(k) and anc[k][2] > 0.5), None)
            # ASR word times bleed into neighbouring pauses, so accept the pause that straddles the anchor
            c0 = min([r0 for r0, r1 in runs if r1 > prev[1] + 0.02 and r0 >= prev[1] - 0.6] or [prev[1] + 0.1]) if prev else v0
            c1 = max([r1 for r0, r1 in runs if r0 < nxt[0] - 0.02 and r1 <= nxt[0] + 0.45] or [nxt[0] - 0.1]) if nxt else v1
            # a neighbour's anchor can land inside the garbled stretch (its words also occur there, e.g. "peak"), which
            # would leave the tail of the old take in place; the cut must cover the replaced sentences' own matched span
            first, last = anc.get(g0), anc.get(g1)
            if last and last[2] > 0.5:
                c1 = max(c1, min([r1 for r0, r1 in runs if r0 >= last[1] - 0.45] or [last[1] + 0.1]))
            if first and first[2] > 0.5:
                c0 = min(c0, max([r0 for r0, r1 in runs if r1 <= first[0] + 0.45] or [first[0] - 0.1]))
            ins = [gap(sents[g0 - 1])] if prev else []
            for j, (p, t) in enumerate(reg):
                t = np.clip(t.astype(np.float64) * 10 ** ((ref - lufs(t)) / 20), -32768, 32767).astype(np.int16)
                ins.append(t)
                if j + 1 < len(reg) or nxt:
                    ins.append(gap(sents[p["ks"][-1]]))
            ins = np.concatenate(ins).astype(np.int16)
            edits.append((c0, c1, ins))
            print(f"{f.name[:12]}  #{g0}-{g1}: {c0:.2f}-{c1:.2f}s ({c1 - c0:.1f}s) -> {len(ins) / SR:.1f}s")
        pieces, cur = [], 0.0
        for c0, c1, ins in sorted(edits, key=lambda e: e[0]):
            pieces += [pcm[int(cur * SR):int(c0 * SR)], ins]; cur = c1
        pieces.append(pcm[int(cur * SR):])
        with wave.open(str(OUT / (f.stem + ".wav")), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.concatenate(pieces).tobytes())
    print("wrote", OUT)


if __name__ == "__main__":
    prepare(sys.argv[2]) if sys.argv[1] == "prepare" else apply()
