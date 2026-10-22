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
