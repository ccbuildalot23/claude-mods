import { expect, mock, test } from 'claude-code/testing'

const MSG = `---
id: G2C-2026-10-22-001
type: request
from: grok
to: claude
created_et: 2026-10-22 09:00 ET
topic: harness
status: new
needs_chris: yes - pick a cento
---
Please draft three cento options for Friday.
`

test('lists new messages with summaries, flags needs_chris, acks by protocol', async ($, on) => {
  mock.clock(on, { now: new Date('2026-10-22T16:05:00').getTime() })
  const files: Record<string, string> = {
    '/Users/c/Developer/grok-bridge/to-claude/G2C-2026-10-22-001-cento.md': MSG,
    '/Users/c/Developer/grok-bridge/to-claude/MOVED-old.md': 'moved',
  }
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('fs.list', () => ({ value: [{ name: 'G2C-2026-10-22-001-cento.md', kind: 'file', size: 1, mtimeMs: 0, isLink: false }, { name: 'MOVED-old.md', kind: 'file', size: 1, mtimeMs: 0, isLink: false }, { name: 'assets', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] }) as never)
  on('fs.read', (_, e) => (files[e.path] !== undefined ? { value: files[e.path] } : Promise.reject(new Error('ENOENT'))) as never)
  on('fs.write', (_, e) => {
    files[e.path] = e.text
    return { value: undefined } as never
  })
  on('model.complete', () => ({ value: { isAnswered: true, text: 'Grok wants cento options.\nFor Friday.\nBy Fri Oct 23.' } }) as never)
  on('command.run', () => ({ text: 'engine' }))
  const list = await $.command.run({ command: 'bridge-inbox', args: '' } as never)
  expect(list.text ?? '').toContain('G2C-2026-10-22-001 · from grok · harness · new  ★ NEEDS CHRIS: pick a cento')
  expect(list.text ?? '').toContain('Grok wants cento options.')
  expect(list.text ?? '').not.toContain('MOVED')
  await $.command.run({ command: 'bridge-inbox', args: 'ack G2C-2026-10-22-001' } as never)
  const after = files['/Users/c/Developer/grok-bridge/to-claude/G2C-2026-10-22-001-cento.md'] ?? ''
  expect(after).toContain('status: acked')
  expect(after).toContain('## Status log\n- 2026-10-22 16:05 ET | acked:')
  const archive = await $.command.run({ command: 'bridge-inbox', args: 'archive G2C-2026-10-22-001' } as never)
  expect(archive.text ?? '').toContain('Chris typing')
})
