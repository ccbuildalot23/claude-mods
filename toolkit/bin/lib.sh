#!/bin/bash
# Shared helpers for the toolkit phase scripts. Bash 3.2 safe (the Mac's /bin/bash).
# Every phase: says what it does, installs only its own pinned items, runs three passes per item
# (works / blocked stays blocked / removes cleanly), logs to toolkit/logs/, and queues its Changes rows.

TK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV="$HOME/Developer"
BRIDGE="$DEV/grok-bridge"
OPS="$DEV/labeau-ops"
# shellcheck source=../versions.env
. "$TK/versions.env"
export DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 HYPERFRAMES_SKIP_SKILLS=1

mkdir -p "$TK/logs" "$TK/out"
LOG="$TK/logs/phase${PHASE}-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

OKS=0
FAILS=0
FAILED=""
step() { echo; echo "== $*"; }
ok() { echo "  ✓ $*"; OKS=$((OKS + 1)); }
bad() { echo "  ✗ $*"; FAILS=$((FAILS + 1)); FAILED="$FAILED; $*"; }
note() { echo "    $*"; }

# Homebrew on Apple silicon or Intel, added to this shell's PATH.
brew_env() {
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"
  fi
}

# A Linux box (the cloud rehearsal) has no Homebrew: the brew steps check the command is there instead.
TEST_BOX=0
[ "$(uname)" = Linux ] && TEST_BOX=1

ensure_brew() {
  if [ "$TEST_BOX" = 1 ]; then ok "Linux test box: Homebrew steps check the command instead"; return 0; fi
  brew_env
  if command -v brew >/dev/null 2>&1; then
    ok "Homebrew $(brew --version | head -1 | awk '{print $2}') already here"
    return 0
  fi
  note "Homebrew is missing; running the official installer from brew.sh (it asks for your Mac password)."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || { bad "Homebrew install failed"; return 1; }
  brew_env
  if ! grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
    echo "eval \"\$($(command -v brew) shellenv)\"" >> "$HOME/.zprofile"
    note "added Homebrew to ~/.zprofile so new Terminal windows find it"
  fi
  command -v brew >/dev/null 2>&1 && ok "Homebrew $(brew --version | head -1 | awk '{print $2}') installed" || bad "Homebrew still not on PATH"
}

# Installs a formula if missing, then holds it with `brew pin` so `brew upgrade` leaves it alone.
ensure_formula() {
  local f="$1"
  if [ "$TEST_BOX" = 1 ]; then
    local bin="${2:-${f%%@*}}"
    command -v "$bin" >/dev/null 2>&1 && ok "$f: $bin present on the test box" || bad "$f: $bin missing on the test box"
    return
  fi
  if brew list --versions "$f" >/dev/null 2>&1; then
    note "$f $(brew list --versions "$f" | awk '{print $2}') already installed"
  else
    HOMEBREW_NO_AUTO_UPDATE=1 brew install "$f" || { bad "brew install $f failed"; return 1; }
  fi
  brew pin "$f" 2>/dev/null
  local v
  v="$(brew list --versions "$f" | awk '{print $2}')"
  brew list --pinned | grep -qx "$f" && ok "$f $v installed and pinned" || bad "$f $v installed but not pinned"
}

node_ok() { command -v node >/dev/null 2>&1 && node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>22||(a===22&&b>=20)?0:1)'; }

# Node.js LTS: keeps a Node 22.20+ that is already here; otherwise Homebrew node@24 (LTS), linked onto PATH.
ensure_node() {
  if node_ok; then
    ok "Node.js $(node -v) already here ($(command -v node))"
    return 0
  fi
  ensure_formula "$NODE_FORMULA" node || return 1
  brew link --force --overwrite "$NODE_FORMULA" >/dev/null 2>&1
  hash -r
  node_ok && ok "Node.js $(node -v) on PATH ($(command -v node))" || bad "Node.js 22.20+ still not on PATH"
}

ensure_python() {
  ensure_formula "$PYTHON_FORMULA" python3.13 || return 1
  local py
  if [ "$TEST_BOX" = 1 ]; then py="$(command -v python3.13)"; else py="$(brew --prefix "$PYTHON_FORMULA")/bin/python3.13"; fi
  [ -x "$py" ] && ok "Python $("$py" --version | awk '{print $2}') at $py" || bad "python3.13 not found after install"
}

PY="$(command -v python3.13 || command -v python3)"

# One Airtable row waiting in the bridge queue (bridge-inbox flushes Changes rows at the next session start;
# Access Register and Skills Catalog rows wait for a session or Bridge Keeper that can write them).
queue_row() {
  [ -d "$BRIDGE/status" ] || { note "no grok-bridge here; row kept in the log only"; return 0; }
  "$PY" - "$BRIDGE/status/airtable-pending.jsonl" "$@" <<'PY'
import json, sys, time
path, args = sys.argv[1], sys.argv[2:]
row = {"date_et": time.strftime("%Y-%m-%d %H:%M ET")}
for a in args:
    k, _, v = a.partition("=")
    row[k] = v
try:
    queued = [json.loads(l) for l in open(path) if l.strip()]
except (OSError, ValueError):
    queued = []
if any(q.get("table") == row.get("table") and q.get("summary") == row.get("summary") for q in queued):
    sys.exit(0)   # already waiting from an earlier run
with open(path, "a") as f:
    f.write(json.dumps(row) + "\n")
PY
}

change_row() {  # component summary why rollback
  queue_row table=Changes system="Mac" component="$1" summary="$2" why="$3" made_by="Chris (Terminal paste of toolkit phase $PHASE, written by Claude Code)" status="Verified" rollback="$4" bridge_ref="G2C-2026-10-24-001" risk="Low"
}

# Append-only thread turn, as PROTOCOL section 3 asks for every change on this Mac.
thread_turn() {
  [ -d "$BRIDGE/threads" ] || return 0
  printf '\n### %s - Claude Code\n%s\n' "$(date '+%Y-%m-%d %H:%M ET')" "$1" >> "$BRIDGE/threads/labeau.md"
}

# This phase's Access Register and Skills Catalog rows (toolkit/registers/*.csv), queued once for Airtable.
register_rows() {
  "$PY" "$TK/bin/registers.py" "$PHASE"
}

# "enabled" / "disabled" / "" for a plugin id such as hookify@claude-plugins-official, and its version.
# Reads `claude plugin list --json` (the text layout differs between machines); user scope wins over others.
plugin_field() {
  claude plugin list --json 2>/dev/null | "$PY" -c '
import json, sys
want, field = sys.argv[1:3]
try:
    rows = [p for p in json.load(sys.stdin) if p.get("id") == want]
except ValueError:
    rows = []
rows.sort(key=lambda p: p.get("scope") != "user")
if rows:
    p = rows[0]
    print(("enabled" if p.get("enabled") else "disabled") if field == "status" else p.get("version", ""))
' "$1" "$2"
}
plugin_status() { plugin_field "$1" status; }
plugin_version() { plugin_field "$1" version; }

# Folder a marketplace lives in, from `claude plugin marketplace list --json` ("" if not added).
marketplace_dir() {
  claude plugin marketplace list --json 2>/dev/null | "$PY" -c '
import json, sys
try:
    rows = json.load(sys.stdin)
except ValueError:
    rows = []
print(next((m.get("installLocation") or m.get("path") or "" for m in rows if m.get("name") == sys.argv[1]), ""))
' "$1"
}

finish() {
  echo
  if [ "$FAILS" -eq 0 ]; then
    echo "PHASE $PHASE: PASS ($OKS checks). Log: $LOG"
  else
    echo "PHASE $PHASE: FAIL ($FAILS of $((OKS + FAILS)) checks failed${FAILED}). Log: $LOG"
  fi
  [ "$FAILS" -eq 0 ]
}
