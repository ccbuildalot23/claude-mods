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
