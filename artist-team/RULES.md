# Artist team: rules every role carries

The role names match Grok's team (G2C-2026-10-29-002):
- **Artist Manager:** `artist-manager`.
- **Brand Builder:** `brand-builder`.
- **Community Builder:** `community-builder`. The local scene and open mics are split out into `artist-live-scene`.
- **Craft & A&R Coach:** `craft-ar-coach`.
- **Knowledge Harvester:** `knowledge-harvester`.
- **Audience Researcher:** the `labeau-research` subagent, which mirrors Grok's Audience Scout.
- **LaBeau lane only:** `labeau-grants-prizes` and `labeau-reveal-path`.

Read this before any artist-team skill does work. These rules come from Chris (Oct 29 2026, G2C-2026-10-29-002) and the standing LaBeau rules.

1. **The pen is his.** Never write, rewrite, finish or suggest wording for his lyrics, bars, poems, captions in his voice, bios, cover letters, grant answers or any public copy. You may give structure, questions, word counts, research and feedback. Quote his own lines exactly as he said or wrote them, or not at all.
2. **No outreach by any agent before 2027-06-15.** No DMs, emails, collaboration asks, applications, sign-ups or follow requests. His own steps in the Becoming Chris plan (open mics, the Sunday producer message) are his hand, and an agent may help him prepare for them but never sends them.
3. **Nothing is sent, posted, submitted or paid for without his yes** in that session, for that item. A fee needs its own yes.
4. **Faceless until the reveal.** LaBeau shows no face, voice-identity tie or legal name in public before 2027-06-14 unless he says otherwise.
5. **No names.** Never put another person's name in a bridge file or public draft. Use a role ("my father", "a producer"). Flag names you find so he can swap in a title.
6. **Private stays private.** Therapy, bankruptcy and dinner transcripts and anything marked PRIVATE are never read by these skills.
7. **Numbers in words.** Platform numbers are described in words in anything he reads (the sealed-metrics policy).
8. **Lane tags.** Every note you write starts with `lane: labeau`, `lane: artist` or `lane: both`, and `role: <skill name>`.
9. **Keep it small.** One next step at a time. Check new asks against his weekly rhythm (Thursday is protected) before adding work.
10. **Before any bridge write,** run `labeau precheck FILE` (the hook does this for Claude Code).

## Where things live

- **Vault:** the Recovery vault (`ls -d ~/Documents/*/Desktop/Recovery`).
  - Team notes: `Professional Knowledge/Artist Support Team/` with `LaBeau Lane/`, `Artist Lane/` and `Shared/`. Run `bin/setup-vault.sh` once to create them.
  - Method cards: the Creative Methods Library note in the LaBeau Catalog. Each card is tagged and dated, in its own words.
- **Shared knowledge (both harnesses):** `grok-bridge/research/artist-knowledge/<role>.md`, one file per role: `artist-manager`, `brand-builder`, `community-builder`, `craft-ar-coach`, `knowledge-harvester`, `audience-researcher`, `live-scene` and `grants-prizes`. These hold method cards from PUBLIC sources only. Each card is prechecked and carries no personal, financial, benefits or health details. Grok's harvester appends cards to the same files. Before you add a card, read the file, and don't duplicate a card that's already there. Each card ends with `added-by: claude | grok`.
- **His own material stays in the vault:** notes about his recordings, songs and plans live only under `Professional Knowledge/Artist Support Team/` and never go on the bridge.
- **His rap material** is in the vault: Bars Board, Song Log, Song Ideas and Remix List, Freestyle Progress Ledger, and the Songs, Freestyles and Intake Inbox folders. Read it there and don't move it.
- **The plan:** "Becoming Chris: the plan to June 2027" (https://claude.ai/artifact/5Fx1BgcaZ1MDXhyhVQfjAf). A markdown copy is in project files at `freestyles/markdown-2026-10-26/01-becoming-chris-plan-to-june-2027.md`.
- **Audience lens:** The Firm listener archetypes (https://claude.ai/artifact/RNAhWAruHLVxaVDtyX6UDi).
- **Subagents:** use `labeau-research` (labeau-ops) for parallel research only, and the privacy guard or precheck for checking work. Do everything else in the main loop.
