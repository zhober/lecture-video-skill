# lecture-video-skill

English | [简体中文](README.zh-CN.md)

Turn slides, outlines or papers into narrated teaching videos, delivered together with subtitles,
a transcript and an editable slide deck.

This is a workflow and script template for coding agents that support `SKILL.md`. The examples use
a bioinformatics topic with simulated data; the workflow also works for other science courses.

## Features

- Split an explanation into HTML/SVG pages revealed step by step, rendered to 1080p video.
- Highlight the diagram or code being explained, with a moving mascot and delayed highlights.
- Check external narration for omissions, misreadings and repetitions; patch individual sentences
  and reuse recordings that were already approved.
- Adjust speaking rate and the pauses between sentences and steps while preserving pitch.
- Export MP4, SRT, a Markdown transcript with per-page timestamps, and a PPTX with editable text.
- Optional: lay out the deck with Office fonts on macOS and check PowerPoint's actual rendering.

## Installation and usage

Put the contents of this repository in your agent's skills directory, in a folder named
`lecture-video`. For example:

```text
skills/
  lecture-video/
    SKILL.md
    references/
    template/
    examples/
```

Example prompt:

```text
Use /lecture-video to turn this slide deck into a ~20-minute teaching video. Draft the outline first.
```

The scripts need Python 3.10+, the dependencies and a browser. See
[references/environment.md](references/environment.md) for installation and configuration, and
[SKILL.md](SKILL.md) for the production workflow.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
export LECTURE_BROWSER_CHANNEL=""
```

Copy `template/` into a course project as `build/`, then edit pages and scripts and store narration
audio in that project. `examples/` provides four pages, the matching narration structure and a script
that generates the simulated result plot. Final narration can come from external recordings or a TTS
platform of your choice; account-dependent steps require the corresponding authorization.

## Configuration

| Variable | Purpose |
| --- | --- |
| `LECTURE_BROWSER_CHANNEL` | Playwright browser channel; an empty string uses the installed Chromium |
| `LECTURE_ASR_MODEL` | ASR model name or local model directory, default `large-v3-turbo` |
| `LECTURE_SUBTITLE_FONT` | CJK font file used for subtitles |
| `LECTURE_SUBTITLE_FONT_INDEX` | Face index within a font collection |
| `LECTURE_MONO_FONT` | Monospace font for the optional approximate PPTX preview |
| `VOICE_DIR` | Narration platform directory name, default `豆包` |

The macOS system font paths and PowerPoint application path are platform defaults; on other systems,
configure fonts and the browser as described in the environment reference. Office-font export and
PowerPoint verification depend on locally installed software; this repository does not include those fonts.

## Repository contents

- `SKILL.md`: agent entry point and production workflow.
- `references/`: page contract, narration repair and runtime environment.
- `template/`: build scripts and visual assets to copy into a course project.
- `examples/`: generic examples and a simulated plot.
- `requirements.txt`: Python dependencies.

Private course material, recordings, transcripts, personal paths, account settings, model weights,
calibration caches, generated output and work logs belong in the course project, not in this public
skill repository. Copyright and license information for the bundled font is in [NOTICE.md](NOTICE.md).
