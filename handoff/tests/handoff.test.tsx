import { expect, mock, test } from 'claude-code/testing'

test('/handoff writes the fork model reply to the handoffs folder', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  const written: Record<string, string> = {}
  on('model.fork', () => ({ value: { isAnswered: true, text: '1. Goal: ship captions', usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } }) as never)
  on('fs.write', (_, e) => {
    written[e.path] = e.text
    return { value: undefined } as never
  })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  const r = await $.command.run({ command: 'handoff', args: '' })
  const path = Object.keys(written)[0] ?? ''
  expect(path.startsWith('/Users/c/Developer/claude-mods/handoffs/handoff-')).toBe(true)
  expect(written[path]).toContain('ship captions')
  expect(r.text ?? '').toContain(path)
  const band = await $.ui.mount({ plugin: 'handoff', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Button', key: 'copy' })).toBeDefined()
  await band.unmount()
})

test('past 250k tokens the band offers a handoff', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('turn.complete', (_, e) => ({ text: e.answer }) as never)
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 260000 }, rateLimits: [] } }) as never)
  await $.turn.complete({ answer: 'hi', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' } as never)
  const band = await $.ui.mount({ plugin: 'handoff', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: /past 260k tokens/ })).toBeDefined()
  await band.unmount()
})
