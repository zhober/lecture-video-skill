# Environment and configuration

## Python dependencies

Use Python 3.10 or newer in a virtual environment. Scripts use the interpreter that runs them; they do not
switch to a machine-specific Python installation.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run installation commands from the skill checkout; run production scripts from a copy of `template/`
inside a separate project's `build/`. `imageio-ffmpeg` supplies the encoder binary. For ASR, scripts decode
and resample audio to float32 16 kHz arrays before passing it to faster-whisper.

## Browser

The default is installed Google Chrome via Playwright's `chrome` channel. Alternatively install Chromium
and set an empty channel:

```sh
python -m playwright install chromium
export LECTURE_BROWSER_CHANNEL=""
```

## Speech recognition

Use model names such as `small` and `large-v3-turbo`, or supply a local model directory. A first model-name
run may download weights to the normal model cache. Keep model files outside the skill repository.

`check_external.py` accepts the model as its second argument. For sentence patching, new-take checks and
sync checking, set `LECTURE_ASR_MODEL` to a model name or directory; the default is `large-v3-turbo`.
The `small` model is the second independent checker in the take-repair scripts.

## Fonts

HTML pages prefer PingFang SC with the CSS fallbacks in `assets/theme.css`. Code prefers Menlo/monospace.
The bundled ZCOOL KuaiLe font is used for mascot placards and carries its SIL Open Font License in
`assets/fonts/OFL-zcoolkuaile.txt`.

On macOS, subtitles default to the system Hiragino Sans GB collection, index 2. Other systems should supply
an installed CJK font and its face index:

```sh
export LECTURE_SUBTITLE_FONT="/path/to/cjk-font.ttf"
export LECTURE_SUBTITLE_FONT_INDEX="0"
```

`LECTURE_MONO_FONT` configures the optional approximate PPTX preview. System font paths are platform defaults;
personal font files and licensed Office font binaries are not distributed with this skill.

## Optional Office export on macOS

`prepare_pptx_fonts.py [DFonts-directory]` extracts Microsoft YaHei and Consolas from an installed
Microsoft PowerPoint application into the project's `cache/fonts_office/`. Its default directory is the
application's standard `Contents/Resources/DFonts` directory. It removes only an empty Consolas `prep` table
that otherwise causes Chrome's font sanitizer to reject the font. It does not install or change system fonts.

`export_pptx_office.py` lays out text using these fonts and writes boxes by rendered baseline and width.
`pptx_check.py render` asks PowerPoint to export a PDF alongside the deck, then renders it to PNG.
`measure` compares intended and actual glyph positions. Use `measure --calibrate` followed by a fresh export
when the current Office version/fonts require calibration. Calibration stays in the project cache.

Actual PowerPoint export uses macOS AppleScript. Save the PDF inside the project alongside the PPTX to avoid
application sandbox destination restrictions. On platforms without this integration, use the generic exporter
and inspect the resulting deck in the presentation software you intend to use. `pptx_sim.py` is approximate.

## Local files

Keep recordings, scripts containing course-specific information, generated frames, final presentations,
model weights, calibration and logs in the project. These are not skill source files and should not be added
to a public skill repository.
