#!/bin/bash
# Phase 1: finish harness-addons-v2 steps 2-3.
#   Step 2 (H2): hooks bundle. hookify + security-guidance (official Anthropic marketplace, pinned), the LaBeau
#     hookify rules (pen rule, no push, no send/post/buy, gh read-only, search only, no face), a check that the
#     fail-closed mods (blast-radius, outbox, action-log, privacy-preflight) are on, and the Trail of Bits style
#     deny-list STAGED (enabled only by ./bin/deny-list.sh enable after Chris's yes to the list).
#   Step 3 (H3): ccusage 20.0.40, ccstatusline 2.2.32 as the status line, and the quiet 6-9 PM notification hook
#     (needs-you, already built, quiet hours from config/clock.json).
# Each item: it works, blocked stays blocked, it removes cleanly. Nothing paid, no accounts, no keys.
PHASE=1
. "$(dirname "$0")/bin/lib.sh"
cd "$HOME" || exit 1
echo "Toolkit phase 1 (harness steps 2-3), $(date '+%Y-%m-%d %H:%M ET')"

step "Claude Code"
command -v claude >/dev/null 2>&1 && ok "claude $(claude --version 2>/dev/null | awk '{print $1}')" || { bad "claude command not found"; finish; exit 1; }

step "Node.js (needed by ccusage and ccstatusline)"
ensure_brew && ensure_node

step "H2: official Anthropic plugin marketplace, pinned"
[ -n "$(marketplace_dir claude-plugins-official)" ] || claude plugin marketplace add "$PLUGINS_REPO" >/dev/null
MP="$(marketplace_dir claude-plugins-official)"
if [ -d "$MP/.git" ]; then
  git -C "$MP" fetch -q origin "$PLUGINS_COMMIT" 2>/dev/null
  git -C "$MP" checkout -q "$PLUGINS_COMMIT" 2>/dev/null
  [ "$(git -C "$MP" rev-parse HEAD)" = "$PLUGINS_COMMIT" ] && ok "marketplace at pinned commit ${PLUGINS_COMMIT:0:12} ($MP)" || bad "marketplace not at pinned commit (at $(git -C "$MP" rev-parse --short HEAD))"
elif [ -n "$MP" ]; then
  note "marketplace at $MP is not a git folder; the pin is checked by hookify's version below"
  ok "official marketplace added"
else
  bad "claude-plugins-official marketplace could not be added"
fi

step "H2: hookify + security-guidance"
for p in hookify security-guidance; do
  [ -n "$(plugin_status "$p@claude-plugins-official")" ] || claude plugin install "$p@claude-plugins-official" --scope user >/dev/null
done
HV="$(plugin_version hookify@claude-plugins-official)"; SV="$(plugin_version security-guidance@claude-plugins-official)"
[ "$HV" = "${PLUGINS_COMMIT:0:12}" ] && [ "$(plugin_status hookify@claude-plugins-official)" = enabled ] && ok "works: hookify $HV enabled" || bad "hookify not enabled at ${PLUGINS_COMMIT:0:12} (got $HV)"
[ "$SV" = "2.0.16" ] && [ "$(plugin_status security-guidance@claude-plugins-official)" = enabled ] && ok "works: security-guidance $SV enabled" || bad "security-guidance not enabled at 2.0.16 (got $SV)"

step "H2: LaBeau hookify rules (pen rule, no push, no send, gh read-only, search only, no face)"
for d in "$OPS" "$DEV" "$TK"; do
  [ -d "$d" ] || continue
  mkdir -p "$d/.claude" && cp "$TK"/hookify/hookify.labeau-*.local.md "$d/.claude/"
  note "rules in $d/.claude/"
done
if [ -d "$OPS/.git" ] && ! grep -q 'hookify\.\*\.local\.md' "$OPS/.git/info/exclude" 2>/dev/null; then
  echo '.claude/hookify.*.local.md' >> "$OPS/.git/info/exclude"   # labeau-ops is public; keep local rules out of git
fi
HK="$(ls -d "$HOME"/.claude/plugins/cache/claude-plugins-official/hookify/*/ 2>/dev/null | head -1)"
RULES_AT="$TK"; [ -d "$OPS/.claude" ] && RULES_AT="$OPS"
if [ -n "$HK" ] && HKOUT="$("$PY" "$TK/bin/hookify_selftest.py" "${HK%/}" "$RULES_AT")"; then
  echo "$HKOUT" | sed 's/^/    /'
  ok "blocked stays blocked: every hookify case blocked or allowed as expected"
else
  echo "${HKOUT:-hookify plugin folder not found}" | sed 's/^/    /'
  bad "hookify self-test failed (see lines above)"
fi

step "H2: security-guidance per-edit check"
SG="$(ls -d "$HOME"/.claude/plugins/cache/claude-plugins-official/security-guidance/*/ 2>/dev/null | head -1)"
SGT="$(mktemp -d)"
OUT="$(echo "{\"session_id\":\"toolkit-selftest\",\"hook_event_name\":\"PostToolUse\",\"tool_name\":\"Write\",\"cwd\":\"$SGT\",\"tool_input\":{\"file_path\":\"$SGT/a.js\",\"content\":\"const x = eval(userInput)\"},\"tool_response\":{}}" | (cd "$SGT" && CLAUDE_PLUGIN_ROOT="${SG%/}" ENABLE_CODE_SECURITY_REVIEW=0 bash "${SG%/}/hooks/sg-python.sh" "${SG%/}/hooks/security_reminder_hook.py" 2>/dev/null))"
echo "$OUT" | grep -q "eval" && ok "blocked stays blocked: security-guidance flags eval() on write" || bad "security-guidance did not flag eval()"

step "H2: removes cleanly (disable, check, enable again)"
for p in hookify security-guidance; do
  claude plugin disable "$p@claude-plugins-official" --scope user >/dev/null 2>&1
  OFF="$(plugin_status "$p@claude-plugins-official")"
  claude plugin enable "$p@claude-plugins-official" --scope user >/dev/null 2>&1
  ON="$(plugin_status "$p@claude-plugins-official")"
  [ "$OFF" = disabled ] && [ "$ON" = enabled ] && ok "removes cleanly: $p switches off and back on" || bad "$p did not switch off and on cleanly"
done

step "H2: fail-closed mods (Outbox guard, action log, pen-rule guard)"
for m in blast-radius outbox action-log privacy-preflight; do
  [ "$(plugin_status "$m@chris-mods")" = enabled ] && ok "$m enabled" || bad "$m is not enabled (run ~/Developer/claude-mods/install.sh)"
done

step "H2: Trail of Bits style deny-list, staged only"
"$TK/bin/deny-list.sh" status | sed 's/^/    /'
note "the list is in toolkit/deny-list.json; turn it on with: ~/Developer/claude-mods/toolkit/bin/deny-list.sh enable"
ok "deny-list staged (not enabled by this script)"

step "H3: ccusage $CCUSAGE and ccstatusline $CCSTATUSLINE (pinned by package-lock)"
(cd "$TK/cli" && npm ci --no-audit --no-fund --loglevel=error --no-update-notifier) || bad "npm ci in toolkit/cli failed"
CCU="$TK/cli/node_modules/.bin/ccusage"
CCS="$TK/cli/node_modules/ccstatusline/dist/ccstatusline.js"
[ "$("$CCU" --version 2>/dev/null | awk '{print $NF}')" = "$CCUSAGE" ] && ok "works: ccusage $CCUSAGE" || bad "ccusage is not $CCUSAGE"
"$CCU" daily --offline --json >/dev/null 2>&1 && ok "works: ccusage daily report reads your local usage logs (offline)" || bad "ccusage daily failed"
SAMPLE='{"session_id":"t","transcript_path":"/dev/null","cwd":"/tmp","model":{"id":"claude","display_name":"Claude"},"workspace":{"current_dir":"/tmp","project_dir":"/tmp"},"version":"x","cost":{"total_cost_usd":0}}'
[ -f "$CCS" ] && [ -n "$(echo "$SAMPLE" | node "$CCS" 2>/dev/null)" ] && ok "works: ccstatusline $CCSTATUSLINE draws a line" || bad "ccstatusline did not draw a line"

step "H3: status line in ~/.claude/settings.json (backup kept)"
SET="$HOME/.claude/settings.json"
[ -f "$SET" ] || echo '{}' > "$SET"
CMD="\"$(command -v node)\" \"$CCS\""
BAK="$SET.bak-$(date +%Y%m%d-%H%M%S)-statusline"
cp "$SET" "$BAK"
"$PY" - "$SET" "$CMD" <<'PY'
import json, sys
path, cmd = sys.argv[1:3]
s = json.load(open(path))
old = s.get("statusLine")
if old and old.get("command") != cmd:
    print("    previous status line (kept in the backup):", json.dumps(old))
s["statusLine"] = {"type": "command", "command": cmd, "padding": 0}
json.dump(s, open(path, "w"), indent=2)
open(path, "a").write("\n")
PY
"$PY" -c 'import json,sys; s=json.load(open(sys.argv[1])); sys.exit(0 if "ccstatusline" in s.get("statusLine",{}).get("command","") else 1)' "$SET" && ok "statusLine is ccstatusline (backup: $BAK)" || bad "statusLine not set"
note "the cache-clock mod's line still shows beside it (mods pin their own line)"
note "undo: cp \"$BAK\" \"$SET\""

step "H3: blocked stays blocked, removes cleanly"
grep -q '"ccstatusline' "$TK/cli/package-lock.json" && grep -q '"version": "20.0.40"' "$TK/cli/package-lock.json" && ok "blocked stays blocked: versions locked in toolkit/cli/package-lock.json (npm ci installs only these)" || bad "lockfile does not pin ccusage/ccstatusline"
(cd "$TK/cli" && npm uninstall --dry-run ccusage ccstatusline >/dev/null 2>&1) && ok "removes cleanly: npm uninstall dry run passes; the status line backup restores settings" || bad "npm uninstall dry run failed"

step "H3: quiet 6-9 PM notification hook (needs-you)"
[ "$(plugin_status needs-you@chris-mods)" = enabled ] && ok "needs-you enabled" || bad "needs-you not enabled"
"$PY" - "$DEV/claude-mods/config/clock.json" <<'PY' && ok "quiet hours cover 6-9 PM" || bad "quiet hours in config/clock.json do not cover 6-9 PM"
import json, sys
c = json.load(open(sys.argv[1]))
m = lambda t: int(t[:2]) * 60 + int(t[3:5])
a, b = m(c["quietFrom"]), m(c["quietTo"])
quiet = (lambda x: a <= x or x < b) if a > b else (lambda x: a <= x < b)
sys.exit(0 if all(quiet(x) for x in range(18 * 60, 21 * 60)) else 1)
PY

step "Log: Changes rows, register rows, thread turn"
if [ "$FAILS" -eq 0 ]; then
  change_row "Claude Code plugins" "hookify (${PLUGINS_COMMIT:0:12}) and security-guidance 2.0.16 from claude-plugins-official, plus LaBeau hookify rules in labeau-ops, ~/Developer and the toolkit" "harness-addons-v2 step 2, Chris's yes Oct 24" "claude plugin uninstall hookify@claude-plugins-official security-guidance@claude-plugins-official; delete .claude/hookify.labeau-*.local.md"
  change_row "Claude Code permissions" "Trail of Bits style deny-list staged in claude-mods/toolkit/deny-list.json (not enabled)" "harness-addons-v2 step 2" "nothing to undo until enabled; then ./bin/deny-list.sh disable"
  change_row "Claude Code status line" "ccusage 20.0.40 and ccstatusline 2.2.32 (toolkit/cli, package-lock); statusLine set to ccstatusline" "harness-addons-v2 step 3" "cp $BAK ~/.claude/settings.json"
  register_rows
  thread_turn "Toolkit phase 1 PASS (harness steps 2-3): hookify + security-guidance pinned, LaBeau hookify rules, deny-list staged, ccusage 20.0.40, ccstatusline 2.2.32 status line, quiet-hours hook confirmed. Changes + register rows queued in status/airtable-pending.jsonl. Run by Chris in Terminal."
  ok "rows queued"
else
  note "not logged: fix the failures above and run phase 1 again"
fi
finish
