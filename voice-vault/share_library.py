"""The Brand Message Library (share-candidates.csv) and the Hierophant Lens.

Everything in Chris's journal is fair game for the brand (his ruling, Oct 23, 2026).
Each line is kept exactly as read. Only Chris changes what is shared: on the
Monday docket he can strike a line, pick a role in place of a person's name, or
fix a misread. Silence clears a plain line; a line with a name or an unsure
reading waits for him. Agents read rows with status "cleared" and quote
`shared_line` from cleared.csv; they never write here (blast-radius guards the folder).
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import tempfile
from pathlib import Path

BRANDS = ("labeau", "chris", "both")
LENS_TAGS = ("lens", "echo")
FIELDS = ["id", "harvested", "written_on", "ei_week", "brand", "line", "shared_line", "status",
          "flag", "role_options", "docket", "docket_no", "source"]
# pending: clears on docket silence. held-name / held-reading: wait for Chris.
# cleared: agents may use. struck: never shared. lens / echo: moved to the Lens.
STATUSES = ("pending", "held-name", "held-reading", "cleared", "struck", "lens", "echo")

# The EI Brand Journal: setup weekend Oct 24-25, then Week 1 starts Mon Oct 26
# and Week 8 ends Sun Dec 20, 2026.
EI_SETUP = dt.date(2026, 10, 24)
EI_WEEK1 = dt.date(2026, 10, 26)
EI_END = dt.date(2026, 12, 20)


def ei_week(day: dt.date) -> str:
    if day < EI_SETUP:
        return "before"
    if day < EI_WEEK1:
        return "setup"
    if day > EI_END:
        return "after"
    return f"week {(day - EI_WEEK1).days // 7 + 1}"


def load(library: Path) -> list[dict]:
    if not library.exists() or library.stat().st_size == 0:
        return []
    with library.open(newline="") as f:
        return [{k: r.get(k) or "" for k in FIELDS} for r in csv.DictReader(f)]


CLEARED_FIELDS = ["id", "written_on", "ei_week", "brand", "shared_line"]


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    # Temp file, then rename, so a crash never leaves half a table.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".share-", suffix=".csv")
    with os.fdopen(fd, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def save(library: Path, rows: list[dict]) -> None:
    """Write the full table, and beside it cleared.csv: only cleared lines, as
    Chris cleared them. Agents read cleared.csv alone, so a name he has not yet
    swapped (or a line he struck) never reaches them, or the cloud."""
    library.parent.mkdir(parents=True, exist_ok=True)
    _write(library, FIELDS, rows)
    _write(library.parent / "cleared.csv", CLEARED_FIELDS, [r for r in rows if r["status"] == "cleared"])


def add(rows: list[dict], line: str, written_on: dt.date, source: str, status: str = "pending",
        flag: str = "", role_options: list[str] | None = None, brand: str = "both") -> dict:
    if status not in STATUSES or brand not in BRANDS:
        raise ValueError("bad status or brand")
    today = dt.date.today()
    prefix = f"SC-{today.isoformat()}-"
    n = sum(1 for r in rows if r["id"].startswith(prefix)) + 1
    row = {k: "" for k in FIELDS}
    row.update({
        "id": f"{prefix}{n:03d}",
        "harvested": today.isoformat(),
        "written_on": written_on.isoformat(),
        "ei_week": ei_week(written_on),
        "brand": brand,
        "line": line,
        "shared_line": line if status in ("pending", "cleared") else "",
        "status": status,
        "flag": flag,
        "role_options": " | ".join(role_options or []),
        "source": source,
    })
    rows.append(row)
    return row


def append_candidates(library: Path, entries: list[dict]) -> list[str]:
    """Add lines (each: line, written_on, source, optional brand) as pending."""
    rows = load(library)
    ids = [add(rows, e["line"], e["written_on"], e["source"], brand=e.get("brand", "both"))["id"] for e in entries]
    save(library, rows)
    return ids


# Each Lens section ends with one of these markers; new lines go just above it.
LENS_MARKERS = {"lens": "<!-- harvest adds Chris's lines above this -->",
                "echo": "<!-- harvest adds reader echoes above this -->"}
PLACEHOLDER = "(empty until "


def append_lens(lens: Path, tag: str, lines: list[str], written_on: dt.date) -> None:
    """Add Chris's confirmed words to a Lens section. Nothing already in the file
    is changed except that section's "(empty until ...)" placeholder line."""
    if tag not in LENS_TAGS:
        raise ValueError(f"tag must be one of {LENS_TAGS}")
    if not lens.exists():
        raise FileNotFoundError(f"{lens} is missing; install the Hierophant Lens first")
    text = lens.read_text()
    marker = LENS_MARKERS[tag]
    if marker not in text:
        raise ValueError(f"{lens.name} has lost its {tag} marker line; put it back before harvesting")
    before, after = text.split(marker, 1)
    kept = before.rstrip("\n").split("\n")
    if kept and kept[-1].startswith(PLACEHOLDER):
        kept.pop()
    stamp = f"{written_on.isoformat()} ({ei_week(written_on)})"
    block = [f"- {stamp}: {l}" for l in lines]
    lens.write_text("\n".join(kept + block) + "\n" + marker + after)
