# Voice-to-vault

Record a voice memo; this Mac transcribes it and files it. Not a Claude Code plugin, a small background job (launchd), so nothing here talks to an AI.

## How it routes
Say the trigger as your first word:

| You start with | It goes to | What is written |
|---|---|---|
| "Line", "Line bank", "Poem line", "LaBeau" | `~/Developer/labeau-ops/data/line-bank/voice/` plus the audio in `~/LaBeau-Assets/Voice Lines/` | Your words exactly as transcribed, trigger word removed, nothing else touched. Marked `status: unreviewed` because the transcript is a machine's ear, not yours. |
| "Private", "Vault", "Journal", "Recovery", or anything else | `Recovery/Recovery Library/Imported/Voice Inbox/` with the audio beside it | Raw transcript, `status: needs-intake`, for the recovery-transcript-intake skill to classify and file. |

Private is the default: a memo only reaches LaBeau if you said "Line" first. A line memo that names a real person, therapy, a lawyer or court, money, a phone number or an email is held in the vault instead, with `held_from_line_bank:` saying why. The list also takes in every name and word in `~/Developer/claude-mods/config/private-names.txt` and `private-words.txt` (privacy-preflight's lists), so one list covers both. Add more under `private_words` in `config.json`.

## Text drops
`.txt` and `.md` files dropped in `~/Voice Inbox` (the brain-dump mod's Save, the phone app's export) follow the same triggers and routes, with no transcription. Put the trigger word first, then the text, UTF-8, one dump per file.

## Guarantees
- Transcription is local (mlx-whisper). If it is missing, the job stops and leaves the audio where it is; there is no cloud fallback.
- The log (`state/voice-vault.log`) holds file names, routes and hashes, never what you said.
- Audio dropped in `~/Voice Inbox` is moved to its destination. Folders listed under `watch_readonly` (for example the Voice Memos app) are only read, never changed.
- Each recording is filed once (tracked by hash in `state/processed.json`).

## Getting memos onto the Mac
- **Voice Memos auto-sync (default, Chris's pick 2026-10-22):** record in the iPhone Voice Memos app with iCloud sync on (Settings > your name > iCloud > Voice Memos). install.sh writes `config.json` to read the Mac's Voice Memos folder (read-only) and sets `watch_since` to the install time, so older recordings are left alone. The job needs Full Disk Access; install.sh prints the path. The audio does pass through your iCloud.
- **Local only:** AirDrop the memo to the Mac and drop it in `~/Voice Inbox`. To turn auto-sync off, set `"watch_readonly": []` in `config.json`.

## Install
```
cd ~/Developer/claude-mods/voice-vault && ./install.sh
```
Tests: `.venv/bin/python -m unittest discover -s tests`. Run once by hand: `.venv/bin/python voice_vault.py`. Stop it: `launchctl bootout gui/$(id -u)/com.chris.voice-vault`.
