import { expect, mock, test } from 'claude-code/testing'

test('every call is logged before it runs, keys are masked, and a failed log stops the call', async ($, on) => {
  mock.clock(on, { now: new Date('2026-10-22T16:05:09').getTime() })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('session.id', () => ({ value: 'abcdef1234' }) as never)
  const lines: string[] = []
  let canWrite = true
  on('process.run', (_, e) => {
    lines.push(String(e.argv[4]))
    return { value: { exitCode: canWrite ? 0 : 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } } as never
  })
  let ran = 0
  on('tool.call', () => {
    ran += 1
    return { result: {} }
  })
  await $.tool.call({ tool: 'Bash', command: 'curl -H "x-api-key: sk-ant-abcdefghijklmnop1234" https://example.com' })
  expect(ran).toBe(1)
  expect(lines[0] ?? '').toContain('16:05:09 abcdef12 main Bash:')
  expect(lines[0] ?? '').toContain('[key]')
  expect(lines[0] ?? '').not.toContain('abcdefghijklmnop1234')
  expect(lines[1] ?? '').toContain('ran')
  await $.tool.call({ tool: 'Write', file_path: '/Users/c/notes.md', content: 'secret diary text' })
  expect(lines[2] ?? '').toContain('/Users/c/notes.md')
  expect(lines.join('\n')).not.toContain('diary')
  canWrite = false
  const r = await $.tool.call({ tool: 'Bash', command: 'ls' })
  expect(r.deny ?? '').toContain('fail closed')
  expect(ran).toBe(2)
})
