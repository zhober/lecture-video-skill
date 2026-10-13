# script.json and page authoring

## Contents
1. script.json schema
2. Page skeleton and step reveal
3. Layout rules (mascot and subtitles)
4. Visual vocabulary: CSS classes, bio.js, cartoon.js
5. Self-check list

## 1. script.json schema

```jsonc
{
  "title": "ATAC-seq 数据分析：从 FASTQ 到生物学结论",     // used by make_docs.py
  "subtitle": "示例数据：……。",                            // one line under the transcript title
  "voice": "zh-CN-XiaoxiaoNeural", "rate": "+10%",        // edge-tts draft voice
  "engine": "edge",                                        // "edge" for drafts, "external" once 配音/ audio is aligned
  "progress_steps": ["比对", "过滤", "质控", "Peak calling", "差异分析", "功能注释"],  // header progress bar
  "pron": {"Tn5": "T N 5"},             // edge-tts only: display text -> spoken text
  "tts_instruction": "<整体情绪：平静，语气：大学老师讲课，语速：适中，英文术语用标准英语发音>",
  "tts_say": {"A、B、C": "A，B，C"},     // web-TTS-only rewording for phrases it keeps garbling
  "watch_terms": ["ATAC", "DESeq2"],     // check_external.py reports how long each is spoken
  "pages": [
    {
      "id": "p03",                       // pages/p03.html; ids need not be contiguous (deleted pages leave gaps)
      "chapter": "第2章 ATAC-seq 是什么",  // chip text; transcript groups pages by it
      "title": "染色质、核小体与开放区域",
      "progress": -2,                    // informational; the page HTML passes it to header()
      "beats": [
        {"step": 1, "pose": "point", "text": "先来看……。"},
        {"step": 2, "pose": "sign", "sign": "≈200 bp", "text": "……。"},
        {"step": 3, "pose": "magnifier", "text": "……。",
         "focus": [600, 300, 1200, 700],   // optional: override the mascot focus box
         "mascot": [1500, 400, 0],         // optional: force mascot x, y, flip
         "pause": 0.5}                     // optional extra silence after the beat (edge engine)
      ]
    }
  ]
}
```

**Poses**: `idle wave point sign magnifier thumbs think cheer`. `sign` shows the beat's `sign` text on a
placard. Keep it to 2–6 characters, e.g. 检查点、注意、谨慎解读、需排查、≈200 bp.
Run `render.py mascots` again after adding new sign texts.

**Beats**: one beat is one reveal step and 1–3 sentences. Steps start at 1 and run consecutively; the page's HTML
reveals exactly those step numbers. Plan 3–5 beats per page.

## 2. Page skeleton and step reveal

```html
<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="../assets/theme.css">
<script src="../assets/cartoon.js"></script>
<script src="../assets/bio.js"></script>
</head><body>
<div id="hdr"></div>
<div class="ptitle">页面标题<div id="sq"></div></div>
<div class="card" data-s="1" style="left:80px;top:230px;width:820px;height:600px"> … </div>
<svg … data-s="2"> … </svg>
<script>
document.getElementById('hdr').innerHTML = header('第4章 上游① 比对', 0); // 2nd arg: progress index, -1 none lit, -2 hide bar
document.getElementById('sq').innerHTML = squiggle(400);
// build SVG strings with bio.js helpers and insert them …
applyStep();   // must be the last call: reads ?step=N, toggles .on, sets body[data-ready=1]
</script></body></html>
```

- **`data-s="N"`**: the element appears from step N. **`data-until="M"`**: it hides after step M, for labels
  that make room for others.
- **`<span data-hl="2,3">`**: inside `.code`, the line is highlighted at steps 2 and 3.
- **`data-focus="N"`** (comma list allowed): forces the mascot's focus box onto this element at step N, e.g. one
  code line or one peak. Without it, focus prefers highlighted code (`data-hl`) and then newly shown elements; explicit
  `data-focus` always takes precedence.
- **Text and pictures**: SVG text is fine. `export_pptx.py` turns HTML and SVG text into editable PPTX text boxes,
  so prefer real text over text baked into images.

## 3. Layout rules (mascot and subtitles)

- **Canvas zones**: header y 28–92, title y 110–200, content x 56–1864 and y 210–920.
- **Subtitle band**: keep y > 930 empty. Subtitles are centred at x 960, up to about 1400 wide.
- **Mascot**: about 200×200 px, scored placement. It avoids occupied pixels, stays close to the focus box, and
  prefers the right side. Leave about 220×220 px of free paper next to each step's new content, or it will land
  somewhere awkward or on top of content.
- **New content per step**: group it in one container with `data-s`, so the focus box is tight.
  `build.py`'s `cluster_focus` merges rects only within 24 px.
- **Font sizes**: 20 px minimum, body 24–30, emphasis 34–44.
- **Density**: no more than 3 new elements per step. Code blocks run 8 lines at most, 24–27 px, with long commands
  wrapped using `\`.

## 4. Visual vocabulary

**theme.css**
- **Paper**: background #FAF8F3.
- **Cards**: `.card` (white, light border, soft shadow) and `.card.soft`. Position them absolutely with inline
  `left/top/width/height`.
- **Notes**: `.note.red|yellow|green` with `<span class="nt">标题</span>`. Red is a common pitfall, yellow a
  caution for interpretation, green a checkpoint.
- **Code**: `.code` (white-space preserved) with `.c` comment, `.k` keyword, `.s` string, `.dim`, and `.hl` for
  highlighted lines. Write one command line per text line, or one block-level child per line. `export_pptx.py`
  preserves code line breaks and coloured runs. The Office exporter writes one box per rendered line with
  wrapping disabled, matching the Office font baseline and advance widths; do not use guessed box positions.
- **Smaller pieces**: `.tag`, `.label`, `.big`, `.muted`, `.center`.

**bio.js**: every function returns an SVG string.
- **Molecules**:
  - `helix(x1,x2,y,amp,period)`
  - `nucleosome(x,y,r)`
  - `chromatin(x1,x2,y,[nucX…],r)`
  - `tfProtein(x,y,color,label,s)`
  - `tn5Dimer(x,y,s,withLabels)`
  - `seqFragment(x,y,len)`
  - `readArrow(x,y,len,dir,color)`
- **Tracks**:
  - `coverage(x1,x2,y0,[[centre,height,width]…],line,fill,noise)`
  - `geneModel(x1,x2,y,[[s,e]…],name)`
  - `band(x,y,w,h,fill,text,color)`
  - `bracket(x1,x2,y,up,label,color,sub)`
  - `txt(x,y,text,size,color,weight,anchor)`
- **Cells** (simple; prefer NIH BioArt): `hepatocyte`, `neuron`.
- **Charts**:
  - `axes(x,y,w,h,xlabel,ylabel)`
  - `xticks(...)`
  - `fragLenCurve(x,y,w,h,good,color,maxbp)`
  - `tssHeatmap(...)`
  - `tssProfile(...)`
  - `pcaPlot(x,y,w,h,groups,xl,yl)`
  - `volcano(...)`
  - `pie(cx,cy,r,[[label,frac,color]…],lx,ly)`
  - `seqLogo(x,y,colW,h,[{A,C,G,T}…])`
  - `footprintCurve(...)`
  - `countdown(...)`
- **Colours**: `B.*` in bio.js. For example `B.adA` and `B.adB` are the red and blue adapters/reads, `B.tf` is
  purple, `B.tn5` is teal, and `B.peak` is orange-red.

**cartoon.js**
- **Chrome**: `header()`, `squiggle(w)` (title underline) and `applyStep()`.
- **Marks**: `arrow(x1,y1,x2,y2,color,w)`, `tick(x,y,s)` (green tick) and `cross(x,y,s)` (red cross).
- **Don't use**: `yarn`, `spool`, `scissors`, `clip`, `hill`, `camera` and `cell` are optional cartoon motifs.
  Scientific diagrams generally benefit from domain-specific visual vocabulary instead.

**Figures**: put PNG or SVG files in `assets/figs/` and show them as `<div class="card"><img src="../assets/figs/x.png"></div>`.
Generate them with matplotlib at 200 dpi, styled like the real tool's output (`examples/figures_example.py`). Keep
captions neutral ("示意结果"), with no dataset accession and no "原课件".

## 5. Self-check list (look at every step's PNG)

1. No text overflows its card, nothing overlaps, and nothing is clipped at the canvas edge.
2. The subtitle band (y > 930) is empty, and each step's new content has free space beside it for the mascot.
3. What appears at step N matches beat N's narration, and earlier content stays visible unless `data-until` hides it.
4. Commands, parameters and file names match the narration and chain correctly from page to page.
5. No leftover text that isn't pulling its weight, such as a heading that repeats the title.


## 6. Pace and precise highlight timing

For external narration, script.json may contain `"pace": {"tempo": 0.93, "sentence_gap": 0.7, "beat_gap": 1.0}`.
Tempo uses ffmpeg atempo to keep pitch; the two gaps are minimum silences, not extra pauses added to every sentence.
Defaults preserve the existing pace when the object is omitted.

Each beat may use `frame` to record what should be ringed (review guidance), `focus` to override pixel bounds,
`hl: false` to suppress its ring, and `ring_at` to delay the ring until a literal phrase in that beat's narration.
`frame` itself does not select a DOM element: use data-focus or focus. The delay follows the subtitle's character
weights; it is approximate, so inspect real video frames. Missing ring_at text raises an error.
Small targets receive thinner, closer rings so neighbouring code characters stay legible.

After changing focus or placement: render pages, run focus_preview.py, then `python3 build.py frames` to inspect
all beats along the full mascot path. These previews are composed images; for delivery also extract frames from
the encoded MP4, including the subtitle and the moment after any ring_at delay.
