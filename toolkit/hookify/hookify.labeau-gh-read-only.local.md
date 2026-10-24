---
name: labeau-gh-read-only
enabled: true
event: bash
action: block
pattern: \bgh\s+((pr|issue|release|repo|gist|label|workflow|run|secret|variable|project|ruleset|cache|codespace|extension|alias|config|auth|ssh-key|gpg-key)\s+(create|edit|merge|close|reopen|delete|comment|review|ready|lock|unlock|transfer|pin|unpin|develop|upload|fork|rename|archive|unarchive|sync|set|remove|enable|disable|run|rerun|cancel|login|logout|refresh|add|install|upgrade|import|setup-git|token|switch)\b|api\b.*(-X|--method)\s*(POST|PUT|PATCH|DELETE)|api\b.*\s(-f|-F|--field|--raw-field|--input)\s)
---

**GitHub CLI is read-only.** Viewing and listing are fine (gh repo view, gh pr list, gh pr diff). Anything that creates, edits, merges, comments or deletes waits for Chris's yes.
