---
name: labeau-search-only
enabled: true
event: bash
action: block
pattern: (?i)\bskills(@[0-9.]+)?\s+(add|install|update|remove|rm|experimental_sync|use)\b|\bhyperframes(@[0-9.]+)?\s+(skills|add|catalog|capture|auth|login|telemetry\s+enable)\b|\bclaude\s+plugin\s+(install|marketplace\s+add)\b
---

**Search only.** find-skills may search skills.sh, but nothing it finds is installed without Chris's yes on that one item. Show him the name, source, install count and the exact command, and stop.
