import { expect, mock, test } from 'claude-code/testing'

test('/screenshare masks messages and hides tool details, off restores them', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{'text' in e.props ? String(e.props.text) : 'engine'}</Text>
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.command.run({ command: 'screenshare', args: 'add Dana Smith' })
  const on1 = await $.command.run({ command: 'screenshare', args: 'on' })
  expect(on1.text ?? '').toContain('on')
  const msg = await $.ui.mount({ plugin: 'screen-share', surface: 'terminal', component: 'AssistantMessage', props: { text: 'Dana Smith owes $4,200, email dana@x.com' } as never })
  const shown = (await msg.find({ type: 'Text' }))?.text ?? ''
  expect(shown.includes('Dana Smith')).toBe(false)
  expect(shown.includes('4,200')).toBe(false)
  expect(shown.includes('dana@x.com')).toBe(false)
  await msg.unmount()
  await $.command.run({ command: 'screenshare', args: 'off' })
  const msg2 = await $.ui.mount({ plugin: 'screen-share', surface: 'terminal', component: 'AssistantMessage', props: { text: 'Dana Smith owes $4,200' } as never })
  expect((await msg2.find({ type: 'Text' }))?.text ?? '').toContain('Dana Smith')
  await msg2.unmount()
})
