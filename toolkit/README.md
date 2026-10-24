# LaBeau media toolkit (42 add-ons plan, phases 1-4)

Built Oct 24, 2026 from Chris's "42 Things to Install" plan (Charlie Hills post), merged with
`grok-bridge/to-claude/OUT-2026-10-21-harness-addons-v2.md`. Chris said yes to the INSTALL NOW items and phases 1-4.
The LATER list stays one item per yes; nothing here touches it.

Rules every script keeps: official source only, every version pinned, nothing paid, no new accounts, no keys,
three passes per item (it works / blocked stays blocked / it removes cleanly), and a Changes row plus Skills Catalog
and Access Register rows queued for Airtable only when the phase passes. Pen rule: no AI on poems/, line-bank/,
public-copy/. No face in any media.

## Run (Terminal, in order; each phase stops on its own and prints one PASS or FAIL line)

```
cd ~/Developer/claude-mods/toolkit
./phase1.sh      # harness steps 2-3: hookify + security-guidance, LaBeau hook rules, deny-list staged, ccusage, ccstatusline
./phase2.sh      # ffmpeg, Node LTS, Python 3, Puppeteer; test: 4-slide carousel from his text
./phase3.sh      # Remotion + HyperFrames; test: 15-second silhouette text video from each
./phase4.sh      # GitHub CLI (read-only for agents), find-skills (search only), departments
```

`./phase2.sh my-lines.txt` and `./phase3.sh my-lines.txt` use any text file of his instead of the sample
(his posted Oct 22 lines). Carousel: one slide per paragraph. Video: one row per line, blank line for a gap.
Outputs land in `out/`; logs in `logs/`. Neither is committed.

## What each phase installs

| Phase | Item | Pin | Source |
|---|---|---|---|
| 1 | hookify | claude-plugins-official @ 58267944f921 | github.com/anthropics/claude-plugins-official |
| 1 | security-guidance | 2.0.16 (same commit) | code.claude.com/docs/en/security-guidance |
| 1 | LaBeau hookify rules | `hookify/` (7 rules) | this folder, copied to labeau-ops, ~/Developer and toolkit `.claude/` |
| 1 | Trail of Bits style deny-list | `deny-list.json` (61 rules), STAGED | `./bin/deny-list.sh enable` after Chris's yes to the list |
| 1 | ccusage | 20.0.40 | npm, `cli/package-lock.json` |
| 1 | ccstatusline (status line) | 2.2.32 | npm, `cli/package-lock.json` |
| 1 | quiet 6-9 PM notifications | needs-you mod (already built) | `config/clock.json` quiet hours |
| 2 | ffmpeg, Node.js LTS (node@24), Python 3.13 | Homebrew, `brew pin` | formulae.brew.sh |
| 2 | Puppeteer | 25.16.0 | pptr.dev, `package-lock.json` |
| 3 | Remotion | 4.0.538 | remotion.dev (Free License: individuals, up to 3 employees, non-profits; commercial use allowed) |
| 3 | HyperFrames | 0.8.191 | github.com/heygen-com/hyperframes (Apache-2.0), telemetry off |
| 3 | GSAP (HyperFrames runtime) | 3.15.0 | gsap.com, served locally, no CDN |
| 4 | GitHub CLI | Homebrew `gh`, `brew pin` | cli.github.com |
| 4 | find-skills | vercel-labs/skills @ a80e4c9d12d6, skills CLI 1.7.4 | skills.sh |
| 4 | media-maker, scout, bridge-clerk | `agents/` | DESIGN + MAKE, GROW, RUN departments |

## Guards

- hookify rules (`hookify/`): pen rule (Write/Edit and shell), no git push, no send/post/publish/deploy/buy, gh
  read-only, search only (no `skills add`, no `hyperframes skills/add/capture/auth/publish`, no `claude plugin install`),
  no face (avatar, talking head, lip-sync, face swap). `bin/hookify_selftest.py` runs 21 sample calls through them.
- hookify fails open by design, so the fail-closed layer stays the chris-mods guards (blast-radius, outbox,
  action-log, privacy-preflight) and, once enabled, the native deny-list.
- security-guidance never blocks; its end-of-turn and commit reviews use plan usage. Turn those two off and keep the
  free per-edit check with `ENABLE_CODE_SECURITY_REVIEW=0` in your shell profile if usage gets tight.

## Undo

- Plugins: `claude plugin uninstall hookify@claude-plugins-official` (same for security-guidance).
- Status line: copy back `~/.claude/settings.json.bak-*-statusline` (phase 1 prints the exact line).
- Deny-list: `./bin/deny-list.sh disable`.
- npm tools: `rm -r ~/Developer/claude-mods/toolkit/node_modules ~/Developer/claude-mods/toolkit/cli/node_modules ~/.cache/puppeteer ~/.cache/hyperframes`.
- Homebrew: `brew unpin <name> && brew uninstall <name>` (ffmpeg, node@24, python@3.13, gh).
- find-skills: `npx -y skills@1.7.4 remove find-skills -g -y`. Departments: delete the three files in `~/.claude/agents`.

## Logs

- Changes rows (status Verified), Access Register and Skills Catalog rows go to
  `~/Developer/grok-bridge/status/airtable-pending.jsonl`; bridge-inbox flushes Changes rows at the next session
  start. The register rows wait for a session with Airtable (drafts in `registers/`).
- Phase 4 adds the new skill and subagents to `labeau-ops/data/harness_map.csv` (the autonomy map); Chris commits it.
- Each passing phase appends a turn to `grok-bridge/threads/labeau.md`.
