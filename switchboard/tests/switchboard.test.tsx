import { expect, mock, test } from 'claude-code/testing'

const PANE = { plugin: 'switchboard', component: 'Pane', requestId: 'switchboard', props: { title: "x", isFocused: false, bodyColumns: 60, placement: "dock", scroll: { offset: 0, bodyRows: 40 }, view: {} } } as const

test('/mods opens the panel, toggles a mod through its own command, and blast-radius stays locked', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  const ran: string[] = []
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('command.run', (_, e) => {
    ran.push(`${e.command} ${e.args}`)
    return { text: 'ok' }
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const opened = await $.command.run({ command: 'mods', args: '' })
  expect(opened.text ?? '').toContain('Switchboard')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /LOCKED ON/ }))?.text ?? '').toContain('blast-radius')
    expect(await ui.find({ type: 'Button', key: 't:blast-radius' })).toBeUndefined()
    await ui.unmount()
  }
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 't:heads-up' })
  expect(ran).toContain('headsup off')
  await ui.press({ key: 't:heads-up' })
  expect(ran).toContain('headsup on')
  await ui.unmount()
})

