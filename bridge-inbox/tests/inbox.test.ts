import { expect, mock, test } from 'claude-code/testing'

// The start-of-session pass runs in the background; let it land before reading what it wrote.
const settle = () => new Promise(r => setTimeout(r, 20))

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
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/Users/c' : undefined }) as never)
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
  expect(archive.text ?? '').toContain('only done or rejected messages are archived')
})

const NEW2 = MSG.replace('G2C-2026-10-22-001', 'G2C-2026-10-23-004').replace('needs_chris: yes - pick a cento', 'needs_chris: no')
const PENDING = '{"table": "Changes", "date_et": "2026-10-21 19:53 ET", "system": "Mac", "component": "plugins", "summary": "Built mods", "made_by": "Claude Code", "status": "Proposed", "risk": "Low"}\n{"table": "Glitches & Security", "title": "left for Grok"}\n'

function bridge(on: Parameters<Parameters<typeof test>[1]>[1], airtableUp: boolean) {
  mock.store(on)
  mock.clock(on, { now: new Date('2026-10-24T01:43:00').getTime() })
  const B = '/Users/c/Developer/grok-bridge'
  const files: Record<string, string> = {
    [`${B}/to-claude/G2C-2026-10-22-001-cento.md`]: MSG,
    [`${B}/to-claude/G2C-2026-10-23-004-ack.md`]: NEW2,
    [`${B}/to-claude/G2C-2026-10-22-003-v1.md`]: '# G2C-2026-10-22-003 recap\n\n## Status log\n- 2026-10-24 01:51 ET | acked: read.\n',
    [`${B}/status/claude.json`]: '{"agent":"claude-code","bridge":"v2.1","protocol_version_read":"2.1"}',
    [`${B}/status/airtable-pending.jsonl`]: PENDING,
  }
  const calls: { tool: string; args: Record<string, unknown> }[] = []
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/Users/c' : undefined }) as never)
  on('fs.exists', (_, e) => ({ value: e.path === `${B}/to-claude` }) as never)
  on('fs.list', () => ({ value: Object.keys(files).filter(f => f.includes('/to-claude/')).map(f => ({ name: f.split('/').pop(), kind: 'file', size: 1, mtimeMs: 0, isLink: false })) }) as never)
  on('fs.read', (_, e) => (files[e.path] !== undefined ? { value: files[e.path] } : Promise.reject(new Error('ENOENT'))) as never)
  on('fs.write', (_, e) => {
    files[e.path] = e.text
    return { value: undefined } as never
  })
  on('mcp.call', (_, e) => {
    calls.push({ tool: e.tool, args: e.args })
    if (!airtableUp) return { value: { content: [{ type: 'text', text: 'not connected' }], isError: true } } as never
    const text = e.tool === 'list_records_for_table' ? JSON.stringify({ records: [{ cellValuesByFieldId: { fldZGoN8bgtXR2QsH: 'CHG-2026-10-21-008' } }] }) : '{}'
    return { value: { content: [{ type: 'text', text }], isError: false } } as never
  })
  on('ui.toast', () => ({ value: undefined }) as never)
  on('command.register', () => ({ value: {} }) as never)
  on('session.start', (_, e) => e as never)
  on('command.run', () => ({ text: 'engine' }))
  on('prompt.submit', (_, e) => ({ text: e.text, context: e.context }) as never)
  return { B, files, calls }
}

test('session start acks new messages, writes claude.json, updates the heartbeat and flushes Changes rows', async ($, on) => {
  const { B, files, calls } = bridge(on, true)
  await $.session.start({ cwd: '/Users/c' } as never)
  await settle()
  expect(files[`${B}/to-claude/G2C-2026-10-23-004-ack.md`]).toContain('status: acked')
  expect(files[`${B}/to-claude/G2C-2026-10-23-004-ack.md`]).toContain('- 2026-10-24 01:43 ET | acked: surfaced to Claude Code at session start')
  const status = JSON.parse(files[`${B}/status/claude.json`] ?? '{}')
  expect(status.last_session_et).toBe('2026-10-24 01:43 ET')
  expect(status.open_to_claude).toBe(0)
  expect(files[`${B}/to-claude/G2C-2026-10-22-003-v1.md`]).toBe('# G2C-2026-10-22-003 recap\n\n## Status log\n- 2026-10-24 01:51 ET | acked: read.\n')
  expect(status.airtable).toBe('ok')
  const created = calls.find(c => c.tool === 'create_records_for_table')
  const fields = (created?.args.records as { fields: Record<string, unknown> }[])[0]?.fields ?? {}
  expect(fields.fldZGoN8bgtXR2QsH).toBe('CHG-2026-10-21-009')
  expect(fields.fld1pc0ECZV4nQHsw).toBe('2026-10-21T23:53:00.000Z')
  const beat = calls.find(c => c.tool === 'update_records_for_table')
  expect(JSON.stringify(beat?.args)).toContain('recWWUogyPRP3JLga')
  expect(files[`${B}/status/airtable-pending.jsonl`]).toBe('{"table": "Glitches & Security", "title": "left for Grok"}\n')
  const sent = (await $.prompt.submit({ text: 'hi', wait: false } as never)) as unknown as { context?: string[] }
  expect(sent.context?.[0] ?? '').toContain('G2C-2026-10-22-001 from grok (harness), needs Chris: pick a cento')
  const again = (await $.prompt.submit({ text: 'next', wait: false } as never)) as unknown as { context?: string[] }
  expect(again.context ?? []).toHaveLength(0)
})

test('with Airtable unreachable the heartbeat is queued and claude.json says pending', async ($, on) => {
  const { B, files } = bridge(on, false)
  await $.session.start({ cwd: '/Users/c' } as never)
  await settle()
  expect(JSON.parse(files[`${B}/status/claude.json`] ?? '{}').airtable).toBe('pending')
  const queued = files[`${B}/status/airtable-pending.jsonl`] ?? ''
  expect(queued).toContain('"table": "Changes"')
  expect(queued).toContain('"table":"Agent Heartbeats"')
})

test('no bridge folder (a cloud session) means no writes', async ($, on) => {
  mock.store(on)
  const writes: string[] = []
  on('env.get', () => ({ value: '/home/user' }) as never)
  on('fs.exists', () => ({ value: false }) as never)
  on('fs.write', (_, e) => {
    writes.push(e.path)
    return { value: undefined } as never
  })
  on('command.register', () => ({ value: {} }) as never)
  on('session.start', (_, e) => e as never)
  on('command.run', () => ({ text: 'engine' }))
  await $.session.start({ cwd: '/Users/c' } as never)
  await settle()
  expect(writes).toHaveLength(0)
})
