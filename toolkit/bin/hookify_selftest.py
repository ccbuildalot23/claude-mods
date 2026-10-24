#!/usr/bin/env python3
"""Feeds sample tool calls to the installed hookify plugin with the LaBeau rules and checks each one is blocked or
allowed as it should be. Usage: hookify_selftest.py <hookify plugin root> <folder whose .claude/ holds the rules>"""
import json, os, subprocess, sys

root, rules_dir = sys.argv[1], sys.argv[2]
BLOCK, ALLOW = 'block', 'allow'
CASES = [
    ('Write', {'file_path': '/Users/c/Developer/labeau-ops/poems/new.md', 'content': 'x'}, BLOCK, 'Write into poems/'),
    ('Edit', {'file_path': '/Users/c/Vault/Line-Bank/a.md', 'old_string': 'a', 'new_string': 'b'}, BLOCK, 'Edit in line-bank/ (any case)'),
    ('Write', {'file_path': '/Users/c/Developer/labeau-ops/public-copy/x.md', 'content': 'x'}, BLOCK, 'Write into public-copy/'),
    ('Write', {'file_path': '/Users/c/Developer/claude-mods/toolkit/out/notes.md', 'content': 'x'}, ALLOW, 'Write a normal file'),
    ('Bash', {'command': 'echo hi >> poems/today.md'}, BLOCK, 'shell append into poems/'),
    ('Bash', {'command': 'cat poems/today.md | wc -l'}, ALLOW, 'read a poem'),
    ('Bash', {'command': 'git push origin main'}, BLOCK, 'git push'),
    ('Bash', {'command': 'git -C ~/Developer/labeau-ops push'}, BLOCK, 'git -C push'),
    ('Bash', {'command': 'git status'}, ALLOW, 'git status'),
    ('Bash', {'command': 'npx hyperframes publish .'}, BLOCK, 'hyperframes publish'),
    ('Bash', {'command': './deploy-site.sh'}, BLOCK, 'site deploy'),
    ('Bash', {'command': 'gh pr create --fill'}, BLOCK, 'gh pr create'),
    ('Bash', {'command': 'gh api repos/x/y/issues -X POST -f title=t'}, BLOCK, 'gh api POST'),
    ('Bash', {'command': 'gh repo view ccbuildalot23/claude-mods'}, ALLOW, 'gh repo view'),
    ('Bash', {'command': 'gh pr list --state open'}, ALLOW, 'gh pr list'),
    ('Bash', {'command': 'npx -y skills@1.7.4 add vercel-labs/agent-skills'}, BLOCK, 'skills add'),
    ('Bash', {'command': 'npx -y skills@1.7.4 find carousel'}, ALLOW, 'skills find'),
    ('Bash', {'command': 'npx hyperframes render . -o out/a.mp4'}, ALLOW, 'hyperframes render'),
    ('Bash', {'command': 'npx hyperframes skills update'}, BLOCK, 'hyperframes skills update'),
    ('Bash', {'command': 'node make.mjs --avatar talking-head'}, BLOCK, 'avatar / talking head'),
    ('Bash', {'command': 'ffmpeg -i clip.mov -vf scale=1080:1920 out.mp4'}, ALLOW, 'ffmpeg cut'),
]
script = os.path.join(root, 'hooks', 'pretooluse.py')
fails = 0
for tool, inp, want, label in CASES:
    out = subprocess.run([sys.executable, script], input=json.dumps({'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': inp}),
                         capture_output=True, text=True, cwd=rules_dir, env=dict(os.environ, CLAUDE_PLUGIN_ROOT=root)).stdout
    try:
        res = json.loads(out or '{}')
    except ValueError:
        res = {}
    if 'error' in (res.get('systemMessage') or '').lower():
        print('FAIL  hookify reported an error: ' + res['systemMessage'])
        fails += 1
        continue
    got = BLOCK if (res.get('hookSpecificOutput') or {}).get('permissionDecision') == 'deny' else ALLOW
    ok = got == want
    fails += 0 if ok else 1
    print(('ok    ' if ok else 'FAIL  ') + f'{label}: {got}')
print(f'{len(CASES) - fails}/{len(CASES)} hookify cases as expected')
sys.exit(1 if fails else 0)
