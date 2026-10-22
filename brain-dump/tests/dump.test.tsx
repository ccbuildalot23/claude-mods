import { expect, mock, test } from 'claude-code/testing'

const LONG = 'so um I was thinking we should '.repeat(40)

test('off by default; when on, a long dump is held and tidy is offered', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  let reached = 0
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('prompt.submit', (_, e) => {
    reached += 1
    return { text: e.text }
  })
  on('model.complete', () => ({ value: { isAnswered: true, text: 'Task: plan the week', usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } }) as never)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.prompt.submit({ text: LONG, origin: { kind: 'composer' } } as never)
  expect(reached).toBe(1)
  await $.command.run({ command: 'braindump', args: 'on' })
  const held = await $.prompt.submit({ text: LONG, origin: { kind: 'composer' } } as never)
  expect(String((held as { drop?: string }).drop ?? '')).toContain('Held')
  expect(reached).toBe(1)
  const band = await $.ui.mount({ plugin: 'brain-dump', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  await band.press({ key: 'tidy' })
  expect(await band.find({ type: 'Text', text: /plan the week/ })).toBeDefined()
  await band.unmount()
})
