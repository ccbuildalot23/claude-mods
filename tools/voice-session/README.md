# voice-session

Puts Chris's own voice on about 85% of next month's LaBeau Reels and TikToks, from one recording session. Built Oct 24, 2026, for his session on Sun Oct 25.

His ask (Oct 24, 2026): "I want to begin incorporating my voice in my videos going forward ... not every post, but we can do 85% of the posts lets see how they do ... one long read and you can cut the audio, or a few short reads, and then apply it directly to the videos."

## What's here

- `voice_session.py`: the pipeline. It installs as `labeau-ops/scripts/voice_session.py`.
  - `check`: shows the plan, what gets his voice, what stays silent and why, and whether the words still match `fragments.csv`.
  - `onsets`: reads when each of his lines appears on screen in each staged video. It uses Apple Vision on the Mac and tesseract elsewhere, and caches the result in `data/voice/onsets.json`.
  - `cut <memo.m4a> [...]`: finds every passage in his Voice Memo(s) with whisper-cli on the Mac. If he stumbles and rereads, the last clean take wins. It cuts each line in the breath before the next one and lists any passage it couldn't find.
  - `lay`: places each line clip at the moment that line appears on screen. The first line starts inside the first second, and no line is heard before it shows. The voice is brought to -14 LUFS with peaks under -1.5 dB. The video stream is copied bit for bit (checked by md5), so safe zones and hook-first frames stay exactly as approved. If his read runs past the end, the last frame is held instead of cutting his voice. Each output is read back with `audio_readback` (whisper). Output goes to `03-review/voice/2026-10-25/out/`.
  - `stage`: copies the voiced files over the originals in `04-posts` and keeps each original in `_pre-voice-2026-10-25/`. Each voiced file is recorded in the asset ledger under its existing key, so `labeau validate` stays clean. This is his hand, run from a paste.
  - `selftest`: runs the whole chain on the Mac with a synthetic read (macOS `say`) that includes a stumble and a retake, on two real staged videos, in a temp folder. Nothing is staged.
- `test_voice_session.py`: 19 unit tests. They cover finding takes, retakes, cut points, placement, line visibility, and stale words.
- `session-2026-10-25.json`: the plan. It has 57 passages (1,040 of his words, word for word from `fragments.csv`, overlapping fragments merged into one read) and 90 Instagram slots from Oct 26 to Nov 24, each with its TikTok twin.
  - 72 slots get his new read.
  - 5 already carry his read-alouds.
  - 13 stay silent, which makes 85.6% voiced.
  - The silent slots are 2 beat-cut Reels, 1 photo carousel, 1 Wavy highlight, 5 spoken pieces that aren't poem lines, and 4 matched control pairs. Each control pair is the same gem posted once silent and once voiced, in alternating order.
- `gen_plan.py`: builds the plan from `placements.csv`, `plan_3x.csv` and `fragments.csv`.
- `make_script.py`: renders the reading script with mood, pace and breath marks. His lines come from the plan untouched, and direction is always in italic brackets.
- `e2e_cloud.py`: the cloud end-to-end test. It builds a synthetic memo with espeak-ng, word by word so every word's time is known, and adds chatter, a stumble and retake, and a skipped passage. It then runs cut and lay on real staged videos. It checks that the retake was used, every clip holds its whole line, the first word lands inside 1 s, the picture is unchanged, the loudness is right, and the skipped passage is reported. whisper-cli is replaced by the known word times plus injected recognizer errors, because the model can't be downloaded in the cloud.
- `onsets_all.py`: precomputes line onsets for every staged video in parallel.

## Not covered

- Gist gets no voice.
- The DP-F8 B copy (`DP-F8-B`) is built into `03-review` for the A/B test and is never staged over the A file.
- Slots after Nov 10 aren't built yet. Run `lay` again after each new batch is staged; the clips are kept.
- Gems may be reworked the day before posting. When a fragment's words change, `lay` refuses that slot and says so, and a new read is needed.

## Oct 24, 2026: his first real session

- Lines he reads in one breath are cut as one clip (`runs` in `takes.json`) and laid at the first line's onset when the post shows all of them, so his phrasing has no seam in it.
- When something unscripted sits between two lines (a "damn", a restart, the passage number read aloud), line i ends in the first pause after it and line i + 1 starts in the last pause before it, so the extra words are dropped.
- A clip's start looks back only 0.45 s for a breath, so it can't catch the tail of a false start.
- `asr_cloud.py` is the cloud stand-in for whisper-cli: sherpa-onnx with NeMo parakeet-tdt-0.6b-v2 int8, downloaded from the k2-fsa GitHub releases because Hugging Face is blocked in the cloud. It gives word times from token timestamps and works as a `TRANSCRIBE` swap.
