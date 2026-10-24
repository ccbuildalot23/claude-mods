#!/bin/bash
# Phase 4: GitHub CLI (Homebrew, pinned, read-only for agents) and find-skills (skills.sh by Vercel, search only),
# plus the department subagents from the plan: media-maker (DESIGN + MAKE), scout (GROW), bridge-clerk (RUN).
# BUILD is the main loop; plan-checker stays the rule checker.
PHASE=4
. "$(dirname "$0")/bin/lib.sh"
echo "Toolkit phase 4 (GitHub CLI, find-skills, departments), $(date '+%Y-%m-%d %H:%M ET')"
node_ok || { bad "Node.js 22.20+ missing: run phase 2 first"; finish; exit 1; }

step "GitHub CLI (04)"
ensure_brew && ensure_formula gh
GHV="$(gh --version 2>/dev/null | head -1 | awk '{print $3}')"
[ -n "$GHV" ] && ok "works: gh $GHV" || bad "gh not on PATH"
if ! gh auth status >/dev/null 2>&1; then
  if [ "$TEST_BOX" = 1 ]; then
    note "test box: sign-in skipped"
  else
    note "Sign in to your existing GitHub account (a browser window opens; no new account, no token to copy):"
    gh auth login --hostname github.com --git-protocol https --web
  fi
fi
if gh auth status >/dev/null 2>&1; then
  gh repo view ccbuildalot23/claude-mods --json name -q .name >/dev/null 2>&1 && ok "works: gh reads ccbuildalot23/claude-mods" || bad "gh could not read ccbuildalot23/claude-mods"
else
  [ "$TEST_BOX" = 1 ] && ok "test box: gh read check skipped (not signed in)" || bad "gh is not signed in"
fi

step "find-skills (40): search only"
SK="npx -y skills@$SKILLS"
V="$($SK --version 2>/dev/null | tail -1)"
[ "$V" = "$SKILLS" ] && ok "works: skills CLI $V (telemetry off)" || bad "skills CLI is '$V', not $SKILLS"
R="$($SK find carousel 2>&1)"
if echo "$R" | grep -qi "no skills found\|error\|fail"; then
  echo "$R" | head -3 | sed 's/^/    /'
  [ "$TEST_BOX" = 1 ] && note "test box cannot reach skills.sh" || bad "skills.sh search returned nothing"
else
  echo "$R" | head -6 | sed 's/^/    /'
  ok "works: skills.sh search answers (nothing installed)"
fi
if [ ! -f "$HOME/.claude/skills/find-skills/SKILL.md" ]; then
  # The search skill itself, from the official repo at the pinned commit. This is the one install; what it finds is not.
  $SK add "$FIND_SKILLS_REPO#$FIND_SKILLS_COMMIT" --skill find-skills -g -a claude-code -y >/dev/null 2>&1
fi
F="$HOME/.claude/skills/find-skills/SKILL.md"
if [ -f "$F" ]; then
  grep -q "LaBeau rule" "$F" || cat >> "$F" <<'MD'

## LaBeau rule (Chris, Oct 24 2026)

Search only. Show Chris the skill's name, source, install count and the exact install command, then stop.
Never run `npx skills add` (or update, remove, use) yourself: each install needs his yes on that one item,
and it is logged in the Skills Catalog, Access Register and a Changes row before anyone runs it.
MD
  grep -q "$FIND_SKILLS_COMMIT" "$HOME/.agents/.skill-lock.json" 2>/dev/null && ok "find-skills pinned at ${FIND_SKILLS_COMMIT:0:12}, with the search-only rule added" || bad "find-skills is not at the pinned commit"
else
  bad "find-skills skill did not install"
fi

step "Departments (subagents, 4 max)"
mkdir -p "$HOME/.claude/agents"
for a in media-maker scout bridge-clerk; do
  if [ -f "$HOME/.claude/agents/$a.md" ] && ! cmp -s "$TK/agents/$a.md" "$HOME/.claude/agents/$a.md"; then
    cp "$HOME/.claude/agents/$a.md" "$HOME/.claude/agents/$a.md.bak-$(date +%Y%m%d)"
  fi
  cp "$TK/agents/$a.md" "$HOME/.claude/agents/$a.md" && ok "$a installed in ~/.claude/agents"
done
[ -f "$HOME/.claude/agents/plan-checker.md" ] && ok "plan-checker is there (the rule checker stays)" || note "plan-checker.md not found in ~/.claude/agents (it may live in a project folder)"

step "Blocked stays blocked"
HK="$(ls -d "$HOME"/.claude/plugins/cache/claude-plugins-official/hookify/*/ 2>/dev/null | head -1)"
if [ -n "$HK" ]; then
  for c in "gh pr create --fill" "gh repo delete ccbuildalot23/claude-mods" "npx -y skills@$SKILLS add vercel-labs/agent-skills"; do
    D="$(cd "$TK" && echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"$c\"}}" | CLAUDE_PLUGIN_ROOT="${HK%/}" "$PY" "${HK%/}/hooks/pretooluse.py")"
    echo "$D" | grep -q '"deny"' && ok "blocked for agents: $c" || bad "not blocked: $c"
  done
  D="$(cd "$TK" && echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"gh pr list"}}' | CLAUDE_PLUGIN_ROOT="${HK%/}" "$PY" "${HK%/}/hooks/pretooluse.py")"
  echo "$D" | grep -q '"deny"' && bad "gh pr list is blocked but should be allowed" || ok "allowed for agents: gh pr list (read-only)"
else
  bad "hookify not installed (run phase 1)"
fi

step "Removes cleanly"
[ "$TEST_BOX" = 1 ] || { brew uninstall --dry-run gh >/dev/null 2>&1 && ok "brew uninstall --dry-run gh passes" || note "undo: gh auth logout; brew unpin gh && brew uninstall gh"; }
ok "find-skills undo: npx -y skills@$SKILLS remove find-skills -g -y (or delete ~/.claude/skills/find-skills)"
ok "departments undo: delete ~/.claude/agents/{media-maker,scout,bridge-clerk}.md"

step "Skills Catalog: labeau-ops harness map rows for the new skill and subagents"
HM="$OPS/data/harness_map.csv"
if [ -f "$HM" ]; then
  cp "$HM" "$TK/logs/harness_map.csv.bak-$(date +%Y%m%d-%H%M%S)"
  "$PY" - "$HM" "$TK/registers/harness-map-rows.csv" <<'PY'
import csv, sys
path, new = sys.argv[1:3]
have = {r["part_id"] for r in csv.DictReader(open(path))}
rows = [r for r in csv.DictReader(open(new)) if r["part_id"] not in have]
if rows:
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        for r in rows:
            w.writerow(r)
print(f"    {len(rows)} row(s) added to data/harness_map.csv")
PY
  HMC="$(cd "$OPS" && "$PY" scripts/harness_map.py check 2>&1)"
  FLAG="$(echo "$HMC" | grep -E "find-skills|media-maker|subagent:user:scout|bridge-clerk" | grep -v "^WARN")"
  if [ -n "$FLAG" ]; then
    echo "$FLAG" | sed 's/^/    /'
    bad "harness map check still flags a new part"
  else
    ok "labeau harness-map check has nothing to say about the new parts"
  fi
  note "labeau-ops change to commit yourself: cd ~/Developer/labeau-ops && git add data/harness_map.csv && git commit -m 'Harness map: find-skills + media-maker, scout, bridge-clerk'"
else
  note "labeau-ops harness map not found; rows stay in toolkit/registers/harness-map-rows.csv"
fi

step "Log: Changes rows, register rows, thread turn"
if [ "$FAILS" -eq 0 ]; then
  change_row "Mac tools" "GitHub CLI $GHV (Homebrew, brew pin), signed in to Chris's existing account; agents limited to view/list by hookify rule" "42 add-ons plan item 04 (Chris's yes Oct 24)" "gh auth logout; brew unpin gh && brew uninstall gh"
  change_row "Claude Code skills" "find-skills (vercel-labs/skills) in ~/.claude/skills, search only; skills CLI $SKILLS via npx" "42 add-ons plan item 40" "npx -y skills@$SKILLS remove find-skills -g -y"
  change_row "Claude Code subagents" "media-maker, scout, bridge-clerk in ~/.claude/agents (DESIGN + MAKE, GROW, RUN departments)" "42 add-ons plan, departments" "delete the three files in ~/.claude/agents"
  register_rows
  thread_turn "Toolkit phase 4 PASS: gh $GHV read-only for agents, find-skills search only, departments media-maker / scout / bridge-clerk added. Changes + register rows queued. Run by Chris in Terminal."
  ok "rows queued"
else
  note "not logged: fix the failures above and run phase 4 again"
fi
finish
