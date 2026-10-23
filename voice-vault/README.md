# Voice-to-vault

Record a voice memo; this Mac transcribes it and files it. Not a Claude Code plugin, a small background job (launchd), so nothing here talks to an AI.

## How it routes
Say the trigger as your first word:

| You start with | It goes to | What is written |
|---|---|---|
| "Line", "Line bank", "Poem line", "LaBeau" | `~/Developer/labeau-ops/data/line-bank/voice/` plus the audio in `~/LaBeau-Assets/Voice Lines/` | Your words exactly as transcribed, trigger word removed, nothing else touched. Marked `status: unreviewed` because the transcript is a machine's ear, not yours. |
| "Share", "Share LaBeau", "Share Chris", "Share both" | `~/Developer/labeau-ops/data/share-candidates/share-candidates.csv` (the Brand Message Library), brand `both` unless you name one | Your words exactly, one row, status `share-candidate`, with the EI journal week. Same privacy hold as Line. |
| "Private", "Vault", "Journal", "Recovery", or anything else | `Recovery/Recovery Library/Imported/Voice Inbox/` with the audio beside it | Raw transcript, `status: needs-intake`, for the recovery-transcript-intake skill to classify and file. |

Private is the default: a memo only reaches LaBeau if you said "Line" first. A line memo that names a real person, therapy, a lawyer or court, money, a phone number or an email is held in the vault instead, with `held_from_line_bank:` saying why. The list also takes in every name and word in `~/Developer/claude-mods/config/private-names.txt` and `private-words.txt` (privacy-preflight's lists), so one list covers both. Add more under `private_words` in `config.json`.

## Text drops
`.txt` and `.md` files dropped in `~/Voice Inbox` (the brain-dump mod's Save, the phone app's export) follow the same triggers and routes, with no transcription. Put the trigger word first, then the text, UTF-8, one dump per file.

## Diary pages and the Sunday harvest
Photos (`.jpg`, `.heic`, `.png`) dropped in `~/Voice Inbox` are always private: each one moves to `Recovery/Recovery Library/Imported/Diary Pages/` with a sidecar note holding Apple Vision's reading of every line (on this Mac, language correction off), `status: needs-harvest`.

On Sunday, type `harvest`. It files anything new, then opens a page on this Mac only (127.0.0.1, one-time key). Tick the lines you marked with the nib, fix any misread word so it matches your pen, and pick where each goes:

| Pick | Goes to |
|---|---|
| LaBeau, Chris, Both | `labeau-ops/data/share-candidates/share-candidates.csv`, word for word |
| Lens | `labeau-ops/data/hierophant-lens/hierophant-lens.md`, "From Chris's pages" (Saturday Build answers) |
| Echo | the same Lens, "Echo" section (readers' words from a Friday Connect, never their names) |

Every ticked line runs the privacy check first; a line that trips it is shown in red and stays in the vault. Unticked lines never leave the vault. Pages are then marked `harvested`. `harvest --demo` runs the same page on made-up pages in a temp folder.

blast-radius treats `share-candidates/` and `hierophant-lens/` as pen-rule folders: agents read them and never write there. Install once with `./install-harvest.sh` (adds the Vision reader, the Lens, the folder and the `harvest` command; leaves the launchd job alone).

## Guarantees
- Transcription is local (mlx-whisper). If it is missing, the job stops and leaves the audio where it is; there is no cloud fallback.
- The log (`state/voice-vault.log`) holds file names, routes and hashes, never what you said.
- Audio dropped in `~/Voice Inbox` is moved to its destination. Folders listed under `watch_readonly` (for example the Voice Memos app) are only read, never changed.
- Each recording is filed once (tracked by hash in `state/processed.json`).

## Getting memos onto the Mac
- **Voice Memos auto-sync (default, Chris's pick 2026-10-22):** record in the iPhone Voice Memos app with iCloud sync on (Settings > your name > iCloud > Voice Memos). install.sh writes `config.json` to read the Mac's Voice Memos folder (read-only) and sets `watch_since` to the install time, so older recordings are left alone. The job runs inside `~/Applications/VoiceVault.app`, and that app alone needs Full Disk Access (launchd will not pass Python's permission to a background job); install.sh opens the pane and the app for you. The audio does pass through your iCloud.
- **Local only:** AirDrop the memo to the Mac and drop it in `~/Voice Inbox`. To turn auto-sync off, set `"watch_readonly": []` in `config.json`.

## Install
```
cd ~/Developer/claude-mods/voice-vault && ./install.sh
```
Tests (voice-vault and harvest): `.venv/bin/python -m unittest discover -s tests`. Run once by hand: `.venv/bin/python voice_vault.py`. Stop it: `launchctl bootout gui/$(id -u)/com.chris.voice-vault`.
