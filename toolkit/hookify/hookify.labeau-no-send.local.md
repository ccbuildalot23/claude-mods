---
name: labeau-no-send
enabled: true
event: bash
action: block
pattern: (?i)\b(npm\s+publish|hyperframes\s+(publish|present)|wrangler\s+(pages\s+)?(deploy|publish)|deploy-site\.sh|sendmail|osascript\b.*\bsend\b|stripe\s|blotato)\b
---

**Nothing is sent, posted, published, deployed or bought without Chris's yes.** Draft it, put it in the Outbox, and ask him.
