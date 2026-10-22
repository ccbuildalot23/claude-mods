import { expect, mock, test } from 'claude-code/testing'

test('the status line counts down and /keepwarm arms only while warm', async ($, on) => {
  mock.store(on)
  on('command.run', () => ({ text: 'engine' }))
  const clock = mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  const status: (string | undefined)[] = []
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.complete', (_, e) => ({ text: e.answer }) as never)
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 120000 }, rateLimits: [] } }) as never)
  on('ui.status', (_, e) => {
    status.push((e as { text?: string }).text)
    return { value: undefined } as never
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const early = await $.command.run({ command: 'keepwarm', args: '' })
  expect(early.text ?? '').toContain('nothing to keep warm')
  await $.turn.complete({ answer: 'hi', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' } as never)
  expect(status.at(-1) ?? '').toContain('60m left')
  const warm = await $.command.run({ command: 'keepwarm', args: '' })
  expect(warm.text ?? '').toContain('Keeping this chat warm')
  await $.command.run({ command: 'keepwarm', args: 'off' })
  await clock.advance(61 * 60 * 1000)
  expect(status.at(-1) ?? '').toContain('cache cold (120k')
})

test('the status line reads the shared clock file and the usage windows', async ($, on) => {
  mock.store(on)
  // Wednesday Oct 21, 2026, 3:00 pm local: inside the Wed 2:30 to 4:00 window.
  mock.clock(on, { now: new Date('2026-10-21T15:00:00').getTime() })
  const status: (string | undefined)[] = []
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('fs.read', () => ({ value: JSON.stringify({ aiWindows: [{ days: ['mon', 'wed'], from: '14:30', to: '16:00' }], quietFrom: '17:00', quietTo: '08:40' }) }) as never)
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 1000 }, rateLimits: [{ kind: 'five_hour', percentUsed: 23.4 }, { kind: 'seven_day', percentUsed: 41 }] } }) as never)
  on('ui.status', (_, e) => {
    status.push((e as { text?: string }).text)
    return { value: undefined } as never
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(status.at(-1) ?? '').toBe('AI window open till 4:00pm · 5h 23% · week 41%')
})
