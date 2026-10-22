# Voice-to-vault

Record a voice memo; this Mac transcribes it and files it. Not a Claude Code plugin, a small background job (launchd), so nothing here talks to an AI.

## How it routes
Say the trigger as your first word:

| You start with | It goes to | What is written |
|---|---|---|
| "Line", "Line bank", "Poem line", "LaBeau" | `~/Developer/labeau-ops/data/line-bank/voice/` plus the audio in `~/LaBeau-Assets/Voice Lines/` | Your words exactly as transcribed, trigger word removed, nothing else touched. Marked `status: unreviewed` because the transcript is a machine's ear, not yours. |
| "Private", "Vault", "Journal", "Recovery", or anything else | `Recovery/Recovery Library/Imported/Voice Inbox/` with the audio beside it | Raw transcript, `status: needs-intake`, for the recovery-transcript-intake skill to classify and file. |

Private is the default: a memo only reaches LaBeau if you said "Line" first. A line memo that names a real person, therapy, a lawyer or court, money, a phone number or an email is held in the vault instead, with `held_from_line_bank:` saying why. Edit `private_words` in `config.json` to tune that list.

## Text drops
`.txt` and `.md` files dropped in `~/Voice Inbox` (the brain-dump mod's Save, the phone app's export) follow the same triggers and routes, with no transcription. Put the trigger word first, then the text, UTF-8, one dump per file.

## Guarantees
- Transcription is local (mlx-whisper). If it is missing, the job stops and leaves the audio where it is; there is no cloud fallback.
- The log (`state/voice-vault.log`) holds file names, routes and hashes, never what you said.
- Audio dropped in `~/Voice Inbox` is moved to its destination. Folders listed under `watch_readonly` (for example the Voice Memos app) are only read, never changed.
- Each recording is filed once (tracked by hash in `state/processed.json`).

## Getting memos onto the Mac
- **Local only (default):** on the iPhone, share the memo by AirDrop to the Mac, then drag it into `~/Voice Inbox` (or save it there from Files).
- **Zero taps:** if Voice Memos iCloud sync is on, add this to `config.json` and give the job Full Disk Access (install.sh prints the path):
  `{"watch_readonly": ["~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"]}`
  Only memos recorded after you turn it on will be new to the job, but older ones in that folder will be filed on the first run too.

## Install
```
cd ~/Developer/claude-mods/voice-vault && ./install.sh
```
Tests: `.venv/bin/python -m unittest discover -s tests`. Run once by hand: `.venv/bin/python voice_vault.py`. Stop it: `launchctl bootout gui/$(id -u)/com.chris.voice-vault`.
