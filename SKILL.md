---
name: lecture-video
description: >-
  Create narrated teaching videos from slides, outlines, papers or course material, with 1080p MP4,
  subtitles, a timestamped transcript and an editable PPTX. Use for lecture-video production,
  narration checking or sentence-level voice-over replacement. Supports stepwise HTML/SVG visuals,
  moving highlights and externally generated narration.
---

# Lecture video

Produce a teaching video whose narration, progressive reveals, highlights and subtitles explain the same
material at the same time. Also deliver an editable slide deck and transcript. Adapt the topic, duration,
voice and visual style to the request; the included biology examples are demonstrations using synthetic data.

## Project setup

Copy this skill's `template/` into a separate project's `build/` directory. Work on course-specific files there,
keeping the installed skill free of recordings, private slides, generated outputs and working logs.

Read [references/environment.md](references/environment.md) before running the scripts. Use the active Python
environment; browser, ASR-model and font locations are configurable. Office export and actual PowerPoint
verification are optional macOS features.

```text
project/
  build/                  scripts, assets, pages, script.json, cache, out
  配音脚本/               narration text prepared for the chosen TTS platform
  配音/platform/          externally generated recordings
  topic_教学视频.mp4
  topic_字幕.srt
  topic_逐字稿.md
  topic_课件.pptx
```

## Content and script

Read the source material, including its figures, then propose page order, approximate timings, visuals and
the narration's main points. Identify material to simplify and technical corrections. Get agreement on the
outline before a substantial production run unless the user already approved it or explicitly requests a
direct full build. A short sample helps establish appearance, pacing and voice when those choices are open.

Write `build/script.json` with one entry per page and one beat per reveal step. Read
[references/pages.md](references/pages.md) for the schema and layout contract. Use
`examples/script.example.json` and `examples/pages/` as working examples.

- Use clear lecture language and preserve the technical meaning of the source.
- End narration sentences with `。！？；`; alignment and sentence replacement use these boundaries.
- Put pronunciation changes in `pron` for draft TTS or `tts_say` for external recordings, keeping display text
  unchanged. Check unfamiliar terms rather than respelling every English identifier.
- Describe simulated figures as illustrations; do not present their values as measured study results.
- Keep course-specific information and approved edits in the project, not in the skill's shared instructions.

## Visuals

Create `build/pages/pNN.html` at 1920×1080. `data-s` reveals elements, `data-until` hides a prior scene,
`data-hl` highlights code, and `data-focus` identifies the item being explained. Leave room for subtitles
and mascot placement. `frame` records the intended target for review; `ring_at` delays the ring until a
phrase in the narration. Their complete behavior is documented in the page reference.

Prefer accurate scientific diagrams. Use `template/assets/bio.js` for the included biology vocabulary and
`examples/figures_example.py` for synthetic plots. Inspect every rendered step for overflow, clipping,
misplaced rings and content under the subtitle band.

```sh
python render.py mascots
python render.py pages p03 p10 p12 p28
python focus_preview.py p03 p10 p12 p28
python build.py frames
```

The mascot is a silent visual guide. Use poses and brief rings to direct attention without hiding material.
Style defaults are suggestions: paper-colored pages, clear code blocks, scientific schematics and a closing
take-home page. Honor the requested style rather than treating these defaults as universal requirements.

## Narration

Read [references/narration.md](references/narration.md) when preparing, checking, aligning or repairing speech.
Edge TTS is available for drafts; external recordings support a chosen voice or TTS platform. For a web
platform such as 豆包, prepare text files and a concise generation prompt naming their input/output locations;
the user performs account-dependent synthesis. Use credentials only through an explicitly authorized workflow.

```sh
python make_tts_inputs.py 豆包
python check_external.py ../配音/豆包 small
python check_external.py ../配音/豆包 large-v3-turbo
python align_external.py ../配音/豆包
```

Check suspected errors with two ASR models and inspect complete sentence windows. English terms, homophones
and short-window hallucinations can lower exact-text scores. Replace faulty sentences at surrounding pauses;
preserve correct recordings and manual cuts. Never recut an accepted batch to fix one sentence.
Use the optional sentence-reuse scripts described in the narration reference when a revised outline keeps
substantial parts of an already approved recording.

## Assembly and verification

Set `engine` to `external` after external audio is aligned. Optional `pace` settings control tempo while
preserving pitch and enforce minimum sentence/beat gaps.

```sh
python build.py video final -j8
python sync_check.py final 40
python make_docs.py out/final.timeline.json out/final.md
python export_pptx.py out/final.pptx
```

For editable text aligned with Office fonts on macOS, use the optional exporter:

```sh
python prepare_pptx_fonts.py
python export_pptx_office.py out/final.pptx
python pptx_check.py render out/final.pptx
python pptx_check.py measure out/final.pptx
```

Review frames from the encoded MP4, not only composited previews. Check the duration, subtitles, patched
sentences and slide text positions. A cue-window ASR mean of 0.9 with no score below 0.6 is a useful starting
reference, not proof of quality: retain original scores and separately document complete-sentence rechecks.
Recalibrate Office text positions on the current installation when needed; no personal calibration cache is shipped.

Deliver the MP4, SRT, timestamped Markdown transcript and editable PPTX to the project root. Preserve prior
deliverables in a versioned archive directory. Surface the final files with the current agent's file-delivery
tool when available; tool names are environment-specific.
