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
| blast-radius | (always on) | no | Pauses rm, rmdir, find -delete, git clean, git reset --hard, git checkout ., force push, rsync --delete, disk erase; shows the files it would hit; runs only on Proceed. Hard-blocks AI writes into poems/, line-bank/, public-copy/ and Claude settings files, through Write/Edit and through the shell (redirects, cp, mv, sed -i, scripts), in any letter case and through symlinks. |
| screen-share | /screenshare, /screenshare add NAME | no | Gray bars over names, emails, phones, money, keys; hides tool details. Names list stays on this Mac. |
| switchboard | /mods | no | One panel to switch each mod on/off mid-chat, and block any other plugin from loading next time. blast-radius is locked on. |
| helper-desk | /helperdesk | no | Purple progress bar above the prompt; panel of subagents with time, tokens, API-equivalent cost. |
| cache-clock | /keepwarm, /cacheclock | only /keepwarm pings | Countdown until the prompt cache goes cold (60 min on the subscription); warns before a cold, expensive message; /keepwarm pings for up to 2 h. |
| handoff | /handoff | yes, one call | Writes a full handoff prompt for a fresh chat to ~/Developer/claude-mods/handoffs/; offers itself past 250k tokens or when cold. |
| reflect | /reflect on/off | no | Spots rules you give ("never", "always", "from now on") and saves the ones you pick to rules-inbox.md. You promote keepers into CLAUDE.md by hand. |
| chat-inventory | /inventory | no | Cowork-style "In this chat" panel: goal, connectors, skills, links and a file tree (read / editing / changed). Covers the File Tree mod too. |
| replay-theater | /replay | no | Steps through each file edit from the last reply as a diff. Read-only. |
| brain-dump | /braindump on | yes, one small call | Off by default. Holds long voice dumps and offers a tidy prompt; poem lines are kept verbatim. |
| heads-up | /headsup on/off | yes, small, long replies only | The "you should know" mod: pops up costs, irreversible steps, deadlines, asks for your yes. |
| skins | /skin labeau, noir, tokyo, off | no | Icons and colors per tool call, themed spinner words. |
| browser-peek | /peek URL | no | The terminal-browser mod: headless Chrome screenshot of a page in a side panel (picture shows in the terminal app; desktop shows the saved file). In cloud sessions it uses the bundled Chromium. |

All 13 mods named in the Oct 21 lecture are covered (File Tree lives inside chat-inventory).

## Tests
Each mod has engine tests under `<mod>/tests/`. Run one with `claude plugin test <mod>`, or all with:
```
for m in */; do [ -d "$m/tests" ] && claude plugin test "$m"; done
```

## Rules these follow
Pen rule (no AI writes in poems), nothing sent/posted/bought, no secrets or private-life detail written anywhere shared. Handoffs and the rules inbox live only in this folder on the Mac.
