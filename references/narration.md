# Narration preparation, checking and repair

## Contents
1. Choose and prepare a voice
2. Check with two ASR models
3. Patch sentences
4. Align and control pacing
5. Reuse approved sentences

## 1. Choose and prepare a voice

Use the voice and platform requested for the project. Edge TTS can provide a draft; external recordings
support a preferred narrator or hosted TTS voice. Check a term-dense sample before recording a long course.
Do not assume a narrator's technical pronunciation is correct because ordinary sentences sound natural.

For a web platform such as 豆包语音合成 2.0:

```sh
python make_tts_inputs.py 豆包
```

This produces a sample, a complete text file and parts in `配音脚本/`. The default chunk size is conservative;
adjust it to the selected platform's actual limit. `tts_instruction` is a tone instruction, not spoken text.
If the platform reads it aloud, provide the instruction through its settings instead.

Give a short generation prompt naming the project-local input files, the selected voice and the output files.
For local-file workflows, absolute paths belong in that project's handoff prompt; they must not be copied into
shared skill documentation. The user handles account-dependent web synthesis unless another workflow is authorized.

Save audio in `配音/platform/`. Files are naturally sorted; WAV, MP3 and M4A are supported by the alignment
pipeline. Move concatenated duplicates out of the input directory before processing it.

Use `tts_say` to change spoken spelling without altering subtitles: commas may read more consistently than
enumeration punctuation; word boundaries can help camelCase identifiers; Chinese number spellings can help
digits; a spoken name can replace a Greek symbol. Apply these changes only where a sample demonstrates a problem.

## 2. Check with two ASR models

```sh
python check_external.py ../配音/豆包 small
python check_external.py ../配音/豆包 large-v3-turbo
```

Reports include sentence coverage, unmatched extra speech, technical-term hits, pauses, loudness, clipping
and pitch. Checks are cached per source-folder/file modification time under `cache/external/check/`.

Investigate a suspected error when both models have low similarity (minimum below 0.8 and maximum below 0.9),
or both identify unexpected speech near the same time. Inspect a complete sentence with a little surrounding
silence before deciding it needs replacement.

Typical recognition differences include phonetic English spellings, Chinese homophones, traditional/simplified
characters, Arabic/Chinese numerals and punctuation. Short partial cues can produce unrelated hallucinated text.
Similarity is a screening aid: coherent recognition of the expected sentence matters more than spelling alone.

Real problems include nonsensical speech, missing clauses, repeated phrases or a changed content word confirmed
by both models. Report the audio filename, time range, expected content and observed issue.

## 3. Patch sentences

Replace only faulty sentences or runs at surrounding pauses. Avoid word-level splices when a complete sentence
can be regenerated; they are more likely to produce audible changes in pitch or articulation.

```sh
python patch_sentences.py prepare 5,24,34-36
python patch_sentences.py apply
```

Indices are the `check_external.py` global sentence indices in script order, split on `。！？；`.
`prepare` writes `配音脚本/platform_补句.txt` and numbered chunk files. Non-override takes in
`配音/platform_补句/` are joined in natural order; `第N行.wav` overrides line N. `VOICE_DIR` selects the platform
folder; the default is `豆包`.

An `@` token denotes a supplied good sentence from an earlier recording. Put these tokens after the lines
requiring synthesis. Preserve earlier approved audio locally so a new take does not erase the only good copy.

`apply` matches replacement lines, locates surrounding pauses, matches loudness and writes
`配音/platform_修补/`. Recheck the result with both models. Word timestamps can extend into silence or neighbouring
speech, so a clean textual match alone does not guarantee a clean splice.

If a take contains a garbled insert or if character alignment trims a spoken alias, cut at actual pauses,
retain a manual-cut record and transcribe the complete repaired sentence. WAVs with unknown header lengths
should be converted/cropped with ffmpeg rather than assuming Python's wave writer can crop them directly.

## 4. Align and control pacing

```sh
python align_external.py ../配音/豆包_修补
```

Input may be one `全文` recording, one file per page (`P01`, `P02`, ...), or a naturally ordered set of parts.
The pipeline converts to 24 kHz mono, trims long leading/trailing silence, normalizes loudness and aligns
sentences. It writes per-page audio and exact sentence spans in `cache/external/align.json`.

Set `engine` to `external` in script.json. Optional pacing:

```json
"pace": {"tempo": 0.93, "sentence_gap": 0.7, "beat_gap": 1.0}
```

Tempo changes use ffmpeg atempo to preserve pitch. Gaps are minimum sentence/beat silences, not additional
pauses inserted unconditionally. Evaluate pacing on a representative sample.

After assembly, run `sync_check.py` over 30–40 subtitle windows and any repaired sentences. Keep the raw scores.
If a short window fails, separately recheck its complete sentence from the encoded MP4 audio with both models.
Document whether the problem was a splice, timing, pronunciation or recognition error; do not hide a failed
screening score by changing the sample.

## 5. Reuse approved sentences

Optional `assemble_v3.py`, `cut_new_takes.py` and `retake_one.py` illustrate a cache-based revision workflow.
Their v2/v3 labels are file-layout conventions, not mandatory course versions. Populate these files in a project:

- `cache/clips_v2/index.json`: maps punctuation-normalized text to `text`, `wav` and `speech: [start,end]`
  relative to a reusable approved clip.
- `cache/clips_v2/new_lines.json`: new recording order, as objects containing `sentences` lists.
- `cache/clips_v3/check.json`: new clips and their two-model check results, produced by `cut_new_takes.py`.

`cut_new_takes.py [take-directory]` cuts and checks a whole batch. Its default directory is
`配音/豆包_补录v3/`. Do not run a batch recut over accepted manual cuts.
`retake_one.py N [take.wav]` updates just one sentence, trimming at speech edges; each take must contain only
that sentence. `assemble_v3.py` combines reused and new sentences, matches loudness and writes per-page audio
and spans directly. Do not deliver an assembly made with `--allow-bad`; resolve every missing or unaccepted clip.
