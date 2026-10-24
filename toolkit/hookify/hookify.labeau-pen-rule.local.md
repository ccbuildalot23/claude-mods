---
name: labeau-pen-rule
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (?i)(^|/)(poems|line-bank|public-copy)(/|$)
---

**Pen rule.** No AI writes in poems/, line-bank/ or public-copy/. Those words are Chris's alone. Read them if the task needs it; never edit them.
