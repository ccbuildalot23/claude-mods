import { expect, mock, test } from 'claude-code/testing'

const TOOL = { tool: 'Bash', input: { command: 'ls -la' }, isRunning: false, isErrored: false, isInterrupted: false, isExpanded: false }

test('tool calls get an icon per skin, and off hands back the stock look', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>stock</Text>
  })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'skins', component: 'ToolUse', props: TOOL as never, surface })
    expect((await ui.find({ type: 'Text', text: /❯ Bash/ }))?.text ?? '').toContain('ls -la')
    await ui.unmount()
  }
  await $.command.run({ command: 'skin', args: 'off' })
  const ui = await $.ui.mount({ plugin: 'skins', component: 'ToolUse', props: TOOL as never, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /stock/ })).toBeDefined()
  await ui.unmount()
})
