import { expect, mock, test } from 'claude-code/testing'

test('the panel tracks goal, connectors, skills, links and a file tree', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('tool.call', () => ({ result: {} }))
  on('prompt.submit', (_, e) => ({ text: e.text }))
  await $.prompt.submit({ text: 'Fix the caption queue' } as never)
  await $.tool.call({ tool: 'Read', file_path: '/w/a.md' })
  await $.tool.call({ tool: 'Edit', file_path: '/w/b.md', old_string: 'x', new_string: 'y' })
  await $.tool.call({ tool: 'Skill', skill: 'labeau-marketing' } as never)
  await $.tool.call({ tool: 'WebFetch', url: 'https://example.com', prompt: 'x' } as never)
  await $.tool.call({ tool: 'mcp__Gmail__search_threads', query: 'x' } as never)
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'chat-inventory', component: 'Pane', requestId: 'chat-inventory', props: { title: "x", isFocused: false, bodyColumns: 60, placement: "dock", scroll: { offset: 0, bodyRows: 40 }, view: {} }, surface })
    expect(await ui.find({ type: 'Text', text: /Fix the caption queue/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Gmail ×1/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /labeau-marketing/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /example.com/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /✓ b.md/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /· a.md/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /1 changed, 2 touched.*1 shell/ })).toBeDefined()
    await ui.unmount()
  }
})
