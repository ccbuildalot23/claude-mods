import { expect, mock, test } from 'claude-code/testing'

const BAND = { plugin: 'helper-desk', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} } } as const

test('the progress bar fills as to-dos are ticked', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('tool.call', () => ({ result: {} }))
  await $.tool.call({ tool: 'TodoWrite', todos: [
    { content: 'One', activeForm: 'Doing one', status: 'completed' },
    { content: 'Two', activeForm: 'Doing two', status: 'in_progress' },
    { content: 'Three', activeForm: 'Doing three', status: 'pending' },
  ] })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.find({ type: 'Text', text: /1\/3/ }))?.text ?? '').toContain('█')
    expect(await ui.find({ type: 'Text', text: /Doing two/ })).toBeDefined()
    await ui.unmount()
  }
})

test('a subagent shows in the helpers panel with its tokens', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('agent.spawn', () => ({ model: 'haiku', agentId: 'a1' }))
  on('turn.complete', (_, e) => ({ text: e.answer }) as never)
  await $.agent.spawn({ prompt: 'look', description: 'Scan the repo', subagentType: 'Explore' })
  await $.turn.complete({ answer: 'done', durationMs: 5, isAborted: false, turnId: 't', agentId: 'a1', reason: 'answer', usage: { input_tokens: 10000, output_tokens: 2000, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } as never)
  const ui = await $.ui.mount({ plugin: 'helper-desk', component: 'Pane', requestId: 'helper-desk', props: { title: "x", isFocused: false, bodyColumns: 60, placement: "dock", scroll: { offset: 0, bodyRows: 40 }, view: {} }, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /Scan the repo/ }))?.text ?? '').toContain('done')
  expect(await ui.find({ type: 'Text', text: /12k tokens/ })).toBeDefined()
  await ui.unmount()
})
