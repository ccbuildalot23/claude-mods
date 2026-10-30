#!/bin/bash
# Studio fold (Chris's yes, Oct 30 2026): removes the Rig's three Codex studio seats
# (studio-chief, studio-still, studio-motion in labeau-exec) and gives their work to Claude Code:
# media-maker makes the assets, the exec chair (already on Claude Code) plans them as CDO.
# Why: their G197 motion review ran on an OpenAI API key and drew $117.64 on Oct 24 to 25.
#   ./studio-fold.sh --check   read-only: shows the seats, their open queue items and what would change
#   ./studio-fold.sh           does it: snapshot, hand open studio items to the chair, shrink the pod, install media-maker
PHASE=studio-fold
. "$(dirname "$0")/bin/lib.sh"
RIG_NAME=labeau-exec
POD=studio
CHAIR="exec-chair@$RIG_NAME"
SEATS="studio-chief studio-still studio-motion"
POD_FILE="$DEV/.ai-team-preflight-2026-10-12/openrig-workspace-teams/labeau-exec-extension/studio.pod.yaml"
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1
echo "Studio fold, $(date '+%Y-%m-%d %H:%M ET')$([ $CHECK = 1 ] && echo ' (check only, nothing changes)')"

step "The Rig is there"
command -v rig >/dev/null 2>&1 || { bad "rig is not on PATH (OpenRig CLI)"; finish; exit 1; }
RIG_ID="$(rig ps --json 2>/dev/null | "$PY" -c '
import json, sys
name = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
rows = data if isinstance(data, list) else data.get("rigs", [])
for r in rows:
    if isinstance(r, dict) and name in (r.get("name"), r.get("rigName")):
        print(r.get("id") or r.get("rigId") or name)
        break
' "$RIG_NAME")"
[ -n "$RIG_ID" ] && ok "$RIG_NAME is up (id $RIG_ID)" || { bad "$RIG_NAME is not in rig ps"; finish; exit 1; }

NODES="$(rig ps --nodes --rig "$RIG_NAME" 2>&1)"
FOUND=""
for s in $SEATS; do echo "$NODES" | grep -q "$s" && FOUND="$FOUND $s"; done
if [ -z "$FOUND" ]; then
  ok "no studio seats in $RIG_NAME: already folded"
else
  ok "studio seats found:$FOUND"
  echo "$NODES" | grep -E "studio-" | sed 's/^/    /'
fi
echo "$NODES" | grep -q "exec-chair" && ok "the chair seat is there to take studio planning" || bad "exec-chair not found in $RIG_NAME"

step "Open studio queue items (they go to the chair, not lost)"
ITEMS=""
HANDOFF_FAILED=0
for s in $SEATS; do
  L="$(rig queue list -A --destination "$s@$RIG_NAME" 2>/dev/null)"
  IDS="$(echo "$L" | grep -oE 'qitem-[0-9A-Za-z-]+' | sort -u)"
  for i in $IDS; do ITEMS="$ITEMS $i"; note "$s: $i"; done
done
[ -z "$ITEMS" ] && ok "none open"
if [ -n "$ITEMS" ] && [ $CHECK = 0 ]; then
  for i in $ITEMS; do
    rig queue handoff "$i" --to "$CHAIR" >/dev/null 2>&1 && ok "$i handed to $CHAIR" \
      || { bad "$i did not hand off: paste this line to Claude ($i, destined to a studio seat)"; HANDOFF_FAILED=1; }
  done
fi

if [ $CHECK = 1 ]; then
  step "What the full run would do"
  note "1. rig snapshot $RIG_ID (the undo point)"
  note "2. hand the open studio items above to $CHAIR"
  note "3. rig shrink $RIG_ID $POD  (removes studio-chief, studio-still, studio-motion)"
  note "4. install the updated media-maker subagent in ~/.claude/agents (old one backed up)"
  finish; exit 0
fi

if [ "$HANDOFF_FAILED" = 1 ]; then
  bad "stopped before removing any seat, so no studio work is orphaned"
  finish; exit 1
fi

if [ -n "$FOUND" ]; then
  step "Snapshot first (the undo point)"
  SNAP_OUT="$(rig snapshot "$RIG_ID" 2>&1)"
  echo "$SNAP_OUT" | tail -3 | sed 's/^/    /'
  SNAP_ID="$(echo "$SNAP_OUT" | grep -oE '01[0-9A-HJKMNP-TV-Z]{24}' | head -1)"
  [ -n "$SNAP_ID" ] && ok "snapshot $SNAP_ID" || { bad "snapshot did not report an id, so nothing was removed"; finish; exit 1; }

  step "Remove the studio pod"
  SH_OUT="$(rig shrink "$RIG_ID" "$POD" 2>&1)"; SH_RC=$?
  echo "$SH_OUT" | tail -5 | sed 's/^/    /'
  [ $SH_RC = 0 ] && ok "rig shrink $POD finished" || bad "rig shrink exited $SH_RC"
  AFTER="$(rig ps --nodes --rig "$RIG_NAME" 2>&1)"
  LEFT=""
  for s in $SEATS; do echo "$AFTER" | grep -q "$s" && LEFT="$LEFT $s"; done
  [ -z "$LEFT" ] && ok "studio seats gone from $RIG_NAME" || bad "still listed:$LEFT"
  echo "$AFTER" | grep -q "exec-chair" && ok "the chair seat is still up" || bad "exec-chair is missing after the shrink"
  note "undo: rig restore $SNAP_ID --rig $RIG_ID   (or: rig expand $RIG_ID $POD_FILE)"
fi

step "media-maker takes the still and motion work (Claude Code)"
mkdir -p "$HOME/.claude/agents"
A="$HOME/.claude/agents/media-maker.md"
if [ -f "$A" ] && ! cmp -s "$TK/agents/media-maker.md" "$A"; then
  cp "$A" "$A.bak-$(date +%Y%m%d-%H%M%S)" && note "old copy kept as $A.bak-*"
fi
cp "$TK/agents/media-maker.md" "$A" && grep -q "Cost cap" "$A" && ok "media-maker installed with the studio contract and cost cap" || bad "media-maker did not install"

finish
