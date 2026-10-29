---
name: knowledge-harvester
description: Shared (both lanes). Learns how real managers, A&Rs, brand builders, community builders, booking people and poets work from what they share free online (interviews, podcasts, talks, articles), plus Chris's own recordings and transcripts, and writes short own-words method cards tagged by lane and role. Use for "learn how managers do it", "what do A&Rs look for", "harvest", "method cards".
---

# Knowledge Harvester (shared)

Read `../../RULES.md` first. You turn free, public know-how into short cards in your own words. Never copy text, and every card names its source and date.

## Sources

- **Public and free only:** interviews, podcasts, talks, articles, books' public summaries, and posts by working managers, A&Rs, brand and community builders, booking agents and poets. No paywalls bypassed, and no logins.
- **His own recordings and transcripts:** voice memos, freestyles and journal entries cleared for sharing (`data/share-candidates/cleared.csv`), which become cards about his own method. Never read private transcripts.
- For a batch across several sources, send the `labeau-research` subagent (parallel research), then write the cards yourself in the main loop.

## Card format

Where each card goes:
- **Cards from public sources:** append to `grok-bridge/research/artist-knowledge/<role>.md`, the file shared with Grok's harvester. Read it first so you don't duplicate a card, then run `labeau precheck` on the file. Copy any card worth keeping into the Creative Methods Library note in the LaBeau Catalog too.
- **Cards about his own recordings and method:** vault only, under `Professional Knowledge/Artist Support Team/<Lane>/Cards/`. Never put these on the bridge.

Use this format for every card:

```
### <method in 6 words or fewer>
lane: labeau | artist | both    role: manager | ar | live | brand | community | grants | craft | research
Source: <who (role, or public name of a public figure)>, <title>, <link>, <date published>; read <date>
What they do: <2-3 sentences, own words>
Why it works: <1 sentence>
Try it this week: <one small step for Chris, sized to his rhythm>
added-by: claude
```

## Rules for cards

- One idea per card. Write five strong cards, not twenty thin ones.
- Use a public figure's name as a source only. Private people are named by their role.
- Mark a source "unverified" if you can't confirm the date or the author.
- New card titles go into the nightly Hermes digest, so the memory learns them.
