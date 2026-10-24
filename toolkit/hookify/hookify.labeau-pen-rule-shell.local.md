---
name: labeau-pen-rule-shell
enabled: true
event: bash
action: block
pattern: (?i)(>|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\brsync\b|\bln\b|\btruncate\b|\bdd\b|\bpython3?\b|\bnode\b)[^|;&]*(^|[\s/'"])(poems|line-bank|public-copy)/
---

**Pen rule.** That command could write into poems/, line-bank/ or public-copy/. AI never writes there. Read-only commands (cat, grep, ls) are fine.
