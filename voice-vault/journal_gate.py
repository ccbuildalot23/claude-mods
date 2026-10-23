#!/usr/bin/env python3
"""The journal gate: Chris's journal pages into the Brand Message Library, one stop for him.

Everything in the journal is fair game (his ruling, Oct 23, 2026). People's names are
the one stop. Flow:

  Sunday   Chris photographs the week's pages and drops them in ~/Voice Inbox.
  Night    `run` reads each photo on this Mac (Apple Vision, nothing leaves the Mac)
           and adds every line, word for word, to share-candidates.csv:
             pending       a plain line; clears on docket silence
             held-name     names a person; waits for Chris to pick a role (or ok it)
             held-reading  Vision was unsure of the words; waits for ok or a fix
  Monday   7 am: the docket email lists the held lines (with role options) and
           everything harvested. Chris replies only if he wants a change.
  Tuesday  7 am: pending lines from Monday's docket clear. Held lines stay held and
           come back on the next docket.

Reply commands (one per line, or separated by commas):
  strike 3 5      never share those lines
  3 b             use role option b in place of the name in line 3
  3: my coach     use your own words for the name in line 3
  ok 4            line 4 is fine as read (a name line then keeps the name)
  4 fix: words    line 4 should read exactly "words"
  lens 2          line 2 goes into the Hierophant Lens (echo 6 for a reader's words)

  journal_gate.py run              what launchd runs (2:30 am, 7 am, noon, 7 pm)
  journal_gate.py now              read new photos right away (the `harvest` alias)
  journal_gate.py docket           print the next docket without sending it
  journal_gate.py apply "strike 3" apply a command to the latest docket by hand
  journal_gate.py check            prove the gate can log in to read replies

No AI is in the loop. Logs hold counts and ids, never journal words.
"""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import hashlib
import imaplib
import json
import re
import shutil
import smtplib
import subprocess
import sys
from email.message import EmailMessage
from pathlib import Path

import share_library as sl
import voice_vault as vv

HERE = Path(__file__).resolve().parent
STATE = HERE / "state" / "gate"
MIN_CONFIDENCE = 0.5
FROM = "cmcald1018@gmail.com"
TO = "cmcald1018@gmail.com, admin@harmoniqsolution.com"
HIS_ADDRESSES = ("cmcald1018@gmail.com", "admin@harmoniqsolution.com")
DOCKET_DAY, DOCKET_HOUR = 0, 7   # Monday, 7 am
DEFAULT_ROLES = ["a friend", "someone I love", "someone close to me"]

# Capitalised words that are not people. Anything else capitalised mid-line is asked about.
NOT_NAMES = set("""
I I'm I'll I've I'd God Lord Jesus Christ Heaven LaBeau Mom Mama Mother Dad Daddy Father Grandma Grandpa
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
August September October November December Christmas Thanksgiving Easter America American OK Okay
""".split())
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def log(msg: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "gate.log").open("a") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}\n")


def config() -> dict:
    cfg = vv.load_config()
    cfg["known_names"] = vv.shared_list("private-names.txt")
    cfg["roles"] = {}
    for line in vv.shared_list("name-roles.txt"):        # "Name = my brother | my big brother"
        name, _, roles = line.partition("=")
        if roles.strip():
            cfg["roles"][name.strip().lower()] = [r.strip() for r in roles.split("|") if r.strip()]
    cfg["not_names"] = {w.lower() for w in vv.shared_list("name-ok.txt")}
    return cfg


def find_names(text: str, cfg: dict) -> list[str]:
    """Names in a line: anyone on Chris's lists, plus any capitalised word in the
    middle of a sentence that is not a known non-name. Better to ask than to miss."""
    found = []
    known = cfg["known_names"] + list(cfg["roles"])
    for name in known:
        m = re.search(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE)
        if m and m.group(0) not in found:
            found.append(m.group(0))
    words = list(WORD.finditer(text))
    for i, m in enumerate(words):
        w = re.sub(r"['’]s$", "", m.group(0))
        if i == 0 or not w[0].isupper() or w in NOT_NAMES or w.lower() in cfg["not_names"]:
            continue
        before = text[:m.start()].rstrip()
        if before.endswith((".", "!", "?", ":", '"', "“")):
            continue
        if not any(w.lower() == f.lower() for f in found):
            found.append(w)
    return found


def role_options(names: list[str], cfg: dict) -> list[str]:
    opts = []
    for n in names:
        opts += cfg["roles"].get(n.lower(), [])
    for r in DEFAULT_ROLES:
        if r not in opts:
            opts.append(r)
    return opts[:4]


def classify(text: str, confidence: float, cfg: dict) -> tuple[str, str, list[str]]:
    names = find_names(text, cfg)
    if names:
        return "held-name", ", ".join(names), role_options(names, cfg)
    if confidence < MIN_CONFIDENCE:
        return "held-reading", f"reading unsure ({confidence:.2f})", []
    return "pending", "", []


# ---------- intake ----------

def intake(cfg: dict, reader=None) -> int:
    """File each new photo in the Voice Inbox and add every line it holds."""
    import diary_ocr
    reader = reader or diary_ocr.ocr_read
    seen_path = STATE / "photos.json"
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    lib = Path(cfg["share_library"])
    rows = sl.load(lib)
    added = 0
    for photo, _ in vv.candidates(cfg, vv.IMAGE_EXT):
        digest = vv.sha256(photo)
        if digest in seen:
            continue
        when = vv.recorded_at(photo)
        pages = Path(cfg["diary_pages_dir"])
        pages.mkdir(parents=True, exist_ok=True)
        out = vv.unique(pages / f"{when.strftime('%Y-%m-%d %H%M')} Journal Page{photo.suffix.lower()}")
        shutil.move(str(photo), out)
        try:
            lines = reader(out)
        except RuntimeError as e:
            log(f"ERROR {out.name}: {e}")
            seen[digest] = {"photo": out.name, "lines": 0, "error": True}
            continue
        for text, conf in lines:
            status, flag, roles = classify(text, conf, cfg)
            sl.add(rows, text, when.date(), f"journal-page {out.name}", status, flag, roles)
            added += 1
        seen[digest] = {"photo": out.name, "lines": len(lines)}
        log(f"READ {out.name}: {len(lines)} line(s)")
    sl.save(lib, rows)
    STATE.mkdir(parents=True, exist_ok=True)
    seen_path.write_text(json.dumps(seen, indent=1))
    return added


# ---------- docket ----------

def docket_rows(rows: list[dict]) -> list[dict]:
    held = [r for r in rows if r["status"] in ("held-name", "held-reading")]
    new = [r for r in rows if r["status"] == "pending" and not r["docket"]]
    return held + new


def build_docket(rows: list[dict], day: dt.date) -> tuple[str, str, dict]:
    picked = docket_rows(rows)
    mapping = {str(i): r["id"] for i, r in enumerate(picked, 1)}
    clears = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(DOCKET_HOUR))
    lead = (f"Your journal, harvested. Everything under CLEARS goes to the brand at "
            f"{clears.strftime('%-I %p').lower()} {clears.strftime('%A')} unless you reply."
            if any(r["status"] == "pending" for r in picked) else "Your journal: these lines still wait for you.")
    out = [lead,
           "Reply only for a change:  strike 3  ·  3 b  ·  3: my coach  ·  ok 4  ·  4 fix: exact words  ·  lens 2",
           ""]
    sections = [("NAMES (held until you pick a role, or reply ok to keep the name)", "held-name"),
                ("READING UNSURE (held until you reply ok, or fix it)", "held-reading"),
                ("CLEARS (silence = yes)", "pending")]
    for title, status in sections:
        items = [(n, r) for n, r in ((n, next(r for r in picked if r["id"] == i)) for n, i in mapping.items())
                 if r["status"] == status]
        if not items:
            continue
        out.append(title)
        for n, r in items:
            out.append(f'{n}. "{r["line"]}"')
            if status == "held-name":
                letters = "  ".join(f"{chr(97 + k)}) {o}" for k, o in enumerate(r["role_options"].split(" | ")) if o)
                out.append(f"   name: {r['flag']}   {letters}")
            elif status == "held-reading":
                out.append(f"   photo: {r['source'].replace('journal-page ', '')}")
        out.append("")
    out.append("Agents use only cleared lines, word for word, with the Hierophant Lens. Nothing posts without your yes.")
    subject = f"LaBeau docket {day.isoformat()}"
    return subject, "\n".join(out), mapping


def mark_docketed(rows: list[dict], mapping: dict, day: dt.date) -> None:
    by_id = {r["id"]: r for r in rows}
    for n, i in mapping.items():
        by_id[i]["docket"], by_id[i]["docket_no"] = day.isoformat(), n


def clear_expired(rows: list[dict], now: dt.datetime) -> int:
    n = 0
    for r in rows:
        if r["status"] == "pending" and r["docket"]:
            due = dt.datetime.combine(dt.date.fromisoformat(r["docket"]) + dt.timedelta(days=1), dt.time(DOCKET_HOUR))
            if now >= due:
                r["status"], r["shared_line"] = "cleared", r["shared_line"] or r["line"]
                n += 1
    return n


# ---------- replies ----------

CMD = re.compile(r"""^\s*(?:
    (?P<verb>strike|x|ok|lens|echo)\s+(?P<nums>\d+(?:\s*(?:,|&|\band\b)?\s*\d+)*)
  | (?P<fixno>\d+)\s*fix\s*[:=-]\s*(?P<fix>.+)
  | (?P<rno>\d+)\s*[:=]\s*(?P<role>.+)
  | (?P<lno>\d+)\s*[.)-]?\s*(?P<letter>[a-d])
)\s*$""", re.IGNORECASE | re.VERBOSE)


def parse(text: str) -> list[tuple[str, str, str]]:
    """Commands from the top of a reply (quoted text below is ignored)."""
    cmds = []
    for raw in text.splitlines():
        if raw.startswith(">") or re.match(r"^\s*On .+wrote:\s*$", raw):
            break
        parts = [raw] if CMD.match(raw) else re.split(r"[;,]", raw)
        for part in parts:
            m = CMD.match(part)
            if not m:
                continue
            if m["verb"]:
                verb = "strike" if m["verb"].lower() in ("strike", "x") else m["verb"].lower()
                cmds += [(verb, n, "") for n in re.findall(r"\d+", m["nums"])]
            elif m["fixno"]:
                cmds.append(("fix", m["fixno"], m["fix"].strip().strip('"“”')))
            elif m["rno"]:
                cmds.append(("role", m["rno"], m["role"].strip().strip('"“”')))
            else:
                cmds.append(("pick", m["lno"], m["letter"].lower()))
    return cmds


def swap_names(line: str, names: list[str], role: str) -> str:
    for n in names:
        line = re.sub(r"\b" + re.escape(n) + r"(?=('s|’s)?\b)", role, line, flags=re.IGNORECASE)
    return line


def apply(rows: list[dict], mapping: dict, cmds: list[tuple[str, str, str]], cfg: dict) -> list[str]:
    by_id = {r["id"]: r for r in rows}
    done = []
    for verb, n, arg in cmds:
        r = by_id.get(mapping.get(n, ""))
        if r is None:
            done.append(f"{n}: no such line on that docket")
            continue
        names = [x.strip() for x in r["flag"].split(",")] if r["status"] == "held-name" else []
        if verb == "strike":
            r["status"], r["shared_line"] = "struck", ""
            done.append(f"{n}: struck")
        elif verb == "ok":
            r["status"], r["shared_line"] = "cleared", r["shared_line"] or r["line"]
            done.append(f'{n}: cleared as "{r["shared_line"]}"')
        elif verb in ("pick", "role"):
            if not names:
                done.append(f"{n}: has no name to replace")
                continue
            if verb == "pick":
                opts = r["role_options"].split(" | ")
                k = ord(arg) - 97
                if k >= len(opts):
                    done.append(f"{n}: there is no option {arg}")
                    continue
                arg = opts[k]
            r["shared_line"], r["status"] = swap_names(r["line"], names, arg), "cleared"
            done.append(f'{n}: cleared as "{r["shared_line"]}"')
        elif verb == "fix":
            again = find_names(arg, cfg)
            if again:
                r["shared_line"], r["status"], r["flag"] = "", "held-name", ", ".join(again)
                r["line"] = arg
                r["role_options"] = " | ".join(role_options(again, cfg))
                done.append(f"{n}: fixed, but it names {', '.join(again)}; pick a role next docket")
            else:
                r["shared_line"], r["status"] = arg, "cleared"
                done.append(f'{n}: cleared as "{arg}"')
        elif verb in ("lens", "echo"):
            text = r["shared_line"] or r["line"]
            sl.append_lens(Path(cfg["lens_file"]), verb, [text], dt.date.fromisoformat(r["written_on"]))
            r["status"] = verb
            done.append(f"{n}: added to the Lens" + (" (echo)" if verb == "echo" else ""))
    return done


def password() -> str:
    return subprocess.run(["/usr/bin/security", "find-generic-password", "-s", "labeau-mail", "-a", FROM, "-w"],
                          capture_output=True, text=True, check=True).stdout.strip()


def send(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = FROM, TO, subject
    msg.set_content(body, cte="base64")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(FROM, password())
        s.send_message(msg)


def body_text(msg) -> str:
    part = msg.get_body(preferencelist=("plain",)) if msg.is_multipart() else msg
    return part.get_content() if part else ""


def fetch_replies(since: dt.date, imap=None) -> list[tuple[str, str, str]]:
    """(message id, docket date, text) for each reply from Chris to a docket."""
    box = imap or imaplib.IMAP4_SSL("imap.gmail.com")
    if imap is None:
        box.login(FROM, password())
    # A reply Chris sends from this same Gmail lands in All Mail for sure; Inbox maybe.
    if box.select('"[Gmail]/All Mail"', readonly=True)[0] != "OK":
        box.select("INBOX", readonly=True)
    _, data = box.search(None, "SINCE", since.strftime("%d-%b-%Y"), "SUBJECT", '"LaBeau docket"')
    out = []
    for num in (data[0] or b"").split():
        _, parts = box.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(parts[0][1], policy=email.policy.default)
        sender = email.utils.parseaddr(msg["From"] or "")[1].lower()
        m = re.search(r"LaBeau docket (\d{4}-\d\d-\d\d)", msg["Subject"] or "")
        if sender in HIS_ADDRESSES and m and (msg["Subject"] or "").lower().startswith("re"):
            out.append((msg["Message-ID"] or hashlib.sha1(parts[0][1]).hexdigest(), m.group(1), body_text(msg)))
    if imap is None:
        box.logout()
    return out


def handle_replies(rows: list[dict], cfg: dict, replies: list[tuple[str, str, str]], mailer=send) -> int:
    done_path = STATE / "replies.json"
    handled = set(json.loads(done_path.read_text())) if done_path.exists() else set()
    n = 0
    for mid, day, text in replies:
        if mid in handled:
            continue
        mp = STATE / f"docket-{day}.json"
        if not mp.exists():
            continue
        result = apply(rows, json.loads(mp.read_text()), parse(text), cfg)
        handled.add(mid)
        n += 1
        log(f"REPLY docket {day}: {len(result)} change(s)")
        if result:
            mailer(f"LaBeau docket {day}: done", "\n".join(result))
    STATE.mkdir(parents=True, exist_ok=True)
    done_path.write_text(json.dumps(sorted(handled)))
    return n


# ---------- the job ----------

def run(cfg: dict, now: dt.datetime | None = None, reader=None, replies=None, mailer=send) -> dict:
    now = now or dt.datetime.now()
    added = intake(cfg, reader)
    lib = Path(cfg["share_library"])
    rows = sl.load(lib)
    report = {"added": added}
    try:
        got = replies if replies is not None else fetch_replies(now.date() - dt.timedelta(days=14))
        report["replies"] = handle_replies(rows, cfg, got, mailer)
    except Exception as e:  # mail trouble never stops the rest
        log(f"ERROR replies: {type(e).__name__}")
        report["replies"] = "error"
    report["cleared"] = clear_expired(rows, now)
    day = now.date()
    sent_flag = STATE / f"docket-{day.isoformat()}.json"
    if now.weekday() == DOCKET_DAY and now.hour >= DOCKET_HOUR and not sent_flag.exists() and docket_rows(rows):
        subject, body, mapping = build_docket(rows, day)
        mailer(subject, body)
        mark_docketed(rows, mapping, day)
        sent_flag.write_text(json.dumps(mapping))
        report["docket"] = len(mapping)
        log(f"DOCKET {day}: {len(mapping)} line(s)")
    sl.save(lib, rows)
    log("RUN " + json.dumps(report))
    (STATE / "last_run.txt").write_text(now.isoformat(timespec="seconds") + "\n")
    return report


def main(argv: list[str]) -> int:
    global STATE
    cmd = argv[1] if len(argv) > 1 else "run"
    cfg = config()
    if cmd == "run":
        print(run(cfg))
    elif cmd == "now":
        n = intake(cfg)
        rows = sl.load(Path(cfg["share_library"]))
        held = sum(r["status"].startswith("held") for r in rows)
        print(f"Read {n} new line(s). {held} line(s) wait for you on Monday's docket.")
    elif cmd == "docket":
        print("\n".join(build_docket(sl.load(Path(cfg["share_library"])), dt.date.today())[:2]))
    elif cmd == "selftest":
        import tempfile
        root = Path(tempfile.mkdtemp(prefix="gate-selftest-"))
        STATE = root / "state"
        cfg.update({"inbox": [str(root / "inbox")], "watch_readonly": [], "diary_pages_dir": str(root / "pages"),
                    "share_library": str(root / "share-candidates.csv")})
        (root / "inbox").mkdir()
        shutil.copy(HERE / "templates/demo-page.png", root / "inbox" / "demo.png")
        old = dt.datetime.now().timestamp() - 60
        import os
        os.utime(root / "inbox" / "demo.png", (old, old))
        n = intake(cfg)
        rows = sl.load(Path(cfg["share_library"]))
        ok = any("river" in r["line"] for r in rows)
        print(f"Self-test: read {n} line(s) from the made-up page; docket would list {len(docket_rows(rows))}.")
        shutil.rmtree(root, ignore_errors=True)
        if not ok:
            print("Self-test FAILED: the reader did not find the demo words.")
            return 1
        print("Self-test OK.")
    elif cmd == "check":
        box = imaplib.IMAP4_SSL("imap.gmail.com")
        box.login(FROM, password())
        box.select("INBOX", readonly=True)
        box.logout()
        print("Mail OK: the gate can read docket replies.")
    elif cmd == "apply" and len(argv) > 2:
        dockets = sorted(STATE.glob("docket-*.json"))
        if not dockets:
            print("No docket has gone out yet.")
            return 1
        lib = Path(cfg["share_library"])
        rows = sl.load(lib)
        print("\n".join(apply(rows, json.loads(dockets[-1].read_text()), parse(" ".join(argv[2:])), cfg)) or "Nothing understood.")
        sl.save(lib, rows)
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
