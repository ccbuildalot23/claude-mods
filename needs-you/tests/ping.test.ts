import { expect, mock, test } from 'claude-code/testing'

const CLOCK = JSON.stringify({ aiWindows: [], quietFrom: '17:00', quietTo: '08:40' })

test('pings in the day, holds in quiet hours, sums up after', async ($, on) => {
  mock.store(on)
  const clock = mock.clock(on, { now: new Date('2026-10-22T15:00:00').getTime() })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('fs.read', () => ({ value: CLOCK }) as never)
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.complete', (_, e) => ({ text: e.answer }) as never)
  const sent: string[] = []
  on('ui.notify', (_, e) => {
    sent.push(e.text)
    return { value: { isSent: true, channel: 'terminal' } } as never
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete({ answer: 'Built the outbox mod.\nDetails...', durationMs: 3 * 60000, isAborted: false, turnId: 't1', reason: 'answer' } as never)
  expect(sent[0] ?? '').toContain('Done after 3 min: Built the outbox mod.')
  await $.turn.complete({ answer: 'quick', durationMs: 2000, isAborted: false, turnId: 't2', reason: 'answer' } as never)
  expect(sent.length).toBe(1)
  await clock.advance(3 * 60 * 60 * 1000) // 6 pm: quiet
  await $.turn.complete({ answer: 'Nightly job finished.', durationMs: 5 * 60000, isAborted: false, turnId: 't3', reason: 'answer' } as never)
  expect(sent.length).toBe(1)
  await clock.advance(15 * 60 * 60 * 1000) // 9 am next day
  expect(sent[1] ?? '').toContain('While it was quiet: Done after 5 min: Nightly job finished.')
})
