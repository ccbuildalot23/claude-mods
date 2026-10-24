# Chris's Claude Code mods (chris-mods)

Built 2026-10-21 from the bridge mods list and the Oct 21 mods lecture. A local plugin marketplace: Claude Code reads each mod straight from this folder, so an edit here goes live with `/reload-plugins`. Needs Claude Code 2.1.287 or newer (`claude update`).

## Install (Terminal, once)
```
cd ~/Developer/claude-mods && ./install.sh
```
Then restart Claude Code (or run `/reload-plugins` in an open session). Uninstall one: `claude plugin uninstall <name>@chris-mods`.

## The mods
| Mod | Command | Uses AI? | What it does |
|---|---|---|---|
| blast-radius | (always on) | no | Pauses rm, rmdir, find -delete, git clean, git reset --hard, git checkout ., force push, rsync --delete, disk erase; shows the files it would hit; runs only on Proceed. A plain delete of scratch paths alone (/tmp, /private/tmp, /var/folders) runs without asking. Hard-blocks AI writes into poems/, line-bank/, public-copy/ and Claude settings files, through Write/Edit and through the shell (redirects, cp, mv, sed -i, scripts), in any letter case and through symlinks. |
| screen-share | /screenshare, /screenshare add NAME | no | Gray bars over names, emails, phones, money, keys; hides tool details. Names list stays on this Mac. |
| switchboard | /mods | no | One panel to switch each mod on/off mid-chat, and block any other plugin from loading next time. blast-radius is locked on. |
| crew | /crew, /crew on/off | no | Every subagent gets its own character, name and color (🦊 Ember, 🦉 Sage, 🐙 Inky...). A colored row per working agent above the prompt shows what it is doing right now ("Reading README.md", "Run unit tests") and its progress: a bar from its own to-do list, or its step count, plus elapsed time. /crew opens the full roster with each agent's task, checklist, tokens and API-equivalent cost (taken over from helper-desk, retired Oct 24). |
| cache-clock | /keepwarm, /cacheclock | only /keepwarm pings | Status line: today's AI window or quiet hours (from `config/clock.json`), your 5-hour and weekly limits, and the countdown until the prompt cache goes cold; warns before a cold, expensive message; /keepwarm pings for up to 2 h. |
| handoff | /handoff, /wrap | yes, one call | /handoff writes a full prompt for a fresh chat; /wrap closes a session with Done, Still open and one question for you. Both saved to ~/Developer/claude-mods/handoffs/. |
| reflect | /reflect on/off | no | Spots rules you give ("never", "always", "from now on") and saves the ones you pick to rules-inbox.md. Give the same rule twice and it offers to promote it into ~/.claude/CLAUDE.md. |
| chat-inventory | /inventory | no | Cowork-style "In this chat" panel: goal, connectors, skills, links and a file tree (read / editing / changed). Covers the File Tree mod too. |
| replay-theater | /replay | no | Steps through each file edit from the last reply as a diff. Read-only. |
| brain-dump | /braindump on/off/status, /braindump save TEXT, /dumps | yes, one small call per Tidy | On by default. Holds long spoken rambles (pasted code and logs pass through) with Tidy it / Send as is / Save for later; Tidy adds a to-do list and offers Edit first. A prompt starting `Private:` (or Vault:, Journal:, Recovery:) is always held and never reaches Claude: Send to vault drops it in ~/Voice Inbox for the vault router. `Line:` dumps go to the line bank inbox word for word. /dumps lists saved thoughts beside the chat. Phone app: https://claude.ai/artifact/9xMve7HGWkuoSbFmXkjNw8 (source in brain-dump/app/). |
| heads-up | /headsup on/off | yes, small, long replies only | The "you should know" mod: pops up costs, irreversible steps, deadlines, asks for your yes. |
| skins | /skin labeau, noir, tokyo, off | no | Icons and colors per tool call, themed spinner words. |
| browser-peek | /peek URL | no | The terminal-browser mod: headless Chrome screenshot of a page in a side panel (picture shows in the terminal app; desktop shows the saved file). In cloud sessions it uses the bundled Chromium. |
| privacy-preflight | /preflight, /preflight allow ID | no | Locked on. Checks writes headed somewhere shared (grok-bridge, labeau-site, public-copy, Airtable, Notion, Drive, Blotato, Gmail, Slack, Calendar) and blocks private names from `config/private-names.txt`, private-life words, keys, bridge stamps later than now, and bridge files that break PROTOCOL names or statuses. Only you can allow one through: typed at a terminal, or confirmed in the question dialog from the desktop app. |
| outbox | /outbox, /outbox release ID | no | Locked on. Holds sends, replies, posts, comments, invites, shares, deploys, git push and asset approvals until you say yes; drafts pass. When you are watching (terminal or desktop app) it asks Send once / Keep it held on the spot; in a -p or scheduled run it holds for /outbox release, which the desktop app confirms in the dialog. Records in outbox-held/. |
| action-log | /log | no | Locked on. One line per tool call (every session, scheduled runs too) in logs/actions-DATE.log, written before the call runs; no log, no run. Keys masked. |
| bridge-inbox | /bridge-inbox, /bridge-inbox auto on/off | start of session: no; summaries: yes, small, per new message | At each session start on the Mac: acks new grok-bridge/to-claude messages, writes status/claude.json, updates Claude Code's row in the Airtable Agent Heartbeats table, and flushes status/airtable-pending.jsonl (no AI; does nothing where the bridge folder is missing). /bridge-inbox gives a three-line summary of each message, ★ on anything that needs your yes; ack and archive follow the protocol (archive from the desktop app is confirmed in the dialog). Never acts on a message. |
| needs-you | /needsyou on/off | no | Desktop ping when a long turn finishes or Claude waits on you. Quiet hours hold them and send one roundup after. Terminal only: the desktop app sends its own notifications, so here it stays quiet. |
| lightweek | /lightweek [days], /lightweek off | no | Tells every session to keep to essentials for 7 days (or the days you give); a quiet line shows it's on. |

All 13 mods named in the Oct 21 lecture are covered (File Tree lives inside chat-inventory). crew was added Oct 22. The Oct 22 shortlist added privacy-preflight, outbox, action-log, bridge-inbox, needs-you and lightweek, and grew cache-clock, handoff and reflect.

Your private settings live in `config/` and never reach git: `private-names.txt` and `private-words.txt` (one per line, for privacy-preflight), `lightweek.json`, `grid-pins.json`. `config/clock.json` (AI windows and quiet hours) is shared by cache-clock and needs-you.

## In the Claude Code desktop app

Checked Oct 24, 2026 against the mod engine's surface rules. Run `./install.sh` in Terminal once; the desktop app's Code tab then loads the same user-scope mods (`/plugin` itself does not run there, so install from Terminal or the app's + menu, Plugins).

- Works the same: panes (`/mods`, `/crew`, `/inventory`, `/replay`, `/dumps`, `/peek`), the rows above the prompt, the status line, toasts, and every yes/no dialog.
- Changed for the app: the app's prompts are not stamped "typed at the terminal", so outbox, privacy-preflight and bridge-inbox take your yes from the question dialog instead (the model cannot answer it), and brain-dump's `Private:` guard covers prompts typed in the app.
- Terminal only, harmless in the app: skins' spinner words, screen-share's masking of slash-command output, needs-you's pings (the app notifies on its own), and the clipboard buttons (handoff says where the text is when the copy can't land).

## Apps

Five one-page apps that open in your browser. They read only, send nothing, and write their pages to `apps-out/` (never committed, so unpublished lines stay on this Mac).

```
cd ~/Developer/claude-mods/apps && ./open.sh line-bank
```

| App | Open with | What it does |
|---|---|---|
| Line-bank librarian | `./open.sh line-bank` | Every fragment line with its theme, image tags, which centos and pieces use it, and posted vs. planned counts. Search, filter "never used", copy. Read-only: the pen rule holds. |
| Grid preview | `./open.sh grid-preview` | The next 12 Instagram posts plus the last 9, laid out as the profile grid at 3:4, from placements.csv and the 04-posts files. Optional pins in `config/grid-pins.json`. |
| Keep-or-drop board | `./open.sh keep-or-drop` | Every routine, mod and skill with its last real output (job receipts, not a status). Mark Keep or Drop; it prints the exact Terminal lines to retire the drops (skills are moved aside, not deleted). |
| Reel review board | `./open.sh reel-review` | Load a Reel, drop timed notes as you watch, save a fix list. Notes stay in the browser. |
| Brand-deal tracker | `./open.sh brand-deals` | Idea → Researching → Warm intro → In talks → Agreed or Passed, with notes and CSV export. Stays in the browser; nothing is sent. |

Not a plugin, but living here too: **voice-vault/** (voice memos and text dumps transcribed on the Mac and filed to the line bank or the Recovery vault). See `voice-vault/README.md`.

Also not a plugin: **bridge-digest/**, a nightly launchd job (no AI) that writes a Bridge Digest and a Bridge Roster from the Grok bridge's front matter and heartbeats into the vault's `Second Brain/Meta/Bridge/`. See `bridge-digest/README.md`.

Also here: **bridge-connect/** (a small MCP server so ChatGPT and Perplexity can send dated briefs to Grok or Claude Code through the grok-bridge and check receipts, scoped to four folders of their own, with the privacy check both ways). See `bridge-connect/README.md`.

## Tests
Each mod has engine tests under `<mod>/tests/`. Run one with `claude plugin test <mod>`, or all with:
```
for m in */; do [ -d "$m/tests" ] && claude plugin test "$m"; done
```

## Rules these follow
Pen rule (no AI writes in poems), nothing sent/posted/bought, no secrets or private-life detail written anywhere shared. Handoffs and the rules inbox live only in this folder on the Mac.
