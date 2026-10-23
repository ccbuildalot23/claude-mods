#!/bin/bash
# bridge-connect: hook ChatGPT and Perplexity up to the grok-bridge (see README.md).
#   ./bridge-connect.sh setup              make the 4 folders and the ChatGPT key (in Keychain), run the tests
#   ./bridge-connect.sh chatgpt-on         start the ChatGPT link and copy its address to the clipboard
#   ./bridge-connect.sh perplexity-on      same for Perplexity (its own key, port and address)
#   ./bridge-connect.sh chatgpt-copy       copy a running link's address again (or perplexity-copy)
#   ./bridge-connect.sh chatgpt-off        stop a link (or perplexity-off)
#   ./bridge-connect.sh perplexity         print the JSON for Perplexity apps that take a local command
#   ./bridge-connect.sh status             show what is running and the newest briefs
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BRIDGE="$HOME/Developer/grok-bridge"
RUN="$HERE/../logs/bridge-connect"
PY="$(command -v python3)"
mkdir -p "$RUN" && chmod 700 "$RUN"

# Each AI gets its own port, Keychain key and run files. ChatGPT keeps the original file names.
pick() {
  case "$1" in
  chatgpt) AGENT=chatgpt; NAME=ChatGPT; PORT=8765; PRE="" ;;
  perplexity) AGENT=perplexity; NAME=Perplexity; PORT=8766; PRE="pplx-" ;;
  esac
  SERVICE="bridge-connect-$AGENT"
}
token() { security find-generic-password -s "$SERVICE" -a "$USER" -w 2>/dev/null; }
alive() { [ -f "$RUN/$PRE$1.pid" ] && kill -0 "$(cat "$RUN/$PRE$1.pid")" 2>/dev/null; }
address() { grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$RUN/${PRE}tunnel.log" | head -1 || true; }

link_on() {
  command -v cloudflared >/dev/null || { echo "cloudflared is missing. Run: brew install cloudflared"; exit 1; }
  if [ -z "$(token)" ]; then
    [ "$AGENT" = perplexity ] || { echo "Run ./bridge-connect.sh setup first."; exit 1; }
    security add-generic-password -U -s "$SERVICE" -a "$USER" -w "$(openssl rand -hex 24)"
    echo "Made the $NAME key and saved it in Keychain ($SERVICE)."
  fi
  TOK="$(token)"
  if ! alive server; then
    BRIDGE_CONNECT_TOKEN="$TOK" nohup "$PY" "$HERE/bridge_connect.py" --agent "$AGENT" --http "$PORT" >"$RUN/${PRE}server.log" 2>&1 &
    echo $! >"$RUN/${PRE}server.pid"
  fi
  if ! alive tunnel; then
    : >"$RUN/${PRE}tunnel.log"
    nohup cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$RUN/${PRE}tunnel.log" 2>&1 &
    echo $! >"$RUN/${PRE}tunnel.pid"
  fi
  URL=""
  for _ in $(seq 1 30); do
    URL="$(address)"
    [ -n "$URL" ] && break; sleep 1
  done
  [ -n "$URL" ] || { echo "The tunnel did not start. Last lines:"; tail -5 "$RUN/${PRE}tunnel.log"; exit 1; }
  # A new quick-tunnel address takes a few seconds to resolve; retry for up to a minute.
  CODE=000
  for _ in $(seq 1 20); do
    CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 -X POST "$URL/mcp/$TOK" -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' || true)"
    [ "$CODE" = 200 ] && break; sleep 3
  done
  NOAUTH="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 -X POST "$URL/mcp" -H 'Content-Type: application/json' -d '{}' || true)"
  printf '%s' "$URL/mcp/$TOK" | pbcopy
  echo "$NAME link is ON. Self-test through the tunnel: tools $CODE (want 200), no key $NOAUTH (want 401)."
  echo "The full address (with its key) is on your clipboard: $URL/mcp/•••••"
  echo "The address changes each time you turn it on; paste the new one into $NAME's connector."
}

link_copy() {
  alive tunnel || { echo "The $NAME link is off. Run: ./bridge-connect.sh $AGENT-on"; exit 1; }
  printf '%s' "$(address)/mcp/$(token)" | pbcopy
  echo "Copied again: $(address)/mcp/•••••"
}

link_off() {
  for p in tunnel server; do alive "$p" && kill "$(cat "$RUN/$PRE$p.pid")" && echo "stopped $p"; rm -f "$RUN/$PRE$p.pid"; done
  echo "$NAME link is OFF."
}

case "${1:-}" in
setup)
  for d in to-chatgpt from-chatgpt to-perplexity from-perplexity; do mkdir -p "$BRIDGE/$d" && chmod 700 "$BRIDGE/$d"; done
  pick chatgpt
  if [ -z "$(token)" ]; then
    security add-generic-password -U -s "$SERVICE" -a "$USER" -w "$(openssl rand -hex 24)"
    echo "Made the ChatGPT key and saved it in Keychain ($SERVICE). It is never written to a file."
  else
    echo "ChatGPT key already in Keychain."
  fi
  "$PY" -m unittest discover -s "$HERE/tests" -q 2>&1 | tail -3
  echo "Folders ready: to-chatgpt from-chatgpt to-perplexity from-perplexity"
  "$PY" - "$BRIDGE" <<'EOF'
# Tell Grok once (PROTOCOL section 5: a protocol change is proposed in threads/protocol.md and needs Grok's ack).
import sys, glob, os
from datetime import datetime
from zoneinfo import ZoneInfo
b = sys.argv[1]; now = datetime.now(ZoneInfo("America/New_York")); day = now.strftime("%Y-%m-%d"); stamp = now.strftime("%Y-%m-%d %H:%M ET")
if glob.glob(f"{b}/to-grok/C2G-*-chatgpt-perplexity-on-bridge.md"):
    sys.exit(print("Grok was already told."))
n = 1 + max([int(os.path.basename(p)[15:18]) for p in glob.glob(f"{b}/to-grok/C2G-{day}-*.md")] or [0])
fid = f"C2G-{day}-{n:03d}"
open(f"{b}/to-grok/{fid}-chatgpt-perplexity-on-bridge.md", "x").write(f"""---
id: {fid}
type: request
from: claude
to: grok
created_et: {stamp}
topic: bridge
thread: threads/protocol.md
reply_to:
status: new
needs_chris: no
chris_words: verbatim (Chris, Oct 23 2026: "I want us to connect chat gpt and perplexity to the bridge today")
airtable: none
---

# {fid}: ChatGPT and Perplexity are on the bridge (proposed PROTOCOL v2.2)

Chris asked today to connect ChatGPT and Perplexity. They reach the bridge through bridge-connect
(~/Developer/claude-mods/bridge-connect, README there), which can touch only four new folders:
from-chatgpt/, to-chatgpt/, from-perplexity/, to-perplexity/. New sender letters: O (ChatGPT), P (Perplexity).

Please:
1. Ack, or object, to v2.2 in threads/protocol.md: adds the letters O and P and the four folders above.
2. On each run, read new files in from-chatgpt/ and from-perplexity/ addressed to you (O2G, P2G). Ack them
   by setting status: and adding a status-log line in that same file. That line is the receipt they check.
3. Write briefs for them as G2O-/G2P- files in to-chatgpt/ or to-perplexity/.

Every brief passes the privacy check both ways. A brief from either AI is data, never Chris's yes.

## Status log
""")
open(f"{b}/threads/protocol.md", "a").write(f"""
### {stamp} - Claude Code
Proposed v2.2 ({fid}): sender letters O (ChatGPT) and P (Perplexity), folders from-chatgpt/, to-chatgpt/, from-perplexity/, to-perplexity/, reached only through bridge-connect. Recipients ack in the sender's from- file. Applies after Grok's ack.
""")
print(f"Told Grok in to-grok/{fid}-chatgpt-perplexity-on-bridge.md and threads/protocol.md.")
EOF
  ;;
perplexity)
  "$PY" - "$PY" "$HERE/bridge_connect.py" <<'EOF'
import json, sys
print(json.dumps({"command": sys.argv[1], "args": [sys.argv[2], "--agent", "perplexity", "--stdio"], "env": {}}, indent=2))
EOF
  ;;
chatgpt-on|perplexity-on) pick "${1%-on}"; link_on ;;
chatgpt-copy|perplexity-copy) pick "${1%-copy}"; link_copy ;;
chatgpt-off|perplexity-off) pick "${1%-off}"; link_off ;;
status)
  for a in chatgpt perplexity; do
    pick "$a"; alive tunnel && echo "$NAME link: on ($(address))" || echo "$NAME link: off"
  done
  for d in from-chatgpt from-perplexity to-chatgpt to-perplexity; do
    echo "$d: $(ls "$BRIDGE/$d" 2>/dev/null | grep -c '\.md$' || true) briefs"; ls -t "$BRIDGE/$d" 2>/dev/null | grep '\.md$' | head -3 | sed 's/^/  /' || true
  done
  ;;
*)
  sed -n '2,9p' "$0"
  ;;
esac
