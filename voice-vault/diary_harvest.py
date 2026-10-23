#!/usr/bin/env python3
"""Sunday harvest: Chris's ✒-marked diary lines into the Brand Message Library.

  harvest            file any new photos from ~/Voice Inbox, then open the page
  harvest --demo     same page on two made-up pages, writing only to a temp folder

The page runs on this Mac only (127.0.0.1, a one-time key in the address). It
shows each diary page photo beside its machine reading. Chris ticks only the
lines he marked with the nib, fixes any misread word so it matches his pen, and
picks where each goes: LaBeau, Chris, Both, the Hierophant Lens, or Echo (a
reader's words from a Friday Connect). Unticked lines never leave the vault.

Before anything is written, every ticked line goes through the same privacy check
as voice-vault (private names and words, money, phone numbers, emails). A line
that trips it is held back and Chris is told why; it stays in the vault.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import mimetypes
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import share_library
import voice_vault as vv

HERE = Path(__file__).resolve().parent
TAGS = share_library.BRANDS + share_library.LENS_TAGS


def front_matter(note: Path) -> tuple[dict, list[str]]:
    text = note.read_text()
    meta, body = {}, text
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, [l for l in body.splitlines() if l.strip()]


def pending_pages(cfg: dict) -> list[dict]:
    pages = []
    folder = Path(cfg["diary_pages_dir"])
    for note in sorted(folder.glob("*Diary Page*.md")) if folder.is_dir() else []:
        meta, lines = front_matter(note)
        if meta.get("type") != "diary-page" or meta.get("status") != "needs-harvest":
            continue
        day = meta.get("photographed", "")[:10] or dt.date.today().isoformat()
        pages.append({"note": note.name, "photo": meta.get("photo", ""), "written_on": day,
                      "reading": meta.get("reading", ""), "lines": lines})
    return pages


def set_status(note: Path, status: str, extra: list[str]) -> None:
    text = note.read_text()
    text = re.sub(r"(?m)^status: needs-harvest$", f"status: {status}", text, count=1)
    if extra:
        head, sep, body = text[4:].partition("\n---\n")
        text = "---\n" + head + "\n" + "\n".join(extra) + sep + body
    note.write_text(text)


def save(cfg: dict, payload: dict) -> dict:
    """Check every ticked line, then write the ones that pass. With skip_held
    false and anything held, nothing is written and the holds come back."""
    folder = Path(cfg["diary_pages_dir"])
    held, plan = [], []
    for page in payload.get("pages", []):
        note = folder / Path(page["note"]).name
        if not note.exists():
            raise ValueError(f"unknown page {page['note']}")
        day = dt.date.fromisoformat(page["written_on"])
        for item in page.get("lines", []):
            text, tag = item["text"].strip(), item["tag"]
            if not text:
                continue
            if tag not in TAGS:
                raise ValueError(f"unknown place {tag}")
            reasons = vv.private_reasons(text, cfg["private_words"])
            if reasons:
                held.append({"note": note.name, "text": text, "why": "; ".join(reasons)})
            else:
                plan.append((note, day, text, tag))
    if held and not payload.get("skip_held"):
        return {"saved": 0, "held": held, "written": False}

    shares = [{"line": t, "brand": tag, "source": "diary-page " + n.name, "written_on": d}
              for n, d, t, tag in plan if tag in share_library.BRANDS]
    ids = share_library.append_candidates(Path(cfg["share_library"]), shares) if shares else []
    for n, d, t, tag in plan:
        if tag in share_library.LENS_TAGS:
            share_library.append_lens(Path(cfg["lens_file"]), tag, [t], d)
    for page in payload.get("pages", []):
        note = folder / Path(page["note"]).name
        mine = [h for h in held if h["note"] == note.name]
        extra = [f"harvested: {dt.date.today().isoformat()}",
                 f"shared_lines: {sum(1 for p in plan if p[0] == note)}"]
        if mine:
            extra.append("held_at_harvest: " + " | ".join(h["why"] for h in mine))
        set_status(note, "harvested", extra)
    vv.log(cfg, f"HARVEST {len(payload.get('pages', []))} page(s), {len(plan)} line(s) kept, {len(held)} held")
    return {"saved": len(plan), "ids": ids, "held": held, "written": True}


def preview(photo: Path, cache: Path) -> Path:
    """Browsers other than Safari cannot show HEIC; make a local JPEG copy."""
    if photo.suffix.lower() != ".heic" or not shutil.which("sips"):
        return photo
    out = cache / (photo.stem + ".jpg")
    if not out.exists():
        subprocess.run(["sips", "-s", "format", "jpeg", str(photo), "--out", str(out)], check=True, capture_output=True)
    return out


def serve(cfg: dict, open_browser: bool = True, port: int = 0) -> tuple[http.server.HTTPServer, str]:
    key = secrets.token_urlsafe(16)
    page_html = (HERE / "harvest_page.html").read_text()
    cache = Path(tempfile.mkdtemp(prefix="harvest-"))
    pages = pending_pages(cfg)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep diary text out of the Terminal scrollback
            pass

        def _ok(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            q = parse_qs(urlparse(self.path).query)
            if q.get("k", [""])[0] != key:
                self._ok(b"wrong key", "text/plain", 403)
                return False
            return True

        def do_GET(self):
            if not self._authed():
                return
            path = urlparse(self.path).path
            if path == "/":
                data = json.dumps({"pages": pages, "tags": list(TAGS)}).replace("</", "<\\/")
                self._ok(page_html.replace("/*DATA*/null", data).encode(), "text/html; charset=utf-8")
            elif path.startswith("/photo/"):
                name = Path(unquote(path[len("/photo/"):])).name
                if name not in {p["photo"] for p in pages}:
                    return self._ok(b"not found", "text/plain", 404)
                photo = preview(Path(cfg["diary_pages_dir"]) / name, cache)
                self._ok(photo.read_bytes(), mimetypes.guess_type(photo.name)[0] or "image/jpeg")
            else:
                self._ok(b"not found", "text/plain", 404)

        def do_POST(self):
            if not self._authed():
                return
            if urlparse(self.path).path != "/save":
                return self._ok(b"not found", "text/plain", 404)
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                result = save(cfg, payload)
            except Exception as e:
                return self._ok(json.dumps({"error": f"{type(e).__name__}: {e}"}).encode(), "application/json", 400)
            self._ok(json.dumps(result).encode(), "application/json")
            if result["written"]:
                threading.Thread(target=server.shutdown, daemon=True).start()

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/?k={key}"
    server.cache_dir = cache  # type: ignore[attr-defined]
    if open_browser:
        webbrowser.open(url)
    return server, url


def demo_cfg() -> dict:
    root = Path(tempfile.mkdtemp(prefix="harvest-demo-"))
    cfg = vv.load_config(HERE / "no-such-config.json")
    cfg.update({"diary_pages_dir": str(root / "Diary Pages"),
                "share_library": str(root / "share-candidates/share-candidates.csv"),
                "lens_file": str(root / "hierophant-lens/hierophant-lens.md"),
                "log_file": str(root / "harvest.log")})
    pages = Path(cfg["diary_pages_dir"])
    pages.mkdir(parents=True)
    Path(cfg["lens_file"]).parent.mkdir(parents=True)
    shutil.copy(HERE / "templates/hierophant-lens.md", cfg["lens_file"])
    for i, lines in enumerate([["Demo page, made up for the test.", "the river does not apologize for the stone",
                                "Call the trustee Monday about $400"],
                               ["Another made-up line about the light", "we were never lost, only early"]]):
        (pages / f"2026-10-25 140{i} Diary Page.md").write_text(
            f"---\ntype: diary-page\nphotographed: 2026-10-2{4 + i}T14:0{i}\nphoto: 2026-10-25 140{i} Diary Page.png\n"
            "reading: demo\nstatus: needs-harvest\ntags: [diary, private]\n---\n\n" + "\n".join(lines) + "\n")
        shutil.copy(HERE / "templates/demo-page.png", pages / f"2026-10-25 140{i} Diary Page.png")
    print(f"demo files in {root}")
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--demo", action="store_true", help="made-up pages in a temp folder")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.demo:
        cfg = demo_cfg()
    else:
        cfg = vv.load_config()
        n = vv.run(cfg)
        if n:
            print(f"filed {n} new item(s) from Voice Inbox first")
    if not pending_pages(cfg):
        print("No diary pages waiting. AirDrop your marked pages into ~/Voice Inbox and run harvest again.")
        return
    server, url = serve(cfg, open_browser=not args.no_browser)
    print(f"Harvest page open (this Mac only): {url}\nPress Save on the page when done, or Ctrl-C here to stop without saving.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Nothing was saved.")
    finally:
        shutil.rmtree(server.cache_dir, ignore_errors=True)  # type: ignore[attr-defined]


if __name__ == "__main__":
    sys.exit(main())
