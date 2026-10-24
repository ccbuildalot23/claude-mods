# Bridge digest (Grok bridge into the vault)

Every night at 21:45, after Grok's sweep, this writes two notes into the vault under `Second Brain/Meta/Bridge/`:

| Note | What it holds |
|---|---|
| `Bridge Digest - YYYY-MM-DD.md` | The day's snapshot: each agent's health and last check-in, every `to-` inbox by status, messages written that day, what is flagged for Chris, and anything unacked over 7 days. Front matter carries the counts (`open`, `new`, `needs_chris`, `stale`) so Dataview can chart them. |
| `Agents - Bridge Roster (Living).md` | Who is on the bridge and whether each one is checking in, with a Dataview table of the last 14 digests. Rewritten every night. |

It is a small background job (launchd), not a Claude Code plugin, and it talks to no AI and no network.

## What it reads, and what it never writes
- It reads only the front matter of each message in the bridge's `to-*` folders, the Status log line on old files that have no front matter, and `status/*.json`.
- Every value it writes is a count, a date, a message id, or a word from a fixed list:
  - topics: bridge, harness, packet, calendar, security, other;
  - types and statuses from the protocol;
  - agent names.
- Anything else shows as `other`. So these never reach the vault:
  - message text;
  - file-name slugs;
  - topic words outside the list;
  - a `needs_chris` reason (it shows only yes or no);
  - a heartbeat's free-text note.
- It writes those two files and nothing else. It never deletes or moves a file, and it refuses to write outside `Second Brain/Meta/Bridge/`.
- Each digest says "No Second Brain update earned", as the Standard Block asks of a job that only counts. The day count comes from a Meta note's own `created` and `day`, so no date is stored here.

## Install (on the Mac)
```
bash ~/Developer/claude-mods/bridge-digest/install.sh
```
- It runs the tests and installs `com.chris.bridge-digest` inside a tiny `BridgeDigest.app`, so only that app needs the vault.
- It then runs once. If macOS blocks `~/Documents`, it opens Full Disk Access for you.
- To preview without writing: `python3 bridge_digest.py --print`.
- Undo: `bash bridge-digest/uninstall.sh`.

## Status Board
To show the bridge on a Status Board note, paste this:
````
```dataview
TABLE open AS "Open", new AS "New", needs_chris AS "Needs Chris", stale AS "Over 7 days"
FROM "Second Brain/Meta/Bridge"
WHERE type = "bridge-digest"
SORT created DESC
LIMIT 1
```
````

## Config
Optional `config.json` beside the script, which is never committed. It can set:
- `bridge`: default `~/Developer/grok-bridge`;
- `vault`: default `~/Documents/Documents - Christopher’s MacBook Air/Desktop`, with a curly apostrophe;
- `out`: default `Second Brain/Meta/Bridge`;
- `day_one`.

## Tests
`python3 -m unittest discover -s tests`
