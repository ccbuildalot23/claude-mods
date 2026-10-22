import { expect, mock, test } from 'claude-code/testing'

const BAND = { plugin: 'crew', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} } } as const
const PANE = { plugin: 'crew', component: 'Pane', requestId: 'crew', props: { title: 'Crew', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} } } as const

function engine(on: Parameters<Parameters<typeof test>[1]>[1]) {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('tool.call', () => ({ result: {} }))
  on('turn.complete', (_, e) => ({ text: e.answer }) as never)
  let n = 0
  on('agent.spawn', () => ({ model: 'haiku', agentId: `a${++n}` }))
}

test('each subagent gets its own character and color, and shows what it is doing', async ($, on) => {
  engine(on)
  await $.agent.spawn({ prompt: 'look', description: 'Scan the repo', subagentType: 'Explore' })
  await $.agent.spawn({ prompt: 'test', description: 'Run the tests' })
  await $.tool.call({ tool: 'Read', file_path: '/repo/README.md', agentId: 'a1' } as never)
  await $.tool.call({ tool: 'Bash', command: 'npm test', description: 'Run unit tests', agentId: 'a2' } as never)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    const ember = await ui.find({ type: 'Text', text: /Ember/ })
    const sage = await ui.find({ type: 'Text', text: /Sage/ })
    expect(ember?.text ?? '').toContain('🦊')
    expect(sage?.text ?? '').toContain('🦉')
    expect(ember?.props.color).not.toBe(sage?.props.color)
    expect(await ui.find({ type: 'Text', text: /Reading README\.md/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Run unit tests/ })).toBeDefined()
    await ui.unmount()
  }
})

test("a subagent's own to-do list becomes its progress bar", async ($, on) => {
  engine(on)
  await $.agent.spawn({ prompt: 'fix', description: 'Fix the bug' })
  await $.tool.call({ tool: 'TodoWrite', agentId: 'a1', todos: [
    { content: 'Find it', activeForm: 'Finding it', status: 'completed' },
    { content: 'Fix it', activeForm: 'Fixing it', status: 'in_progress' },
  ] } as never)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /1\/2/ }))?.text ?? '').toContain('█')
  expect(await ui.find({ type: 'Text', text: /Fixing it/ })).toBeDefined()
  await ui.unmount()
})

test('a finished subagent shows done in the panel', async ($, on) => {
  engine(on)
  await $.agent.spawn({ prompt: 'look', description: 'Scan the repo' })
  await $.turn.complete({ answer: 'ok', durationMs: 5, isAborted: false, turnId: 't', agentId: 'a1', reason: 'answer' } as never)
  const pane = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await pane.find({ type: 'Text', text: /0 working · 1 finished/ })).toBeDefined()
  expect((await pane.find({ type: 'Text', text: /Ember/ }))?.text ?? '').toContain('done')
  expect(await pane.find({ type: 'Text', text: /Scan the repo/ })).toBeDefined()
  await pane.unmount()
})
