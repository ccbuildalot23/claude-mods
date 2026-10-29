#!/usr/bin/env python3
"""Mission Control: one green / yellow / red light per LaBeau job.

Read-only against labeau-ops. It never posts, never writes a caption or a poem
word, and never shows a platform number (the metrics seal stands). It writes:
  - ~/.labeau/mission-control/status.json, status.html and alerts.csv
  - the same status.json into Google Drive (mission-control folder), which the
    phone page reads through the Drive connector
  - an alert email to Chris, only when something is red at an alert slot

Run: mission_control.py [--now 2026-10-22T16:05] [--no-alert] [--print]
"""
import argparse, csv, datetime as dt, glob, html, json, os, re, smtplib, subprocess, sys
from email.mime.text import MIMEText

HERE = os.path.dirname(os.path.abspath(__file__))
OPS = os.environ.get("LABEAU_OPS", os.path.expanduser("~/Developer/labeau-ops"))
STATE = os.environ.get("MC_STATE", os.path.expanduser("~/.labeau/mission-control"))
DRIVE_DIR = os.environ.get(
    "MC_DRIVE_DIR",
    os.path.expanduser("~/Library/CloudStorage/GoogleDrive-cmcald1018@gmail.com/My Drive/LaBeau-Assets/mission-control"),
)
STATUS_NAME = "labeau-mission-status.json"
MAIL_FROM = "cmcald1018@gmail.com"
MAIL_TO = ["cmcald1018@gmail.com", "admin@harmoniqsolution.com"]
KEYCHAIN_SERVICE = "labeau-mail"

# When a red light becomes an email. Each fires once per day, on the first run
# at or after the time (runs land at :05 and :35).
ALERT_SLOTS = [("06:35", "morning"), ("16:05", "prep"), ("16:35", "email")]
EMAIL_TOMORROW_AT = "16:15"     # launchd ink.labeau.mail-daily
EMAIL_LATE_AFTER = "16:30"      # tomorrow's email missing after this = red
EMAIL_TODAY_CATCHUP = "06:30"   # today's email missing after this = red
LOOKAHEAD_DAYS = 3              # tomorrow is red; the days after are yellow
EXPECTED_JOBS = ["ink.labeau.mail-daily", "ink.labeau.captions-daily", "ink.labeau.pipeline-health"]
HEALTH_JSON = os.path.join(OPS, "data", "pipeline", "health.json")
WATCHDOG_STALE_HOURS = 26       # labeau health runs at 06:50 and 21:15; a day and a bit with no run = it went quiet
PLACEHOLDERS = ("[YOUR WORDS", "[STORYTELLER WRITES", "_not written yet_", "[CAPTION", "TODO")
SKIP_STATES = {"cancelled", "canceled", "dropped", "retired", "skipped", "void", "killed"}
STILL_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif")
VISUAL_PLATFORMS = {"instagram", "tiktok", "youtube", "facebook", "pinterest"}
RANK = {"green": 0, "yellow": 1, "red": 2}


def worst(*colors):
    return max(colors, key=lambda c: RANK[c]) if colors else "green"


def hm(s):
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def card(cid, title, status, headline, details=None, fix=None):
    return {"id": cid, "title": title, "status": status, "headline": headline,
            "details": (details or [])[:6], "fix": fix or ""}


def tail(path, n=40):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readlines()[-n:]
    except OSError:
        return None


def mtime(path):
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return None


# ---------- labeau-ops access (their own helpers, so the rules stay theirs) ----------

class Ops:
    def __init__(self, root):
        self.root = root
        self.data = os.path.join(root, "data")
        sys.path.insert(0, os.path.join(root, "scripts"))
        import common  # noqa: E402  labeau-ops/scripts/common.py
        self.c = common
        try:
            from validate_release import validate
            self.validate = validate
        except Exception:
            self.validate = None
        try:
            from prepare_tomorrow import packet_for
            self.packet_for = packet_for
        except Exception:
            self.packet_for = None

    def placements(self, date):
        rows = self.c.read_csv("placements.csv")
        out = [r for r in rows if r.get("date") == date.isoformat()
               and (r.get("state") or "").strip().lower() not in SKIP_STATES]
        return out, rows

    def holds(self, date):
        """{(platform, slot): [reasons]} from the real packet builder, so any HOLD
        rule added later (video-first, privacy) shows up here unchanged."""
        if not self.packet_for:
            return None
        text = self.packet_for(date)
        holds, cur, why = {}, None, False
        for line in text.splitlines():
            m = re.match(r"^###\s+(.+?)\s+·\s+slot\s+(\d+)\s+·\s+(READY|HOLD)", line)
            if m or line.startswith("#"):
                cur = (m.group(1).strip().lower(), int(m.group(2))) if m and m.group(3) == "HOLD" else None
                why = False
                if cur:
                    holds[cur] = []
                continue
            if cur and "Held because" in line:
                why = True
            elif cur and why and re.match(r"^\s{2,}- ", line):
                holds[cur].append(line.strip()[2:])
            elif why and line.startswith("- "):
                why = False
        return holds


def post_label(pl, slot):
    return f"{pl.get('platform', '?').title()} {slot} ({pl.get('placement_id', '?')})"


def check_days(ops, now):
    """Walk tomorrow plus lookahead days once; feed the captions, assets and
    tomorrow-ready cards."""
    today = now.date()
    days = [today + dt.timedelta(days=i) for i in range(1, LOOKAHEAD_DAYS + 1)]
    out = {"captions": [], "assets": [], "holds": [], "counts": {}}
    for i, d in enumerate(days):
        color = "red" if i == 0 else "yellow"
        pls, allrows = ops.placements(d)
        out["counts"][d.isoformat()] = len(pls)
        for pl in pls:
            slot = ops.c.placement_slot(pl, allrows)
            label = post_label(pl, slot)
            cap = ops.c.read_caption(pl["date"], pl["platform"], slot)
            if not cap.strip():
                out["captions"].append((color, d, f"{label}: no caption"))
            elif any(p in cap for p in PLACEHOLDERS):
                out["captions"].append((color, d, f"{label}: caption still has a placeholder"))
            slug = (pl.get("asset_slug") or "").strip()
            visual = pl.get("platform", "").lower() in VISUAL_PLATFORMS
            files = ops.c.find_assets(slug) if slug else []
            if not slug and not visual:
                pass  # text-only post (Bluesky, Substack note): nothing to build
            elif not files:
                out["assets"].append((color, d, f"{label}: no files built (slug {pl.get('asset_slug') or 'blank'})"))
            elif (pl.get("platform", "").lower() in ("instagram", "tiktok")
                  and len(files) == 1 and files[0].lower().endswith(STILL_EXT)):
                out["assets"].append((color, d, f"{label}: single still, video-first rule holds it"))
        if i == 0:
            holds = ops.holds(d)
            if holds is None and ops.validate:
                pieces = ops.c.index_by(ops.c.read_csv("pieces.csv"), "piece_id")
                frags = ops.c.index_by(ops.c.read_csv("fragments.csv"), "fragment_id")
                holds = {}
                for pl in pls:
                    r = ops.validate(pl, pieces, frags, quiet=True) if "quiet" in ops.validate.__code__.co_varnames else ops.validate(pl, pieces, frags)
                    if r:
                        holds[(pl["platform"].lower(), ops.c.placement_slot(pl, allrows))] = r
            for (plat, slot), reasons in (holds or {}).items():
                why = re.sub(r"/\S*/", "", reasons[0])[:140] if reasons else ""
                out["holds"].append(("red", d, f"{plat.title()} {slot}: HOLD" + (f", {why}" if why else "")))
    return days, out


def summarize(cid, title, items, days, counts, ok_line, fix):
    if not items:
        return card(cid, title, "green", ok_line)
    status = worst(*[c for c, _, _ in items])
    first = [x for x in items if x[1] == days[0]]
    later = [x for x in items if x[1] != days[0]]
    if first:
        headline = f"{len(first)} for tomorrow ({days[0].strftime('%a %b %-d')})"
        if later:
            headline += f", {len(later)} later"
    else:
        headline = f"{len(later)} in the next {LOOKAHEAD_DAYS - 1} days after tomorrow"
    details = [f"{d.strftime('%a')}: {msg}" for _, d, msg in items]
    if len(details) > 6:
        details = details[:5] + [f"...and {len(details) - 5} more"]
    return card(cid, title, status, headline, details, fix)


# ---------- the cards ----------

def email_card(now):
    today, tomorrow = now.date(), now.date() + dt.timedelta(days=1)
    log_csv = os.path.join(OPS, "data", "logs", "mail_sent.csv")
    log_txt = os.path.join(OPS, "data", "logs", "mail-daily.log")
    sent = {}
    try:
        with open(log_csv, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                for d in (today, tomorrow):
                    if any(d.isoformat() in cell for cell in row):
                        sent.setdefault(d, []).append(",".join(row))
    except OSError:
        pass  # no send log yet = nothing has been sent; the checks below say which day

    def real(d):
        return [r for r in sent.get(d, []) if "test" not in r.lower()]

    colors, details = [], []
    if real(today):
        details.append(f"Today's email ({today.strftime('%a %b %-d')}) went out.")
        colors.append("green")
    elif now.time() < hm(EMAIL_TODAY_CATCHUP):
        details.append(f"Today's email not logged yet; the 6:15 am catch-up should send it.")
        colors.append("yellow")
    else:
        details.append(f"Today's email ({today.strftime('%a %b %-d')}) was never sent.")
        colors.append("red")

    if real(tomorrow):
        details.append(f"Tomorrow's email ({tomorrow.strftime('%a %b %-d')}) went out.")
        colors.append("green")
    elif now.time() < hm(EMAIL_TOMORROW_AT):
        details.append(f"Tomorrow's email is due at 4:15 pm.")
    elif now.time() < hm(EMAIL_LATE_AFTER):
        details.append("Tomorrow's email should be sending now.")
        colors.append("yellow")
    else:
        details.append(f"Tomorrow's email ({tomorrow.strftime('%a %b %-d')}) did NOT go out at 4:15.")
        colors.append("red")

    lines = tail(log_txt) or []
    errs = [l.strip() for l in lines if re.search(r"Traceback|Error|error:|failed|FAIL", l)]
    if errs:
        details.append("Log: " + errs[-1][:160])
        colors.append("yellow")
    status = worst(*colors)
    headline = {"green": "On track", "yellow": "Watch it", "red": "Not sent"}[status]
    fix = ""
    if colors and colors[0] == "red":
        fix = f"~/Developer/labeau-ops/bin/labeau mail {today.isoformat()} --send"
    elif status == "red":
        fix = f"~/Developer/labeau-ops/bin/labeau mail {tomorrow.isoformat()} --send"
    return card("email", "Daily email", status, headline, details, fix)


def captions_job_lines(now):
    """The nightly captions job: fresh log, no login errors."""
    log = os.path.join(OPS, "data", "logs", "captions-daily.log")
    m = mtime(log)
    if m is None:
        return "yellow", "Nightly captions job has no log yet."
    age_h = (now - m).total_seconds() / 3600
    lines = tail(log, 200) or []
    starts = [i for i, l in enumerate(lines) if l.startswith("=== ")]
    last = lines[starts[-1]:] if starts else lines[-30:]
    when = last[0][4:20].strip() if starts else m.strftime("%Y-%m-%d %H:%M")
    if any("Not logged in" in l for l in last):
        plist = mtime(os.path.expanduser("~/Library/LaunchAgents/ink.labeau.captions-daily.plist"))
        if plist and plist > m:
            return "yellow", (f"Last run ({when}) failed 'Not logged in' under the old cron; "
                              f"the new launchd job hasn't run yet (first run 9:40 pm).")
        return "red", f"Last nightly captions run ({when}) failed: 'Not logged in'."
    if age_h > 26:
        return "yellow", f"Nightly captions job last ran {age_h:.0f} h ago."
    return "green", f"Nightly captions job ran {age_h:.0f} h ago."


def jobs_card():
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10).stdout
    except Exception as e:
        return card("jobs", "Background jobs", "yellow", "Couldn't read launchd", [str(e)[:120]])
    seen, details, colors = {}, [], []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and "labeau" in parts[2]:
            seen[parts[2]] = parts[1]
    for job in EXPECTED_JOBS:
        if job not in seen:
            details.append(f"{job}: not installed")
            colors.append("red")
    for job, code in sorted(seen.items()):
        if code not in ("0", "-"):
            details.append(f"{job}: last run exited {code}")
            colors.append("yellow")
    status = worst(*colors)
    headline = f"{len(seen)} jobs loaded" if status == "green" else f"{len(details)} need a look"
    return card("jobs", "Background jobs", status, headline, details)


def watchdog_card(now, path=None):
    """Who watches the watchman (loop-engineering change 1, his yes Oct 29, 2026): `labeau health` does not judge
    itself, so a quiet watchdog looked like a calm night. This card reads only health.json's time, overall and
    red lines; it never re-runs the check."""
    path = path or HEALTH_JSON
    fix = "~/Developer/labeau-ops/bin/labeau health"
    try:
        with open(path, encoding="utf-8") as f:
            rep = json.load(f)
        when = dt.datetime.fromisoformat(rep["checked_at"])
    except FileNotFoundError:
        return card("watchdog", "Watchdog", "red", "Health check has never run", [path], fix)
    except Exception as e:
        return card("watchdog", "Watchdog", "red", "Health report unreadable", [f"{type(e).__name__}: {e}"[:120]], fix)
    naive = now.replace(tzinfo=None) if now.tzinfo else now
    hours = (naive - when.replace(tzinfo=None)).total_seconds() / 3600
    ran = f"Last health check {when:%a %b %d %-I:%M %p}."
    if hours > WATCHDOG_STALE_HOURS:
        return card("watchdog", "Watchdog", "red", f"Health check quiet for {int(hours)} h", [ran], fix)
    if rep.get("overall") == "RED":
        lines = [l for c in rep.get("checks", {}).values() for l in c.get("red_lines", [])]
        return card("watchdog", "Watchdog", "yellow", f"Health check found {rep.get('red', len(lines))} red",
                    lines[:5] + [ran], "labeau health (the red lines also went to email)")
    return card("watchdog", "Watchdog", "green", "Health check ran and found nothing red", [ran])


def build(now):
    cards = [email_card(now)]
    try:
        ops = Ops(OPS)
        days, found = check_days(ops, now)
        n = found["counts"].get(days[0].isoformat(), 0)
        cj_color, cj_line = captions_job_lines(now)
        cap = summarize("captions", "Captions written", found["captions"], days, found["counts"],
                        f"All {n} posts for tomorrow have captions", "Run the captions job or ask a thread to write them")
        cap["details"].append(cj_line)
        cap["status"] = worst(cap["status"], cj_color)
        cards.append(cap)
        cards.append(summarize("assets", "Assets built", found["assets"], days, found["counts"],
                               f"Every post for tomorrow has its files", "Build the Reel or carousel into 04-posts"))
        ready = summarize("tomorrow", "Tomorrow ready", found["holds"], days, found["counts"],
                          f"{n} posts, 0 holds" if n else "Nothing posts tomorrow", "labeau prepare tomorrow, then fix what it holds")
        if found["holds"]:
            ready["headline"] = f"{len(found['holds'])} HOLD of {n} posts"
        cards.append(ready)
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"[:200]
        for cid, title in (("captions", "Captions written"), ("assets", "Assets built"), ("tomorrow", "Tomorrow ready")):
            cards.append(card(cid, title, "red", "Checker couldn't read labeau-ops", [msg], "~/Developer/labeau-ops/.venv/bin/python ~/Developer/labeau-ops/scripts/mission_control.py --print --no-alert"))
    cards.append(jobs_card())
    cards.append(watchdog_card(now))
    return {
        "version": 1,
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "today": now.date().isoformat(),
        "tomorrow": (now.date() + dt.timedelta(days=1)).isoformat(),
        "overall": worst(*[c["status"] for c in cards]),
        "cards": cards,
    }


# ---------- outputs ----------

def write_outputs(status):
    os.makedirs(STATE, exist_ok=True)
    body = json.dumps(status, indent=1, ensure_ascii=False)
    with open(os.path.join(STATE, "status.json"), "w", encoding="utf-8") as f:
        f.write(body)
    with open(os.path.join(STATE, "status.html"), "w", encoding="utf-8") as f:
        f.write(render_html(status))
    try:
        os.makedirs(DRIVE_DIR, exist_ok=True)
        tmp = os.path.join(DRIVE_DIR, STATUS_NAME + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(status, ensure_ascii=False, separators=(",", ":")))
        os.replace(tmp, os.path.join(DRIVE_DIR, STATUS_NAME))
        return None
    except OSError as e:
        return f"Drive copy failed: {e}"


def render_html(s):
    dot = {"green": "#2e9e5b", "yellow": "#d9a400", "red": "#d64545"}
    rows = []
    for c in s["cards"]:
        det = "".join(f"<li>{html.escape(d)}</li>" for d in c["details"])
        fix = f"<code>{html.escape(c['fix'])}</code>" if c["fix"] and c["status"] != "green" else ""
        rows.append(f"<section><h2><span style='color:{dot[c['status']]}'>&#9679;</span> {html.escape(c['title'])}</h2>"
                    f"<p>{html.escape(c['headline'])}</p><ul>{det}</ul>{fix}</section>")
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>Mission Control</title><style>body{font:16px -apple-system,sans-serif;margin:16px;max-width:560px}"
            "section{border:1px solid #ddd;border-radius:10px;padding:8px 14px;margin:10px 0}h2{font-size:17px;margin:6px 0}"
            "code{font-size:12px;word-break:break-all}</style>"
            f"<h1>Mission Control</h1><p>Checked {html.escape(s['generated_at'])}</p>" + "".join(rows))


def alert_slot_due(now, sent_log):
    done = set()
    try:
        with open(sent_log, encoding="utf-8") as f:
            done = {tuple(r[:2]) for r in csv.reader(f) if len(r) >= 2}
    except OSError:
        pass
    for at, name in reversed(ALERT_SLOTS):
        t = hm(at)
        start = dt.datetime.combine(now.date(), t)
        if start <= now < start + dt.timedelta(hours=2):
            return name if (now.date().isoformat(), name) not in done else None
    return None


def keychain_password():
    return subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", MAIL_FROM, "-w"],
                          capture_output=True, text=True, timeout=15, check=True).stdout.strip()


def alert_text(status):
    reds = [c for c in status["cards"] if c["status"] == "red"]
    subject = f"Mission Control: {len(reds)} red ({', '.join(c['title'].lower() for c in reds)})"
    lines = [f"Checked {status['generated_at']}.", ""]
    for c in reds:
        lines.append(f"RED  {c['title']}: {c['headline']}")
        lines += [f"     - {d}" for d in c["details"]]
        if c["fix"]:
            lines.append(f"     Fix: {c['fix']}")
        lines.append("")
    yellows = [c for c in status["cards"] if c["status"] == "yellow"]
    if yellows:
        lines.append("Yellow: " + "; ".join(f"{c['title']} ({c['headline']})" for c in yellows))
    lines += ["", "Nothing was posted or changed. This is a status note from Mission Control on the Mac."]
    return subject, "\n".join(lines)


def send_alert(status):
    subject, body = alert_text(status)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, MAIL_FROM, ", ".join(MAIL_TO)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(MAIL_FROM, keychain_password())
        s.sendmail(MAIL_FROM, MAIL_TO, msg.as_string())
    return subject


def notify_mac(title, text):
    try:
        subprocess.run(["osascript", "-e", f'display notification {json.dumps(text)} with title {json.dumps(title)} sound name "Basso"'],
                       capture_output=True, timeout=10)
    except Exception:
        pass


def receipt(problems):
    """The run's receipt (plan 1.3, Oct 27, 2026): launchd runs this every half hour and it left none, so a dead
    Mission Control looked green. One ok row a day; every partial run is written. Never fatal."""
    try:
        import job_runs
    except ImportError:
        return None
    status = "partial" if problems else "ok"
    return job_runs.script_receipt("mission_control", status, errors="; ".join(problems)[:300],
                                   source_access="launchd ink.labeau.mission-control",
                                   output_path=STATE, once_a_day=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="pretend time, YYYY-MM-DDTHH:MM (tests)")
    ap.add_argument("--no-alert", action="store_true", help="never email")
    ap.add_argument("--print", action="store_true", help="print a summary")
    a = ap.parse_args()
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    status = build(now)
    drive_err = write_outputs(status)
    if drive_err:
        status["cards"][-1]["details"].append(drive_err)
        status["cards"][-1]["status"] = worst(status["cards"][-1]["status"], "yellow")
        write_outputs(status)
    log = os.path.join(STATE, "alerts.csv")
    slot = alert_slot_due(now, log)
    problems = [drive_err] if drive_err else []
    if slot and status["overall"] == "red" and not a.no_alert:
        notify_mac("LaBeau Mission Control", alert_text(status)[0])
        try:
            subj = send_alert(status)
            result = "sent"
        except Exception as e:
            subj, result = alert_text(status)[0], f"FAILED {type(e).__name__}: {e}"[:200]
            problems.append(f"alert email {result}")
        with open(log, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([now.date().isoformat(), slot, now.isoformat(timespec="minutes"), subj, result])
    if not a.now:   # a pretend time is a test or a replay, never a real run
        receipt(problems)
    if a.print:
        print(f"overall: {status['overall'].upper()}  ({status['generated_at']})")
        for c in status["cards"]:
            print(f"  {c['status'].upper():6} {c['title']}: {c['headline']}")
            for d in c["details"]:
                print(f"           - {d}")
        if drive_err:
            print("  " + drive_err)


if __name__ == "__main__":
    main()
