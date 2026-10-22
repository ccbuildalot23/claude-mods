#!/usr/bin/env python3
"""Grid preview: the next Instagram posts laid out as the profile grid, at the profile's real 3:4 crop.

Reads labeau-ops data/placements.csv (what posts next on Instagram, and what posted lately) and finds each
post's file in LaBeau-Assets/04-posts the way labeau-ops does (slug, then __ variant). Pins come from
~/Developer/claude-mods/config/grid-pins.json, a list of up to three asset slugs, if you make one.
Output: ~/Developer/claude-mods/apps-out/grid-preview.html. Reads only.
"""
import datetime as dt, json, os, sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

MEDIA = (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v")
SIDECAR = (".json", ".refused.jpg", ".tmp")


def index_posts(root):
    """Every media file under 04-posts, by name."""
    files = []
    for dp, _, fns in os.walk(root, followlinks=True):
        if "_retired" in dp:
            continue
        for fn in fns:
            low = fn.lower()
            if low.endswith(MEDIA) and not low.endswith(SIDECAR):
                files.append((fn, os.path.join(dp, fn)))
    return files


def find(files, slug):
    if not slug:
        return None
    hits = sorted(p for fn, p in files if fn.startswith(slug) and (fn[len(slug):][:2] == "__" or fn[len(slug):][:1] in (".", "")))
    if not hits:
        return None
    ig = [p for p in hits if "ig" in os.path.basename(p).lower()]
    return (ig or hits)[0]


def tile(row, files, kind):
    path = find(files, row.get("asset_slug", ""))
    return {
        "id": row.get("placement_id", ""),
        "date": row.get("date", ""),
        "slug": row.get("asset_slug", "") or "(no asset yet)",
        "state": row.get("state", ""),
        "kind": kind,
        "src": ("file://" + quote(path)) if path else "",
        "isVideo": bool(path and path.lower().endswith((".mp4", ".mov", ".m4v"))),
    }


def main():
    rows = [r for r in common.read_csv("placements.csv") if r.get("platform") == "instagram"]
    if not rows:
        sys.exit(f"No Instagram rows in {common.OPS}/data/placements.csv.")
    root = os.path.join(common.ops_config("assets") or os.path.join(common.HOME, "LaBeau-Assets"), common.ops_config("posts_folder") or "04-posts")
    files = index_posts(root)
    today = dt.date.today().isoformat()
    upcoming = sorted((r for r in rows if r.get("date", "") >= today and r.get("state") in ("planned", "held", "released")), key=lambda r: (r["date"], r["placement_id"]))[:12]
    posted = sorted((r for r in rows if r.get("state") == "posted"), key=lambda r: (r.get("posted_at") or r["date"]), reverse=True)[:9]
    pins = []
    try:
        slugs = json.load(open(os.path.join(common.MODS, "config", "grid-pins.json")))
        pins = [tile({"asset_slug": s, "placement_id": "pin"}, files, "pinned") for s in slugs[:3]]
    except (OSError, ValueError):
        pass
    data = {
        "built": dt.datetime.now().strftime("%a %b %d, %I:%M %p"),
        "pins": pins,
        # The profile shows newest first: the last scheduled post sits top-left.
        "grid": [tile(r, files, "next") for r in reversed(upcoming)] + [tile(r, files, "posted") for r in posted],
        "root": root,
        "found": len(files),
    }
    path = common.write_page("grid-preview", data)
    missing = sum(1 for t in data["grid"] if not t["src"])
    print(f"Grid preview: {len(upcoming)} upcoming, {len(posted)} recent, {missing} without a file yet. Open {path}")


if __name__ == "__main__":
    main()
