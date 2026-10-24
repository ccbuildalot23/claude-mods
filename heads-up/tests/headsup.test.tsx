import { expect, mock, test } from 'claude-code/testing'

// The note is written in the background after the turn ends; let it land.
const settle = () => new Promise(r => setTimeout(r, 5))

test('a long reply gets a you-should-know note; short ones and NONE do not', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  let calls = 0
  let reply = '- Costs $40 a month'
  on('turn.complete', (_, e) => ({ text: e.answer }) as never)
  on('ui.toast', () => ({ value: undefined }) as never)
  on('model.complete', () => {
    calls += 1
    return { value: { isAnswered: true, text: reply, usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } } as never
  })
  await $.turn.complete({ answer: 'short', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' } as never)
  expect(calls).toBe(0)
  await $.turn.complete({ answer: 'x'.repeat(1500), durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' } as never)
  await settle()
  expect(calls).toBe(1)
  const band = await $.ui.mount({ plugin: 'heads-up', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: /\$40 a month/ })).toBeDefined()
  await band.press({ key: 'ok' })
  await band.unmount()
  reply = 'NONE'
  await $.turn.complete({ answer: 'y'.repeat(1500), durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' } as never)
  await settle()
  const quiet = await $.ui.mount({ plugin: 'heads-up', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await quiet.find({ type: 'Button', key: 'ok' })).toBeUndefined()
  await quiet.unmount()
})
