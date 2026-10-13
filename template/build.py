"""TTS + timeline + frame compositing -> MP4 / SRT.

script.json "engine": "edge" = draft narration with edge-tts (sentence by sentence, cached);
"external" = narration recorded elsewhere (e.g. 豆包) and aligned by align_external.py.

usage:
  python3 build.py tts   [pids...]          synthesize narration (cached)
  python3 build.py video OUTNAME [pids...]   compose video (default: all pages)
  python3 build.py still PID STEP            preview frame with mascot + a subtitle
  python3 build.py frames [pids...]          one frame per beat as the video shows it once the ring is fully in
                                             (full timeline, so the mascot path is the video's) -> out/frames/
"""

import asyncio, hashlib, json, math, os, re, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
CACHE = ROOT / "cache" / "tts"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 25
SR = 24000

# display text -> spoken text for the draft TTS (longest keys first).
# Project terms go in script.json "pron"; they extend / override these defaults.
PRON = {
    "FASTQ": "fast Q", "FastQC": "fast QC", "samtools": "sam tools", "bedtools": "bed tools",
    "RNA-seq": "RNA seq", "ChIP-seq": "chip seq", "PCR": "P C R", "SNP": "S N P", "IGV": "I G V",
    "FDR": "F D R", "bp": "b p",
}
SUB_FONT = os.environ.get("LECTURE_SUBTITLE_FONT", "/System/Library/Fonts/Hiragino Sans GB.ttc")
SUB_FONT_INDEX = int(os.environ.get("LECTURE_SUBTITLE_FONT_INDEX", "2"))


def load_script():
    return json.loads((ROOT / "script.json").read_text(encoding="utf-8"))


ENGINE = {"name": "edge"}
_PRON_ALL = None


def spoken(text):
    global _PRON_ALL
    if _PRON_ALL is None:
        _PRON_ALL = dict(PRON, **load_script().get("pron", {}))
    for k in sorted(_PRON_ALL, key=len, reverse=True):
        text = text.replace(k, _PRON_ALL[k])
    return text


def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def sentences(text):
    parts = re.split(r"(?<=[。！？；])", text)
    return [p.strip() for p in parts if p.strip()]


def chunks(sentence, maxlen=24):
    """split a sentence into subtitle chunks at commas / colons."""
    pieces = [p for p in re.split(r"(?<=[，、：,])", sentence) if p]
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > maxlen:
            out.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    return out


def weight(s):
    s = spoken(s)
    cjk = len(re.findall(r"[一-鿿]", s))
    latin = len(re.findall(r"[A-Za-z]", s))
    digits = len(re.findall(r"[0-9]", s))
    return cjk + 0.42 * latin + 0.9 * digits + 0.3


def clean_sub(s):
    return re.sub(r"[，。；、：,]$", "", s.strip())


# ---------------- TTS ----------------
async def _synth(text, voice, rate, mp3):
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=rate)
    await asyncio.wait_for(c.save(str(mp3)), timeout=45)  # the service sometimes stalls without erroring


def tts_wav(text, voice, rate):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    wav = CACHE / f"{key}.wav"
    if not wav.exists():
        mp3 = CACHE / f"{key}.mp3"
        for attempt in range(8):
            try:
                asyncio.run(_synth(text, voice, rate, mp3))
            except Exception as e:  # network hiccup
                print("tts retry", attempt, e, flush=True)
                continue
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
            with wave.open(str(wav)) as w:
                dur = w.getnframes() / w.getframerate()
            # the service sometimes returns a clip cut short without any error (normal: ~0.2 s per CJK char / half an English word)
            units = len(re.findall(r"[\u4e00-\u9fff]", text)) + 2 * len(re.findall(r"[A-Za-z0-9]+", text))
            if dur >= 0.13 * units or units < 8:
                break
            print("tts truncated, retry", attempt, f"{dur:.1f}s for {units} units", flush=True)
            wav.unlink()
        if not wav.exists():
            raise RuntimeError(f"edge-tts failed for: {text}")
    with wave.open(str(wav)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data


# ---------------- timeline ----------------
LEAD, GAP, TAIL, PAGE_TAIL, XFADE = 0.25, 0.16, 0.22, 0.3, 0.45
END_HOLD, FADE_OUT = 2.2, 1.0


def _stretched(wav, tempo):
    """pitch-preserving tempo change of an aligned page (ffmpeg atempo), cached by source mtime"""
    src = Path(wav)
    out = CACHE.parent / "tempo" / f"{src.stem}_{tempo:.3f}_{int(src.stat().st_mtime)}.wav"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-filter:a", f"atempo={tempo}",
                        "-ac", "1", "-ar", str(SR), str(out)], check=True)
    return read_wav(out)


def build_timeline_external(pages, pace=None):
    """Timeline from externally generated per-page narration aligned by align_external.py.
    pace (script.json "pace"): tempo < 1 slows speech (atempo, pitch kept); sentence_gap / beat_gap are the
    minimum silences between sentences / between beats (web TTS often leaves only ~0.3 s, which sounds rushed)."""
    pace = pace or {}
    tempo = float(pace.get("tempo", 1.0))
    gap_s, gap_b = float(pace.get("sentence_gap", 0.0)), float(pace.get("beat_gap", 0.0))
    al = json.loads((ROOT / "cache" / "external" / "align.json").read_text(encoding="utf-8"))
    audio, segs, subs, t = [], [], [], 0.0
    for page in pages:
        info = al[page["id"]]
        if abs(tempo - 1.0) > 1e-3:
            pcm = _stretched(info["wav"], tempo)
            spans = [(a / tempo, b / tempo) for a, b in info["sentences"]]
        else:
            pcm, spans = read_wav(info["wav"]), info["sentences"]
        sb = [(bi, sen) for bi, bt in enumerate(page["beats"]) for sen in sentences(bt["text"])]
        assert len(sb) == len(spans), (page["id"], len(sb), len(spans))
        a0 = max(0.0, spans[0][0] - 0.25)
        a1 = min(len(pcm) / SR, spans[-1][1] + 0.35)
        # cut points in the middle of each inter-sentence pause; widen pauses that are shorter than the target
        cuts = [a0] + [(spans[i - 1][1] + spans[i][0]) / 2 for i in range(1, len(spans))] + [a1]
        page_t0 = t
        audio.append(np.zeros(int(LEAD * SR), np.int16)); t += LEAD
        starts, prev_end = {}, None
        for i, (bi, sen) in enumerate(sb):
            if i:
                target = gap_b if bi != sb[i - 1][0] else gap_s
                extra = max(0.0, target - (spans[i][0] - spans[i - 1][1]))
                if extra:
                    audio.append(np.zeros(int(extra * SR), np.int16)); t += extra
            piece = pcm[int(cuts[i] * SR):int(cuts[i + 1] * SR)]
            s0, s1 = t + spans[i][0] - cuts[i], t + spans[i][1] - cuts[i]
            if bi not in starts:
                starts[bi] = page_t0 if i == 0 else (prev_end + s0) / 2
            cs = chunks(sen); ws = [weight(c) for c in cs]; acc = s0
            for c, wgt in zip(cs, ws):
                d = (s1 - s0) * wgt / sum(ws)
                subs.append((acc, acc + d, clean_sub(c))); acc += d
            audio.append(piece); t += len(piece) / SR
            prev_end = s1
        audio.append(np.zeros(int((TAIL + PAGE_TAIL) * SR), np.int16)); t += TAIL + PAGE_TAIL
        for bi, bt in enumerate(page["beats"]):
            end = starts.get(bi + 1, t)
            segs.append((starts[bi], end, page["id"], bt.get("step", 1), bt.get("pose", "idle"), bt.get("sign")))
    if segs:
        audio.append(np.zeros(int(END_HOLD * SR), np.int16)); t += END_HOLD
        segs[-1] = segs[-1][:1] + (t,) + segs[-1][2:]
    return segs, subs, np.concatenate(audio)


def build_timeline(script, pids):
    voice, rate = script["voice"], script.get("rate", "+0%")
    pages = [p for p in script["pages"] if p["id"] in pids] if pids else script["pages"]
    ENGINE["name"] = script.get("engine", "edge")
    if ENGINE["name"] == "external":
        return build_timeline_external(pages, script.get("pace"))

    def synth(sp):
        return tts_wav(sp, voice, rate)
    audio = []
    t = 0.0
    segs = []   # (t0, t1, pid, step, pose, sign)
    subs = []   # (t0, t1, text)
    for page in pages:
        for bi, beat in enumerate(page["beats"]):
            b0 = t
            t += LEAD
            audio.append(np.zeros(int(LEAD * SR), np.int16))
            for sen in sentences(beat["text"]):
                data = synth(spoken(sen))
                dur = len(data) / SR
                cs = chunks(sen)
                ws = [weight(c) for c in cs]
                acc = t
                for c, wgt in zip(cs, ws):
                    d = dur * wgt / sum(ws)
                    subs.append((acc, acc + d, clean_sub(c)))
                    acc += d
                audio.append(data)
                t += dur
                audio.append(np.zeros(int(GAP * SR), np.int16))
                t += GAP
            pause = beat.get("pause", 0)
            tail = TAIL + pause + (PAGE_TAIL if bi == len(page["beats"]) - 1 else 0)
            audio.append(np.zeros(int(tail * SR), np.int16))
            t += tail
            segs.append((b0, t, page["id"], beat.get("step", 1), beat.get("pose", "idle"), beat.get("sign")))
    if segs:   # hold the last frame a little longer at the very end
        audio.append(np.zeros(int(END_HOLD * SR), np.int16))
        t += END_HOLD
        segs[-1] = segs[-1][:1] + (t,) + segs[-1][2:]
    pcm = np.concatenate(audio)
    return segs, subs, pcm


# ---------------- compositing ----------------
_img_cache = {}


def page_img(pid, step):
    k = (pid, step)
    if k not in _img_cache:
        _img_cache[k] = Image.open(OUT / "pages" / f"{pid}_s{step}.png").convert("RGB")
    return _img_cache[k]


MASCOT_SCALE = 0.42
MS = int(480 * MASCOT_SCALE)          # sprite size on screen
_m_cache = {}


def mascot_img(pose, blink, flip, sign=None):
    k = (pose, blink, flip, sign)
    if k not in _m_cache:
        name = f"{pose}_{int(blink)}_{int(flip)}" + (f"_{hashlib.md5(sign.encode()).hexdigest()[:8]}" if sign else "")
        im = Image.open(OUT / "mascot" / f"{name}.png").convert("RGBA")
        _m_cache[k] = im.resize((MS, MS), Image.LANCZOS)
    return _m_cache[k]


# ---------------- mascot placement ----------------
PAPER = np.array([250, 248, 243], dtype=np.int16)
_occ_cache = {}


def occupancy_map(pid, step):
    k = (pid, step)
    if k not in _occ_cache:
        a = np.asarray(page_img(pid, step).resize((480, 270), Image.BILINEAR), dtype=np.int16)
        _occ_cache[k] = (np.abs(a - PAPER).sum(axis=2) > 45).astype(np.float32)
    return _occ_cache[k]


def load_focus(pid):
    f = OUT / "pages" / f"{pid}_focus.json"
    return json.loads(f.read_text()) if f.exists() else {}


def place_mascot(pid, step, focus, prev):
    occ = occupancy_map(pid, step)
    x0, y0, x1, y1 = focus
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    S = MS
    cands = []
    for my in (y0 - 30, cy - S / 2, y1 - S + 10):
        cands.append((x1 - 24, my, 0, 0.0))            # right of focus, facing left
        cands.append((x0 - S + 24, my, 1, 0.05))       # left of focus, facing right
    for mx in (x0, cx - S / 2, x1 - S):
        cands.append((mx, y1 - 14, 0 if mx > 400 else 1, 0.15))      # below
        cands.append((mx, y0 - S + 14, 0 if mx > 400 else 1, 0.3))   # above
    for gx in range(0, 1920 - S, 120):             # fallback grid
        for gy in range(110, 960 - S, 110):
            cands.append((gx, gy, 0 if gx + S / 2 > cx else 1, 0.4))
    best, bs = None, 1e9
    for mx, my, flip, pen in cands:
        mx = min(max(8, mx), 1912 - S)
        my = min(max(100, my), 1076 - S)
        if my + S > 958 and mx + S * 0.2 < 1620:      # keep clear of subtitles
            my = 958 - S
        # occupancy of the mascot body/prop box (in 1/4-res map)
        bx0 = mx + (22 if not flip else S - 192); bx1 = bx0 + 170
        by0, by1 = my + 18, my + S - 16
        region = occ[int(by0 / 4):int(by1 / 4), int(bx0 / 4):int(bx1 / 4)]
        o = float(region.mean()) if region.size else 1.0
        bcx, bcy = mx + (S * 0.58 if not flip else S * 0.42), my + S * 0.55
        dx = max(x0 - bx1, 0, bx0 - x1); dy = max(y0 - by1, 0, by0 - y1)
        dist = math.hypot(dx, dy)
        inside = x0 + 20 < bcx < x1 - 20 and y0 + 20 < bcy < y1 - 20
        move = math.hypot(mx - prev[0], my - prev[1]) if prev else 0
        score = o * 9 + dist / 260 + (0.9 if inside else 0) + move / 4000 + pen
        if score < bs:
            best, bs = (mx, my, flip), score
    return best


MOVE, HL_IN, HL_HOLD, HL_OUT = 0.75, 0.3, 2.4, 0.5
_hl_cache = {}


def ring_style(box):
    """(pad, line width, radius). A ring around one or two lines of text (a code argument, a table row) hugs it:
    the roomy ring sits 3-9 px out and would cross the glyphs of the neighbouring code lines."""
    return (9, 4, 12) if box[3] - box[1] <= 72 else (12, 6, 22)


def highlight_layers(box):
    k = tuple(box)
    if k not in _hl_cache:
        x0, y0, x1, y1 = box
        pad, lw, rad = ring_style(box)
        w, h = int(x1 - x0 + 2 * pad), int(y1 - y0 + 2 * pad)
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        d.rounded_rectangle((3, 3, w - 4, h - 4), radius=rad, outline=(217, 119, 87, 255), width=lw)
        layers = []
        for lv in range(1, 9):
            im = base.copy()
            a = im.getchannel("A").point(lambda v, lv=lv: int(v * lv / 8))
            im.putalpha(a)
            layers.append(im)
        _hl_cache[k] = (int(x0 - pad), int(y0 - pad), layers)
    return _hl_cache[k]


_sub_cache = {}
FONT = None


def sub_overlay(text):
    global FONT
    if text in _sub_cache:
        return _sub_cache[text]
    if FONT is None:
        FONT = ImageFont.truetype(SUB_FONT, 42, index=SUB_FONT_INDEX)
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bbox = d0.textbbox((0, 0), text, font=FONT)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pw, ph = tw + 64, 78
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=22, fill=(43, 45, 66, 222))
    d.text((32 - bbox[0], (ph - th) // 2 - bbox[1]), text, font=FONT, fill=(255, 255, 255, 255))
    _sub_cache[text] = im
    return im


SUB_CX, SUB_BOTTOM = 960, 1052


def cluster_focus(rects):
    """largest newly-shown element + anything within 60px of it."""
    if not rects:
        return None
    if isinstance(rects[0], (int, float)):
        return rects
    rects = sorted(rects, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    x0, y0, x1, y1 = rects[0]
    changed = True
    while changed:
        changed = False
        for r in rects[1:]:
            gap = max(r[0] - x1, x0 - r[2], r[1] - y1, y0 - r[3])
            inside = r[0] >= x0 and r[1] >= y0 and r[2] <= x1 and r[3] <= y1
            if gap < 24 and not inside:
                nx0, ny0, nx1, ny1 = min(x0, r[0]), min(y0, r[1]), max(x1, r[2]), max(y1, r[3])
                if (nx0, ny0, nx1, ny1) != (x0, y0, x1, y1):
                    x0, y0, x1, y1 = nx0, ny0, nx1, ny1
                    changed = True
    return [x0, y0, x1, y1]


DEFAULT_FOCUS = [160, 220, 1760, 900]


def ring_delay(beat, seg, subs):
    """Seconds into the beat at which its ring appears: just after the mascot sets off, or, with "ring_at" (a phrase
    of the beat's narration), when the narration reaches that phrase. For beats whose ringed item is only mentioned
    halfway through. Timed like the subtitle cues, by character weight."""
    at = beat.get("ring_at")
    if not at or not subs:
        return MOVE * 0.6
    norm = lambda s: re.sub(r"[，。；、：,！？\s]", "", s)
    cues = [c for c in subs if seg[0] <= c[0] < seg[1]]
    k = "".join(norm(c[2]) for c in cues).find(norm(at))
    if k < 0:
        raise ValueError(f"ring_at not found in the narration of {seg[2]} step {seg[3]}: {at}")
    for c0, c1, text in cues:
        n = norm(text)
        if k < len(n):
            return max(MOVE * 0.6, c0 + (c1 - c0) * (weight(n[:k]) - 0.3) / (weight(n) - 0.3) - seg[0])
        k -= len(n)


def plan_mascot(segs, script, subs=None):
    """per segment: (mx, my, flip, focusbox, ring delay in s)"""
    beats = {}
    for page in script["pages"]:
        for b in page["beats"]:
            beats[(page["id"], b.get("step", 1))] = b
    plans, prev, fcache = [], None, {}
    for seg in segs:
        t0, t1, pid, step, pose, sign = seg
        if pid not in fcache:
            fcache[pid] = load_focus(pid)
        b = beats.get((pid, step), {})
        focus = b.get("focus") or cluster_focus(fcache[pid].get(str(step))) or DEFAULT_FOCUS
        # no ring when the beat opts out ("hl": false) or when no real focus was found (fallback box)
        ring = b.get("hl", True) and focus != DEFAULT_FOCUS
        if b.get("mascot"):
            mx, my, flip = b["mascot"]
        else:
            mx, my, flip = place_mascot(pid, step, focus, prev)
        plans.append((mx, my, flip, focus if ring else None, ring_delay(b, seg, subs)))
        prev = (mx, my)
    return plans


def compose_frame(t, segs, subs, plans, si_hint=[0]):
    i = si_hint[0]
    while i < len(segs) - 1 and t >= segs[i][1]:
        i += 1
    while i > 0 and t < segs[i][0]:
        i -= 1
    si_hint[0] = i
    t0, t1, pid, step, pose, sign = segs[i]
    base = page_img(pid, step)
    if i > 0 and t - t0 < XFADE:
        _, _, ppid, pstep, _, _ = segs[i - 1]
        if (ppid, pstep) != (pid, step):
            a = (t - t0) / XFADE
            a = a * a * (3 - 2 * a)
            base = Image.blend(page_img(ppid, pstep), base, a)
    frame = base.copy()
    mx, my, flip, focus, ts = plans[i]
    dt = t - t0
    # focus highlight (skip when disabled or for near-full-frame boxes)
    fw, fh = (focus[2] - focus[0], focus[3] - focus[1]) if focus else (1920, 1080)
    if fw * fh < 0.55 * 1920 * 1080:
        if ts < dt < ts + HL_IN + HL_HOLD + HL_OUT:
            u = dt - ts
            lvl = min(1, u / HL_IN) if u < HL_IN else (1 if u < HL_IN + HL_HOLD else max(0, 1 - (u - HL_IN - HL_HOLD) / HL_OUT))
            k = int(round(lvl * 8))
            if k > 0:
                hx, hy, layers = highlight_layers(focus)
                frame.paste(layers[k - 1], (hx, hy), layers[k - 1])
    # mascot position: glide from previous placement with a small hop
    px, py = mx, my
    if i > 0 and dt < MOVE:
        qx, qy = plans[i - 1][:2]
        if (qx, qy) != (mx, my):
            u = dt / MOVE
            e = u * u * (3 - 2 * u)
            hop = min(90, 0.18 * math.hypot(mx - qx, my - qy)) * math.sin(math.pi * u)
            px, py = qx + (mx - qx) * e, qy + (my - qy) * e - hop
    blink = (t % 3.7) < 0.13
    m = mascot_img(pose, blink, flip, sign)
    arrived = dt >= MOVE or (i > 0 and plans[i - 1][:2] == (mx, my))
    if arrived and (i == 0 or segs[i - 1][4:6] != (pose, sign) or plans[i - 1][:3] != (mx, my, flip)):
        da = dt - (MOVE if i > 0 and plans[i - 1][:2] != (mx, my) else 0)
        if 0 <= da < 0.28:
            pop = 0.88 + 0.12 * math.sin(da / 0.28 * math.pi / 2) + 0.06 * math.sin(da / 0.28 * math.pi)
            sz = int(MS * pop)
            m = m.resize((sz, sz), Image.BILINEAR)
            px += (MS - sz) / 2; py += (MS - sz)
    bob = 4 * math.sin(2 * math.pi * t / 1.8) if arrived else 0
    frame.paste(m, (int(px), int(py + bob)), m)
    for (s0, s1, text) in subs:
        if s0 <= t < s1 and text:
            ov = sub_overlay(text)
            frame.paste(ov, (SUB_CX - ov.width // 2, SUB_BOTTOM - ov.height), ov)
            break
    end = segs[-1][1]
    if i == len(segs) - 1 and t > end - FADE_OUT:
        a = min(1.0, (t - (end - FADE_OUT)) / FADE_OUT)
        frame = Image.blend(frame, Image.new("RGB", frame.size, (250, 248, 243)), a)
    return frame


def srt_time(x):
    h, r = divmod(x, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def _render_chunk(args):
    name, k0, k1, segs, subs, plans, idx = args
    part = OUT / f"{name}.part{idx:02d}.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "animation", "-pix_fmt", "yuv420p", str(part)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    hint = [0]
    for k in range(k0, k1):
        proc.stdin.write(compose_frame(k / FPS, segs, subs, plans, hint).tobytes())
    proc.stdin.close()
    proc.wait()
    return str(part)


def make_video(name, pids, jobs=1):
    script = load_script()
    segs, subs, pcm = build_timeline(script, pids)
    total = len(pcm) / SR
    OUT.mkdir(exist_ok=True)
    wav = OUT / f"{name}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    with open(OUT / f"{name}.srt", "w", encoding="utf-8") as f:
        for k, (s0, s1, text) in enumerate(subs, 1):
            f.write(f"{k}\n{srt_time(s0)} --> {srt_time(s1)}\n{text}\n\n")
    plans = plan_mascot(segs, script, subs)
    for seg, pl in zip(segs, plans):
        if pl[3] and pl[4] + HL_IN + HL_HOLD > seg[1] - seg[0]:
            print(f"warning: {seg[2]} step {seg[3]}: ring_at so late that the ring is cut off by the next step")
    n = int(total * FPS)
    bounds = [round(n * i / jobs) for i in range(jobs + 1)]
    tasks = [(name, bounds[i], bounds[i + 1], segs, subs, plans, i) for i in range(jobs)]
    if jobs == 1:
        parts = [_render_chunk(tasks[0])]
    else:
        from multiprocessing import get_context
        with get_context("fork").Pool(jobs) as pool:
            parts = pool.map(_render_chunk, tasks)
    lst = OUT / f"{name}.parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    mp4 = OUT / f"{name}.mp4"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)], check=True)
    for p in parts:
        Path(p).unlink()
    lst.unlink()
    json.dump({"segments": segs, "plans": plans, "total": total}, open(OUT / f"{name}.timeline.json", "w"), ensure_ascii=False, indent=1)
    print(f"done {mp4} {total:.1f}s")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "tts":
        build_timeline(load_script(), sys.argv[2:])
        print("tts ok")
    elif cmd == "video":
        args = sys.argv[3:]
        jobs = 1
        if args and args[0].startswith("-j"):
            jobs = int(args[0][2:]); args = args[1:]
        make_video(sys.argv[2], args, jobs)
    elif cmd == "frames":
        script = load_script()
        segs, subs, _ = build_timeline(script, [])
        plans = plan_mascot(segs, script, subs)
        d = OUT / "frames"
        d.mkdir(parents=True, exist_ok=True)
        want, tiles = set(sys.argv[2:]), {}
        for i, (seg, pl) in enumerate(zip(segs, plans)):
            if want and seg[2] not in want:
                continue
            t = min(seg[0] + max(pl[4] + HL_IN + 0.2, MOVE + 0.3), seg[1] - 0.05)
            im = compose_frame(t, segs, subs, plans, [i])
            im.save(d / f"{seg[2]}_s{seg[3]}.png")
            tiles.setdefault(seg[2], []).append(im.resize((960, 540)))
        for pid, ims in tiles.items():
            sh = Image.new("RGB", (1920, 540 * ((len(ims) + 1) // 2)), "white")
            for k, im in enumerate(ims):
                sh.paste(im, ((k % 2) * 960, (k // 2) * 540))
            sh.save(d / f"{pid}_sheet.png")
        print("frames ->", d)
    elif cmd == "still":
        pid, step = sys.argv[2], int(sys.argv[3])
        script = load_script()
        page = next(p for p in script["pages"] if p["id"] == pid)
        beat = next(b for b in page["beats"] if b.get("step", 1) == step)
        segs = [(0, 10, pid, step, beat.get("pose", "idle"), beat.get("sign"))]
        plans = plan_mascot(segs, script)
        sub = chunks(sentences(beat["text"])[0])[0]
        compose_frame(2.0, segs, [(0, 10, clean_sub(sub))], plans).save(OUT / f"still_{pid}_{step}.png")
