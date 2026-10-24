---
name: labeau-no-push
enabled: true
event: bash
action: block
pattern: \bgit\s+(-C\s+\S+\s+)?push\b
---

**No git push from an agent.** Chris commits and pushes himself. Stage the change and hand him the exact Terminal lines.
