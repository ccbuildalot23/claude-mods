# Voice-to-vault

Record a voice memo; this Mac transcribes it and files it. Not a Claude Code plugin, a small background job (launchd), so nothing here talks to an AI.

## How it routes
Say the trigger as your first word:

| You start with | It goes to | What is written |
|---|---|---|
| "Line", "Line bank", "Poem line", "LaBeau" | `~/Developer/labeau-ops/data/line-bank/voice/` plus the audio in `~/LaBeau-Assets/Voice Lines/` | Your words exactly as transcribed, trigger word removed, nothing else touched. Marked `status: unreviewed` because the transcript is a machine's ear, not yours. |
| "Share", "Share LaBeau", "Share Chris", "Share both" | `~/Developer/labeau-ops/data/share-candidates/share-candidates.csv` (the Brand Message Library), brand `both` unless you name one | Your words exactly, one row, status `pending` until the Monday docket, with the EI journal week. Same privacy hold as Line. |
| "Private", "Vault", "Journal", "Recovery", or anything else | `Recovery/Recovery Library/Imported/Voice Inbox/` with the audio beside it | Raw transcript, `status: needs-intake`, for the recovery-transcript-intake skill to classify and file. |

Private is the default: a memo only reaches LaBeau if you said "Line" first. A line memo that names a real person, therapy, a lawyer or court, money, a phone number or an email is held in the vault instead, with `held_from_line_bank:` saying why. The list also takes in every name and word in `~/Developer/claude-mods/config/private-names.txt` and `private-words.txt` (privacy-preflight's lists), so one list covers both. Add more under `private_words` in `config.json`.

## Text drops
`.txt` and `.md` files dropped in `~/Voice Inbox` (the brain-dump mod's Save, the phone app's export) follow the same triggers and routes, with no transcription. Put the trigger word first, then the text, UTF-8, one dump per file.

## Journal pages: the gate and the Monday docket
Everything in Chris's journal is fair game for the brand (his ruling, Oct 23, 2026); people's names are the one stop.

1. **Sunday:** drop photos of the week's pages in `~/Voice Inbox`.
2. **Overnight:** launchd runs `journal_gate.py run` (2:30 am, 7 am, noon, 7 pm). Each photo moves to `~/LaBeau-Assets/Journal Pages/` and Apple Vision reads it on this Mac (language correction off). Every line goes, word for word, into `~/Developer/labeau-ops/data/share-candidates/share-candidates.csv`: plain lines are `pending`; a line naming a person is `held-name` with role options; a line Vision was unsure of is `held-reading`.
3. **Monday 7 am:** the docket email (to Gmail and admin@) lists held lines with their role options and everything new. Reply only for a change: `strike 3`, `3 b` (pick role b), `3: my coach` (your own words for the name), `ok 4` (fine as read; on a name line it keeps the name), `4 fix: exact words`, `lens 2` / `echo 6` (into the Hierophant Lens). The gate reads replies from Gmail at its next run and emails back what it did.
4. **Tuesday 7 am:** pending lines clear. Held lines wait and return on the next docket.

Agents read only `cleared.csv` (written beside the library, cleared lines alone) and quote `shared_line`; the full table, with names not yet swapped, stays for the gate. Role options come from `../config/name-roles.txt` (`Name = my brother | my big brother`, Mac only, never committed); words that look like names but are not go in `../config/name-ok.txt`. The `harvest` command reads new photos right away. `journal_gate.py docket` previews the next docket; `journal_gate.py apply "strike 3"` applies a command by hand. Logs hold counts, never journal words.

blast-radius treats `share-candidates/` and `hierophant-lens/` as pen-rule folders: agents read them and never write there. Install once with `./install-gate.sh`, then `./wire-agents.sh` (points labeau-ops CLAUDE.md, Grok and Muse at the Lens and cleared.csv; safe to run twice). The installer covers the reader, Lens, launchd job, `harvest` command, a self-test on a made-up page and a mail login check; leaves the voice-vault job alone).

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
Tests (voice-vault and the journal gate): `.venv/bin/python -m unittest discover -s tests`. Run once by hand: `.venv/bin/python voice_vault.py`. Stop it: `launchctl bootout gui/$(id -u)/com.chris.voice-vault`.
