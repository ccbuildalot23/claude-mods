#!/usr/bin/env python3
"""Nightly Grok-bridge digest into the Obsidian vault (Chris's go, Oct 24, 2026: step 3 of the bridge plan).

Reads only what the bridge keeps as machine state: the front matter of each message in its to-* folders and the
status/*.json heartbeats. Never a message body, a file-name slug, a heartbeat's free-text note, or a needs_chris
reason. Every value it writes comes from a fixed list (topics, types, agents, statuses) or is a count, a date or a
message id, so nothing private can ride into the vault through it.

Writes two notes under Second Brain/Meta/Bridge/ and nothing else:
  Bridge Digest - YYYY-MM-DD.md       the day's snapshot (rewritten if run twice the same day)
  Agents - Bridge Roster (Living).md  who is alive, and a Dataview table of the last two weeks of digests
It never deletes or moves a file. No AI, no network, standard library only.

  bridge_digest.py              write today's digest and the roster
  bridge_digest.py --print      show what would be written, write nothing
  bridge_digest.py --date D     as of day D (YYYY-MM-DD)
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = {
    "bridge": "~/Developer/grok-bridge",
    # The folder name has a curly apostrophe; the straight one does not exist on this Mac.
    "vault": "~/Documents/Documents - Christopher’s MacBook Air/Desktop",
    "out": "Second Brain/Meta/Bridge",
    "day_one": "",  # optional YYYY-MM-DD; otherwise inferred from a Meta note's created/day pair
}

SAFE_TOPICS = ("bridge", "harness", "packet", "calendar", "security", "other")
SAFE_TYPES = ("request", "reply", "fyi", "alert", "packet", "ack", "note", "update")
STATUSES = ("new", "acked", "claimed", "blocked", "done", "rejected")
AGENTS = {"claude": "Claude Code", "grok": "Grok Bot", "hermes": "Hermes", "muse": "Muse",
          "chatgpt": "ChatGPT", "perplexity": "Perplexity", "chris": "Chris"}
HEARTBEATS = (("claude", "Claude Code"), ("grok", "Grok Bot"), ("hermes", "Hermes"), ("muse", "Muse"),
              ("chatgpt", "ChatGPT"), ("perplexity", "Perplexity"))
AIRTABLE_STATES = ("ok", "pending", "error", "not connected")
ID_RE = re.compile(r"^[A-Z]2[A-Z]-\d{4}-\d{2}-\d{2}-\d{3}$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
ET_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})")


def load_config(path=None):
    cfg = dict(DEFAULTS)
    path = path or os.path.join(HERE, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    for k in ("bridge", "vault"):
        cfg[k] = os.path.expanduser(cfg[k])
    return cfg


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    for line in (m.group(1) if m else "").splitlines():
        k, sep, v = line.partition(":")
        if sep and re.fullmatch(r"[a-z_]+", k.strip()):
            out[k.strip()] = re.sub(r"\s+#.*$", "", v).strip()
    return out


def pick(value, allowed, fallback="other"):
    v = (value or "").strip().lower()
    return v if v in allowed else fallback


LOG_RE = re.compile(r"^- [^\n|]*\|\s*([a-z]+):", re.M)


def message(fm, folder, name="", text=""):
    """One message as safe fields only."""
    mid = fm.get("id", "") or name[:18]
    if not fm.get("status"):
        # v1-style files carry no front matter; their status is the last Status log line's.
        logged = LOG_RE.findall(text)
        if logged:
            fm = dict(fm, status=logged[-1])
    sender = fm.get("from", "").lower()
    to = folder[3:]  # v2.1: the folder follows the recipient
    created = DATE_RE.search(fm.get("created_et", "") or mid)
    return {
        "id": mid if ID_RE.match(mid) else "(no id)",
        "from": AGENTS.get(sender, "other"),
        "to": AGENTS.get(to, "other"),
        "type": pick(fm.get("type"), SAFE_TYPES),
        "topic": pick(fm.get("topic"), SAFE_TOPICS),
        "status": pick(fm.get("status") or "new", STATUSES, "new"),
        "needs_chris": fm.get("needs_chris", "no").lower().startswith("yes"),
        "created": created.group(0) if created else "",
        "folder": folder,
    }


def read_messages(bridge):
    out = []
    for folder in sorted(os.listdir(bridge)):
        path = os.path.join(bridge, folder)
        if not folder.startswith("to-") or not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            if not name.endswith(".md") or name.startswith("MOVED-"):
                continue
            with open(os.path.join(path, name), encoding="utf-8", errors="replace") as f:
                text = f.read()
            out.append(message(front_matter(text), folder, name, text))
    return out


def et_datetime(s):
    m = ET_RE.match(s or "")
    return dt.datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M") if m else None


def health(seen, now, open_count):
    if seen is None:
        return "No heartbeat", ""
    quiet = (now - seen).days
    if quiet > 7:
        return "Stale", quiet
    return ("Watch" if quiet > 2 or open_count > 3 else "OK"), quiet


def read_heartbeats(bridge, messages, now):
    rows = []
    for stem, name in HEARTBEATS:
        path = os.path.join(bridge, "status", f"{stem}.json")
        beat = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    beat = json.load(f)
            except (OSError, ValueError):
                beat = {}
        open_count = sum(1 for m in messages if m["to"] == name and m["status"] == "new")
        seen = et_datetime(str(beat.get("last_session_et", "")))
        state, quiet = health(seen, now, open_count)
        rows.append({
            "agent": name,
            "last_seen": seen.strftime("%Y-%m-%d %H:%M ET") if seen else "none",
            "days_quiet": quiet,
            "health": state,
            "open": open_count,
            "airtable": pick(str(beat.get("airtable", "")), AIRTABLE_STATES, "unknown") if beat else "unknown",
        })
    return rows


def day_one(cfg):
    """Day 1 of the vault's day count: config, else the newest Meta note that carries both created and day."""
    if DATE_RE.fullmatch(cfg.get("day_one") or ""):
        return dt.date.fromisoformat(cfg["day_one"])
    meta = os.path.join(cfg["vault"], "Second Brain", "Meta")
    best = None
    if os.path.isdir(meta):
        for name in os.listdir(meta):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(meta, name), encoding="utf-8", errors="replace") as f:
                fm = front_matter(f.read(4096))
            if DATE_RE.fullmatch(fm.get("created", "")) and fm.get("day", "").isdigit():
                created = dt.date.fromisoformat(fm["created"])
                if best is None or created > best[0]:
                    best = (created, int(fm["day"]))
    return best[0] - dt.timedelta(days=best[1] - 1) if best else None


def table(head, rows):
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def build(cfg, today, now):
    messages = read_messages(cfg["bridge"])
    beats = read_heartbeats(cfg["bridge"], messages, now)
    first = day_one(cfg)
    day = (today - first).days + 1 if first else None
    iso = today.isoformat()
    week_ago = (today - dt.timedelta(days=7)).isoformat()
    open_msgs = [m for m in messages if m["status"] in ("new", "acked", "claimed", "blocked")]
    new = [m for m in messages if m["status"] == "new"]
    stale = [m for m in new if m["created"] and m["created"] < week_ago]
    waiting = [m for m in open_msgs if m["needs_chris"]]
    moved = [m for m in messages if m["created"] == iso]
    pretty = today.strftime("%A, %B %-d, %Y")
    day_line = f", Day {day}" if day else ""
    day_fm = f"day: {day}\n" if day else ""
    roster = "[[Agents - Bridge Roster (Living)]]"
    hubs = "[[Relational Context Bridge - Obsidian and Airtable]] | [[Connector Operating Rhythm (Living)]]"

    folders = sorted({m["folder"] for m in messages})
    inbox_rows = [[f"`{f}/`"] + [sum(1 for m in messages if m["folder"] == f and m["status"] == s) for s in STATUSES]
                  for f in folders]
    msg_row = lambda m: [m["id"], f"{m['from']} → {m['to']}", m["type"], m["topic"], m["status"], "yes" if m["needs_chris"] else "no"]
    beat_rows = [[b["agent"], b["health"], b["last_seen"], b["days_quiet"], b["open"], b["airtable"]] for b in beats]
    beat_head = ["Agent", "Health", "Last seen", "Days quiet", "New to it", "Airtable"]

    digest = f"""---
type: bridge-digest
status: snapshot
created: {iso}
{day_fm}open: {len(open_msgs)}
new: {len(new)}
needs_chris: {len(waiting)}
stale: {len(stale)}
privacy: restricted
written_by: bridge-digest (launchd, no AI)
tags: [bridge, agents, digest, machine-written]
---

# Bridge Digest, {pretty}

**{pretty}{day_line}, {now.strftime('%H:%M')} ET.** A machine count of the Grok bridge: who checked in, what moved, what waits on Chris. Built from message front matter and heartbeats only, never message text. Hub: {roster}. Siblings: {hubs}.

## Agents
{table(beat_head, beat_rows)}

## Inboxes
{table(["Folder"] + list(STATUSES), inbox_rows) if inbox_rows else "No to- folders found."}

## Moved today
{table(["Message", "From → to", "Type", "Topic", "Status", "Needs Chris"], [msg_row(m) for m in moved]) if moved else "Nothing new was written today."}

## Waiting on Chris
{", ".join(m["id"] for m in waiting) if waiting else "Nothing open is flagged needs_chris."} These go in his Saturday packet; no ping before then.

## Unacked over 7 days
{", ".join(m["id"] for m in stale) if stale else "None."}{" Each is a glitch by the protocol; whoever notices logs it." if stale else ""}

## Second Brain
No Second Brain update earned: this is a count of agent traffic, not his experience. Anything worth folding in goes through the weekly pass.
"""

    roster_note = f"""---
type: roster
status: living
updated: {iso}
{day_fm}privacy: restricted
written_by: bridge-digest (launchd, no AI)
tags: [bridge, agents, roster, living-doc, machine-written]
---

# Agents, the Bridge Roster

**Updated {pretty}{day_line}, {now.strftime('%H:%M')} ET, by the nightly bridge digest.** Who is on the Grok bridge and whether each one is checking in. This note is rewritten every night; notes about an agent belong in its own room. Siblings: {hubs}.

{table(beat_head, beat_rows)}

Health: OK; Watch when quiet over 2 days or more than 3 new messages wait; Stale when quiet over 7 days; No heartbeat when the agent writes no status file (Muse reaches the bridge through Airtable only). The same rule drives the Agent Heartbeats table in Airtable.

## The last two weeks
```dataview
TABLE open AS "Open", new AS "New", needs_chris AS "Needs Chris", stale AS "Over 7 days"
FROM "{cfg['out']}"
WHERE type = "bridge-digest"
SORT created DESC
LIMIT 14
```
"""
    return {f"Bridge Digest - {iso}.md": digest, "Agents - Bridge Roster (Living).md": roster_note}


def write(cfg, notes):
    out = os.path.realpath(os.path.join(cfg["vault"], cfg["out"]))
    if not os.path.isdir(cfg["vault"]):
        raise SystemExit(f"vault not found: {cfg['vault']}")
    os.makedirs(out, exist_ok=True)
    written = []
    for name, text in notes.items():
        path = os.path.realpath(os.path.join(out, name))
        if os.path.dirname(path) != out:
            raise SystemExit(f"refusing to write outside {out}: {name}")
        tmp = f"{path}.tmp-bridge-digest"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        written.append(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description="Nightly Grok-bridge digest into the vault (no AI).")
    ap.add_argument("--date", help="as of YYYY-MM-DD (default today)")
    ap.add_argument("--print", action="store_true", help="show the notes, write nothing")
    ap.add_argument("--config", help="config.json path")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    now = dt.datetime.now().replace(second=0, microsecond=0)
    today = dt.date.fromisoformat(a.date) if a.date else now.date()
    if a.date:
        now = dt.datetime.combine(today, now.time())
    if not os.path.isdir(cfg["bridge"]):
        print(f"bridge not found: {cfg['bridge']}", file=sys.stderr)
        return 1
    notes = build(cfg, today, now)
    if a.print:
        for name, text in notes.items():
            print(f"===== {name}\n{text}")
        return 0
    for path in write(cfg, notes):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
