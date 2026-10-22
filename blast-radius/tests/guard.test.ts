import { expect, test } from 'claude-code/testing'

test('pen-rule folders and settings are refused, safe commands run', async ($, on) => {
  on('tool.call', () => ({ result: {} }))
  const pen = await $.tool.call({ tool: 'Write', file_path: '/Users/c/vault/poems/new.md', content: 'x' })
  expect(pen.deny ?? '').toContain('pen-rule')
  const settings = await $.tool.call({ tool: 'Edit', file_path: '/Users/c/.claude/settings.json', old_string: 'a', new_string: 'b' })
  expect(settings.deny ?? '').toContain('settings file')
  const ok = await $.tool.call({ tool: 'Write', file_path: '/Users/c/Developer/notes.md', content: 'x' })
  expect(ok.deny).toBeUndefined()
  const ls = await $.tool.call({ tool: 'Bash', command: 'ls -la' })
  expect(ls.deny).toBeUndefined()
})

test('a risky command with nobody to confirm is not run', async ($, on) => {
  on('tool.call', () => ({ result: {} }))
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  const rm = await $.tool.call({ tool: 'Bash', command: 'rm -rf ./drafts' })
  expect(rm.deny ?? '').toContain('blast-radius')
})

test('a risky command runs only on Proceed, and Cancel stops it', async ($, on) => {
  let ran = 0
  let question = ''
  let answer = 'Cancel'
  // The person's dialog: $.ui.ask is an AskUserQuestion call answered here.
  on('tool.call', (_, e) => {
    if (e.tool === 'AskUserQuestion') {
      question = e.questions[0]?.question ?? ''
      return { result: { questions: e.questions, answers: { [question]: answer } } }
    }
    ran += 1
    return { result: {} }
  })
  on('process.run', () => ({ value: { exitCode: 0, stdout: 'junk/a.txt\njunk/b.txt\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  const cancelled = await $.tool.call({ tool: 'Bash', command: 'rm -rf junk' })
  expect(cancelled.deny ?? '').toContain('cancelled')
  expect(question).toContain('2 files')
  expect(ran).toBe(0)
  answer = 'Proceed'
  const proceeded = await $.tool.call({ tool: 'Bash', command: 'rm -rf junk' })
  expect(proceeded.deny).toBeUndefined()
  expect(ran).toBe(1)
  for (const command of ['git reset --hard HEAD~1', 'git push --force origin main', 'find . -name "*.tmp" -delete', 'git clean -fd', 'rsync -a --delete a/ b/']) {
    answer = 'Cancel'
    const r = await $.tool.call({ tool: 'Bash', command })
    expect(r.deny ?? '').toContain('blast-radius')
  }
  expect(ran).toBe(1)
})

test('the shell cannot write, move or delete inside pen-rule folders', async ($, on) => {
  on('tool.call', (_, e) =>
    e.tool === 'AskUserQuestion' ? { result: { questions: e.questions, answers: { [e.questions[0]?.question ?? '']: 'Proceed' } } } : { result: {} },
  )
  on('process.run', () => ({ value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  const blocked = [
    'echo "new line" >> ~/vault/poems/rain.md',
    'cp draft.md poems/rain.md',
    'mv notes.md line-bank/notes.md',
    "sed -i '' 's/a/b/' Poems/rain.md",
    'rm -rf line-bank',
    'tee public-copy/caption.txt < x',
    'python3 fix.py poems/',
    'echo {} > ~/.claude/settings.json',
  ]
  for (const command of blocked) {
    const r = await $.tool.call({ tool: 'Bash', command })
    expect(r.deny ?? '').toContain('blast-radius')
  }
  for (const command of ['cat poems/rain.md', 'ls -la line-bank/', 'grep -r moon poems/ 2>/dev/null', 'wc -l public-copy/*.txt', 'echo hi > notes/today.md']) {
    const r = await $.tool.call({ tool: 'Bash', command })
    expect(r.deny).toBeUndefined()
  }
})

test('pen-rule folders are refused in any letter case and through a symlink', async ($, on) => {
  on('tool.call', () => ({ result: {} }))
  on('fs.stat', (_, e) =>
    e.path === '/Users/c/Developer/shortcut'
      ? { value: { kind: 'directory', size: 0, mtimeMs: 0, isLink: true, realPath: '/Users/c/vault/poems' } }
      : Promise.reject(Object.assign(new Error('ENOENT'), { code: 'ENOENT' })),
  )
  const upper = await $.tool.call({ tool: 'Write', file_path: '/Users/c/vault/Poems/new.md', content: 'x' })
  expect(upper.deny ?? '').toContain('pen-rule')
  const linked = await $.tool.call({ tool: 'Write', file_path: '/Users/c/Developer/shortcut/new.md', content: 'x' })
  expect(linked.deny ?? '').toContain('pen-rule')
  const lineBank = await $.tool.call({ tool: 'Edit', file_path: '/Users/c/labeau/line-bank/2026.md', old_string: 'a', new_string: 'b' })
  expect(lineBank.deny ?? '').toContain('pen-rule')
})
