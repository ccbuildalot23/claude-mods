#!/bin/bash
# Turns the staged deny-list on or off in ~/.claude/settings.json (a backup is kept beside it).
#   ./bin/deny-list.sh show | enable | disable | status
cd "$(dirname "$0")/.." || exit 1
SETTINGS="$HOME/.claude/settings.json"
case "$1" in
  show) python3 -c 'import json,sys; [print(" ", r) for r in json.load(open(sys.argv[1]))["deny"]]' deny-list.json ;;
  enable|disable|status)
    mkdir -p "$HOME/.claude"
    [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
    [ "$1" = status ] || cp "$SETTINGS" "$SETTINGS.bak-$(date +%Y%m%d-%H%M%S)-denylist"
    python3 - "$1" "$SETTINGS" deny-list.json <<'PY'
import json, sys
mode, path, staged = sys.argv[1:4]
s = json.load(open(path))
rules = json.load(open(staged))["deny"]
deny = s.setdefault("permissions", {}).setdefault("deny", [])
if mode == "enable":
    deny.extend(r for r in rules if r not in deny)
elif mode == "disable":
    s["permissions"]["deny"] = [r for r in deny if r not in rules]
on = sum(1 for r in rules if r in s["permissions"]["deny"])
if mode != "status":
    json.dump(s, open(path, "w"), indent=2)
    open(path, "a").write("\n")
print(f"deny-list: {on} of {len(rules)} rules on in {path}")
PY
    ;;
  *) echo "usage: ./bin/deny-list.sh show | enable | disable | status"; exit 2 ;;
esac
