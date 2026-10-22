#!/usr/bin/env python3
"""Voice-to-vault: record a voice memo, it is transcribed on this Mac and filed.
Text files (.txt, .md) dropped in the inbox are routed the same way, untranscribed.

Routing is by the first words Chris says, never by an AI guess:
  "Line ..." / "Line bank ..." / "LaBeau ..."  -> LaBeau line bank, word for word
  "Private ..." / "Vault ..." / anything else  -> Recovery vault Voice Inbox

Private is the default. A line memo that names a real person, therapy, money or
legal matters is held in the vault instead, with a note saying why.

Transcription runs locally (mlx-whisper, or whisper.cpp as a fallback). If no
local transcriber is installed the job stops; it never sends audio anywhere.
Logs record file names, routes and hashes only, never what was said.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()

DEFAULTS = {
    # Folders to pick audio up from. Files in "inbox" folders are moved out once
    # filed; files in "watch_readonly" folders (Voice Memos app) are never touched.
    "inbox": [str(HOME / "Voice Inbox")],
    "watch_readonly": [],
    # Only file read-only memos recorded at or after this time (ISO), so turning on
    # Voice Memos sync does not sweep up every old recording.
    "watch_since": "",
    "vault_inbox": str(HOME / "Documents/Desktop/Recovery/Recovery Library/Imported/Voice Inbox"),
    "line_bank_dir": str(HOME / "Developer/labeau-ops/data/line-bank/voice"),
    "line_audio_dir": str(HOME / "LaBeau-Assets/Voice Lines"),
    "state_file": str(HERE / "state/processed.json"),
    "log_file": str(HERE / "state/voice-vault.log"),
    "mlx_model": "mlx-community/whisper-large-v3-turbo",
    "whisper_cpp_model": "",
    # Words that keep a "line" memo out of LaBeau. Matched as whole words, any case.
    # Real names live only on the Mac in config/private-names.txt (see shared_list).
    "private_words": [
        "therapy", "therapist", "counselor", "bankruptcy", "trustee",
        "attorney", "lawyer", "court", "creditor", "timeshare", "diagnosis",
    ],
}

AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".caf", ".qta", ".aiff", ".flac", ".ogg"}
# Typed or dictated dumps from the brain-dump mod and phone app use the same
# triggers and routes; they skip transcription.
TEXT_EXT = {".txt", ".md"}
SETTLE_SECONDS = 15

# Spoken triggers. Whisper spells LaBeau a few ways, so accept the usual ones.
_LABEAU = r"(?:la\s?beau|la\s?bo|lebo|labo|le\s?beau)"
LINE_TRIGGER = re.compile(
    r"^\W*(?:" + _LABEAU + r"(?:\s+line(?:\s+bank)?)?|line\s+bank|poem\s+line|line)\b[\s,.:;!?-]*",
    re.IGNORECASE,
)
PRIVATE_TRIGGER = re.compile(r"^\W*(?:private|vault|journal|recovery)\b[\s,.:;!?-]*", re.IGNORECASE)
MONEY = re.compile(r"\$\s?\d|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|bucks)\b", re.IGNORECASE)
PHONE = re.compile(r"\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b")
EMAIL = re.compile(r"\b\S+@\S+\.\w+\b")


def shared_list(name: str) -> list[str]:
    """Names and words from privacy-preflight's lists (config/ in this repo, kept off git)."""
    try:
        text = (HERE.parent / "config" / name).read_text()
    except OSError:
        return []
    return [l.strip() for l in text.splitlines() if len(l.strip()) > 1 and not l.strip().startswith("#")]


def load_config(path: Path | None = None) -> dict:
    cfg = dict(DEFAULTS)
    path = path or HERE / "config.json"
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    for k in ("inbox", "watch_readonly"):
        cfg[k] = [os.path.expanduser(p) for p in cfg[k]]
    cfg["private_words"] = list(cfg["private_words"]) + shared_list("private-names.txt") + shared_list("private-words.txt")
    for k in ("vault_inbox", "line_bank_dir", "line_audio_dir", "state_file", "log_file"):
        cfg[k] = os.path.expanduser(cfg[k])
    return cfg


def private_reasons(text: str, words: list[str]) -> list[str]:
    reasons = []
    for w in words:
        if re.search(r"\b" + re.escape(w) + r"\b", text, re.IGNORECASE):
            reasons.append("names '" + w + "'")
    if MONEY.search(text):
        reasons.append("mentions money")
    if PHONE.search(text):
        reasons.append("has a phone number")
    if EMAIL.search(text):
        reasons.append("has an email address")
    return reasons


def route(text: str, private_words: list[str]) -> tuple[str, str, list[str]]:
    """Return (destination, body, held_reasons). Body is the transcript with only
    the spoken trigger removed; nothing else is changed."""
    m = LINE_TRIGGER.match(text)
    if m:
        body = text[m.end():].strip()
        if not body:
            return "vault", text.strip(), ["line memo was empty after the trigger word"]
        held = private_reasons(body, private_words)
        if held:
            return "vault", body, held
        return "line_bank", body, []
    m = PRIVATE_TRIGGER.match(text)
    if m:
        return "vault", text[m.end():].strip() or text.strip(), []
    return "vault", text.strip(), []


def transcribe(audio: Path, cfg: dict) -> str:
    try:
        import mlx_whisper  # type: ignore
    except ImportError:
        mlx_whisper = None
    if mlx_whisper is not None:
        out = mlx_whisper.transcribe(str(audio), path_or_hf_repo=cfg["mlx_model"], initial_prompt="LaBeau.")
        return out["text"].strip()
    cli = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    if cli and cfg["whisper_cpp_model"]:
        wav = audio.with_suffix(".vv.wav")
        try:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-ar", "16000", "-ac", "1", str(wav)], check=True)
            res = subprocess.run([cli, "-m", cfg["whisper_cpp_model"], "-nt", "-np", "-f", str(wav)], check=True, capture_output=True, text=True)
            return " ".join(res.stdout.split())
        finally:
            wav.unlink(missing_ok=True)
    raise RuntimeError("no local transcriber installed (run install.sh); audio was not sent anywhere")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    n = 2
    while True:
        p = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not p.exists():
            return p
        n += 1


VOICE_MEMO_NAME = re.compile(r"^(\d{8} \d{6})")


def recorded_at(audio: Path) -> dt.datetime:
    # Voice Memos names files by recording time; iCloud gives synced copies a new
    # creation date, so trust the name first.
    m = VOICE_MEMO_NAME.match(audio.name)
    if m:
        try:
            return dt.datetime.strptime(m.group(1), "%Y%m%d %H%M%S")
        except ValueError:
            pass
    st = audio.stat()
    times = [t for t in (getattr(st, "st_birthtime", None), st.st_mtime) if t]
    return dt.datetime.fromtimestamp(min(times))


def file_memo(audio: Path, text: str, cfg: dict, move_audio: bool) -> tuple[str, Path]:
    when = recorded_at(audio)
    is_text = audio.suffix.lower() in TEXT_EXT
    kind = "text-drop" if is_text else "voice-memo"
    transcript_line = "text: as typed or dictated, not edited" if is_text else "transcript: machine (local whisper), not edited"
    stamp = when.strftime("%Y-%m-%d %H%M")
    dest, body, held = route(text, cfg["private_words"])

    if dest == "line_bank":
        audio_dir = Path(cfg["line_audio_dir"])
        note_dir = Path(cfg["line_bank_dir"])
        note = unique(note_dir / f"{stamp} {'Text' if is_text else 'Voice'} Line.md")
        audio_out = unique(audio_dir / f"{note.stem}{audio.suffix.lower()}")
        front = [
            "---",
            "type: line-bank-entry",
            f"source: {kind}",
            f"recorded: {when.isoformat(timespec='minutes')}",
            f"original: {audio_out}",
            transcript_line,
            "status: unreviewed",
            "---",
            "",
        ]
        content = "\n".join(front) + body + "\n"
    else:
        note_dir = Path(cfg["vault_inbox"])
        note = unique(note_dir / f"{stamp} {'Text Drop' if is_text else 'Voice Memo'} - Transcript.md")
        audio_out = unique(note_dir / f"{note.stem} (original){audio.suffix.lower()}")
        front = [
            "---",
            "type: transcript-raw",
            f"source: {kind}",
            f"recorded: {when.isoformat(timespec='minutes')}",
            f"original: {audio_out.name}",
            "status: needs-intake",
            "tags: [recovery, voice-memo]",
        ]
        if held:
            front.append("held_from_line_bank: " + "; ".join(held))
        front += ["---", ""]
        content = "\n".join(front) + body + "\n"

    note_dir.mkdir(parents=True, exist_ok=True)
    audio_out.parent.mkdir(parents=True, exist_ok=True)
    if move_audio:
        shutil.move(str(audio), audio_out)
    else:
        shutil.copy2(audio, audio_out)
    note.write_text(content)
    label = "vault (held: " + "; ".join(held) + ")" if held else dest
    return label, note


def log(cfg: dict, msg: str) -> None:
    p = Path(cfg["log_file"])
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}\n")


def candidates(cfg: dict) -> list[tuple[Path, bool]]:
    out = []
    now = time.time()
    since = dt.datetime.fromisoformat(cfg["watch_since"]) if cfg.get("watch_since") else None
    for folder, move in [(d, True) for d in cfg["inbox"]] + [(d, False) for d in cfg["watch_readonly"]]:
        d = Path(folder)
        try:
            entries = sorted(d.iterdir()) if d.is_dir() else []
        except PermissionError:
            log(cfg, f"ERROR cannot read {d.name}: grant Full Disk Access (see README)")
            continue
        for p in entries:
            if not (p.is_file() and p.suffix.lower() in AUDIO_EXT | TEXT_EXT and now - p.stat().st_mtime > SETTLE_SECONDS):
                continue
            if not move and since and recorded_at(p) < since:
                continue
            out.append((p, move))
    return out


def run(cfg: dict, transcriber=transcribe) -> int:
    state_path = Path(cfg["state_file"])
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    filed = 0
    for audio, move in candidates(cfg):
        digest = sha256(audio)
        if digest in state:
            continue
        try:
            text = audio.read_text() if audio.suffix.lower() in TEXT_EXT else transcriber(audio, cfg)
        except Exception as e:  # keep going; the file stays put for the next run
            log(cfg, f"ERROR {audio.name}: {type(e).__name__}: {e}")
            if isinstance(e, RuntimeError) and "no local transcriber" in str(e):
                break
            continue
        if not text.strip():
            log(cfg, f"SKIP {audio.name}: empty transcript")
            state[digest] = {"route": "empty", "at": dt.datetime.now().isoformat(timespec="seconds")}
            continue
        label, note = file_memo(audio, text, cfg, move)
        state[digest] = {"route": label.split(" ")[0], "note": note.name, "at": dt.datetime.now().isoformat(timespec="seconds")}
        log(cfg, f"FILED {audio.name} -> {label} [{digest[:12]}]")
        filed += 1
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1))
    # Heartbeat, so a quiet run (nothing new) can be told apart from no run.
    (state_path.parent / "last_run.txt").write_text(dt.datetime.now().isoformat(timespec="seconds") + "\n")
    return filed


if __name__ == "__main__":
    n = run(load_config(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
    print(f"voice-vault: filed {n} memo(s)")
