import { expect, mock, test } from 'claude-code/testing'

const files: Record<string, string> = {
  '/Users/c/Developer/claude-mods/config/private-names.txt': '# one name per line\nJordan Example\n',
}

test('shared writes with private detail are blocked; clean and private-folder writes pass', async ($, on) => {
  mock.clock(on, { now: new Date('2026-10-22T16:00:00').getTime() })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('fs.read', (_, e) => (files[e.path] !== undefined ? { value: files[e.path] } : Promise.reject(new Error('ENOENT'))) as never)
  on('fs.stat', () => Promise.reject(new Error('ENOENT')) as never)
  on('tool.call', () => ({ result: {} }))

  const bridge = '/Users/c/Developer/grok-bridge/threads/protocol.md'
  const name = await $.tool.call({ tool: 'Write', file_path: bridge, content: 'Talked with Jordan Example today.' })
  expect(name.deny ?? '').toContain('private list')

  const word = await $.tool.call({ tool: 'Write', file_path: bridge, content: 'He has therapy on Thursday.' })
  expect(word.deny ?? '').toContain('private-life word')

  const key = await $.tool.call({ tool: 'Write', file_path: bridge, content: 'key: sk-ant-abcdefghijklmnopqrstuvwxyz123456' })
  expect(key.deny ?? '').toContain('API key')

  const future = await $.tool.call({ tool: 'Write', file_path: bridge, content: '## Status log\n- 2026-10-22 18:30 ET acked: read.' })
  expect(future.deny ?? '').toContain('later than now')

  const badName = await $.tool.call({ tool: 'Write', file_path: '/Users/c/Developer/grok-bridge/to-claude/OUT-2026-10-22-notes.md', content: 'status: new' })
  expect(badName.deny ?? '').toContain('PROTOCOL')

  const badStatus = await $.tool.call({ tool: 'Write', file_path: '/Users/c/Developer/grok-bridge/to-grok/C2G-2026-10-22-001-hello.md', content: 'status: open' })
  expect(badStatus.deny ?? '').toContain('status "open"')

  const clean = await $.tool.call({ tool: 'Write', file_path: '/Users/c/Developer/grok-bridge/to-grok/C2G-2026-10-22-001-hello.md', content: 'status: new\n- 2026-10-22 15:58 ET sent.' })
  expect(clean.deny).toBeUndefined()

  const privateFolder = await $.tool.call({ tool: 'Write', file_path: '/Users/c/Documents/vault/notes.md', content: 'therapy notes' })
  expect(privateFolder.deny).toBeUndefined()

  const airtable = await $.tool.call({ tool: 'mcp__Airtable__create_records_for_table', records: [{ fields: { Note: 'relapse risk' } }] } as never)
  expect(airtable.deny ?? '').toContain('private-life word')

  const shell = await $.tool.call({ tool: 'Bash', command: 'echo "therapy" >> ~/Developer/grok-bridge/threads/x.md' })
  expect(shell.deny ?? '').toContain('privacy-preflight')
})

test('only Chris typing /preflight allow lets a blocked write through once', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: new Date('2026-10-22T16:00:00').getTime() })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('fs.read', () => Promise.reject(new Error('ENOENT')) as never)
  on('fs.stat', () => Promise.reject(new Error('ENOENT')) as never)
  on('tool.call', () => ({ result: {} }))
  on('command.run', () => ({ text: 'engine' }))
  const call = { tool: 'Write', file_path: '/Users/c/Developer/grok-bridge/threads/t.md', content: 'sober and steady' } as const
  const first = await $.tool.call(call)
  const id = /PF-[0-9a-f]+/.exec(first.deny ?? '')?.[0] ?? ''
  expect(id.length > 0).toBe(true)
  const byModel = await $.command.run({ command: 'preflight', args: `allow ${id}` } as never)
  expect(byModel.text).toContain('only Chris')
  const byChris = await $.command.run({ command: 'preflight', args: `allow ${id}`, origin: { kind: 'composer' } } as never)
  expect(byChris.text).toContain('allowed once')
  expect((await $.tool.call(call)).deny).toBeUndefined()
  expect((await $.tool.call(call)).deny ?? '').toContain('privacy-preflight')
})
