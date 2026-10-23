"""The Brand Message Library's share-candidates and the Hierophant Lens.

Both hold Chris's words exactly as he confirmed them. This module only appends;
it never rewrites a line that is already there. Agents read these files and write
captions around the lines, never inside them (blast-radius guards both folders).
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

BRANDS = ("labeau", "chris", "both")
LENS_TAGS = ("lens", "echo")
FIELDS = ["id", "harvested", "written_on", "ei_week", "brand", "line", "source", "status"]

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


def _next_id(rows: list[dict], day: dt.date) -> str:
    prefix = f"SC-{day.isoformat()}-"
    n = sum(1 for r in rows if r.get("id", "").startswith(prefix)) + 1
    return f"{prefix}{n:03d}"


def append_candidates(library: Path, entries: list[dict]) -> list[str]:
    """Append share-candidates. Each entry: line, brand, source, written_on (date).
    The line is stored exactly as given. Returns the new ids."""
    library.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if library.exists():
        with library.open(newline="") as f:
            rows = list(csv.DictReader(f))
    today = dt.date.today()
    new_ids = []
    write_header = not library.exists() or library.stat().st_size == 0
    with library.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        for e in entries:
            if e["brand"] not in BRANDS:
                raise ValueError(f"brand must be one of {BRANDS}")
            row = {
                "id": _next_id(rows, today),
                "harvested": today.isoformat(),
                "written_on": e["written_on"].isoformat(),
                "ei_week": ei_week(e["written_on"]),
                "brand": e["brand"],
                "line": e["line"],
                "source": e["source"],
                "status": "share-candidate",
            }
            rows.append(row)
            w.writerow(row)
            new_ids.append(row["id"])
    return new_ids


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
