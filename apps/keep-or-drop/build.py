#!/usr/bin/env python3
"""Keep-or-drop board for the Nov 1 review day: every routine, mod and skill set, with its last real output.

Reads labeau-ops data/harness_map.csv (what exists), data/job_runs.csv (receipts: judge a job by its
output, never its status, LESSONS Oct 20), the Claude app's scheduled-tasks file if it can find one, and
this repo's marketplace.json. Writes ~/Developer/claude-mods/apps-out/keep-or-drop.html, where you mark
Keep or Drop and get the exact steps to retire the drops. It changes nothing itself. Local only.
"""
import datetime as dt, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402


def key(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_").removeprefix("task_").removeprefix("labeau_")


def receipts():
    last = {}
    for r in common.read_csv("job_runs.csv"):
        k = key(r.get("job", ""))
        when = r.get("completed_at") or r.get("started_at") or ""
        if r.get("status") == "ok" and when > last.get(k, {}).get("when", ""):
            last[k] = {"when": when, "output": r.get("output_path", ""), "changed": r.get("items_changed", "")}
    return last


def app_tasks():
    """Last run per Claude desktop scheduled task, from the app's own file, if this Mac has one we can read."""
    found = {}
    roots = glob.glob(os.path.join(common.HOME, "Library", "Application Support", "Claude*"))
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "scheduled-tasks.json"), recursive=True)[:3]:
            try:
                data = json.load(open(path))
            except (OSError, ValueError):
                continue
            items = data if isinstance(data, list) else data.get("tasks", list(data.values()) if isinstance(data, dict) else [])
            for t in items if isinstance(items, list) else []:
                if not isinstance(t, dict):
                    continue
                name = t.get("taskId") or t.get("id") or t.get("name") or ""
                found[key(str(name))] = {"lastRun": str(t.get("lastRunAt") or t.get("lastRun") or ""), "enabled": t.get("enabled", t.get("isEnabled"))}
    return found


def how_to_stop(row):
    loc = row.get("location", "")
    name = row.get("name", "")
    m = re.search(r"launchd\s+(ink\.labeau\.[\w.-]+)", loc)
    if m:
        return {"cmd": f"launchctl bootout gui/$(id -u)/{m.group(1)}"}
    if "crontab" in loc:
        return {"hand": f"Run crontab -e and delete the line for {name} ({loc.split('crontab', 1)[1].strip()})."}
    if "scheduled-tasks" in loc:
        return {"hand": f"Claude app, Code tab, Scheduled: turn off {name}."}
    return {"hand": f"Retire {name} by hand ({loc})."}


def main():
    harness = common.read_csv("harness_map.csv")
    if not harness:
        sys.exit(f"No harness_map.csv under {common.OPS}/data.")
    got, tasks = receipts(), app_tasks()
    items = []
    for r in harness:
        if r.get("kind") != "routine":
            continue
        k = key(r.get("name", ""))
        rec = got.get(k) or next((v for kk, v in got.items() if kk and (kk in k or k in kk)), None)
        task = tasks.get(k) or tasks.get(key(r.get("part_id", "").split(":")[-1]))
        items.append({
            "group": "Routines",
            "id": r.get("part_id", ""),
            "name": r.get("name", ""),
            "where": r.get("location", ""),
            "lastOutput": (rec or {}).get("when", ""),
            "output": (rec or {}).get("output", ""),
            "lastRun": (task or {}).get("lastRun", ""),
            "note": (r.get("notes", "") or "")[:220],
            **how_to_stop(r),
        })
    try:
        market = json.load(open(os.path.join(common.MODS, ".claude-plugin", "marketplace.json")))
        for p in market.get("plugins", []):
            locked = p["name"] in ("blast-radius", "privacy-preflight", "switchboard")
            items.append({"group": "Mods", "id": p["name"], "name": p["name"], "where": "chris-mods", "note": p.get("description", "")[:220],
                          "locked": locked, "cmd": "" if locked else f"claude plugin disable {p['name']}@chris-mods"})
    except (OSError, ValueError, KeyError):
        pass
    # Skills one row each (the page folds this group shut). A drop under ~/.claude/skills is moved aside, not deleted.
    for r in harness:
        if r.get("kind") != "skill":
            continue
        name, loc = r.get("name", ""), r.get("location", "")
        item = {"group": "Skills", "id": f"skill:{name}", "name": name, "where": loc, "note": (r.get("notes", "") or "")[:160]}
        if loc.rstrip("/").startswith("~/.claude/skills/"):
            item["cmd"] = f"mkdir -p ~/.claude/skills-retired && mv {loc.rstrip('/')} ~/.claude/skills-retired/"
        else:
            item["hand"] = f"Retire the {name} skill by hand ({loc})."
        items.append(item)
    data = {"built": dt.datetime.now().strftime("%a %b %d, %I:%M %p"), "today": dt.date.today().isoformat(), "items": items, "appTasksFound": len(tasks)}
    path = common.write_page("keep-or-drop", data)
    print(f"Keep-or-drop: {sum(1 for i in items if i['group'] == 'Routines')} routines, {sum(1 for i in items if i['group'] == 'Mods')} mods, {sum(1 for i in items if i['group'] == 'Skills')} skills. Open {path}")


if __name__ == "__main__":
    main()
