#!/bin/bash
# Installs hybrid search (G2C-2026-10-24-004, Chris's yes Oct 24 2026).
# Free and local. Every Python package pinned with hashes (requirements.lock);
# both models pinned to exact revisions (models.lock.json). Nothing paid, no API keys.
# Steps: 1 disk check  2 venv + pinned packages  3 pinned models  4 index  5 scoreboard
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
NEED_GB=6   # venv ~1 GB + models ~1.3 GB, and keep a few GB spare on this Mac

echo "== 1. Free disk"
FREE_GB=$(df -g "$HOME" | awk 'NR==2{print $4}')
echo "Free: ${FREE_GB} GB (need at least ${NEED_GB} GB)"
if [ "$FREE_GB" -lt "$NEED_GB" ]; then echo "STOP: not enough free disk. Nothing was installed."; exit 1; fi

echo "== 2. Python packages (pinned, hash-checked)"
PY=""
for c in /opt/homebrew/opt/python@3.13/bin/python3.13 python3.13; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "STOP: python3.13 not found (brew install python@3.13)."; exit 1; }
[ -d "$DIR/.venv" ] || "$PY" -m venv "$DIR/.venv"
"$DIR/.venv/bin/python" -m pip install --quiet --disable-pip-version-check \
  --require-hashes --no-deps -r "$DIR/requirements.lock"

echo "== 3. Models (exact revisions from models.lock.json)"
HF_HUB_DISABLE_TELEMETRY=1 "$DIR/.venv/bin/python" - "$DIR/models.lock.json" <<'PY'
import json, sys
from huggingface_hub import snapshot_download
pins = json.load(open(sys.argv[1]))
for role, p in pins.items():
    path = snapshot_download(p["id"], revision=p["revision"],
                             allow_patterns=["*.json", "*.txt", "*.model", "model.safetensors"])
    print(f"{role}: {p['id']} @ {p['revision'][:12]} -> {path}")
PY

echo "== 4. Index"
"$DIR/hs" index

echo "== 5. Scoreboard (20 questions, all four modes)"
"$DIR/hs" scoreboard --publish && echo "SCOREBOARD: PASS" || echo "SCOREBOARD: NOT YET (tool installed; do not hand it to other agents yet)"
FREE_AFTER=$(df -g "$HOME" | awk 'NR==2{print $4}')
echo "Free disk after: ${FREE_AFTER} GB"
