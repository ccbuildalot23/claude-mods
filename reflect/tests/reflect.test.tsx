import { expect, mock, test } from 'claude-code/testing'

test('a lasting rule is spotted and saved to the rules inbox', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const written: Record<string, string> = {}
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('fs.read', (_, e) => (written[e.path] !== undefined ? { value: written[e.path] } : Promise.reject(new Error('ENOENT'))) as never)
  on('fs.write', (_, e) => {
    written[e.path] = e.text
    return { value: undefined } as never
  })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('ui.toast', () => ({ value: undefined }) as never)
  await $.prompt.submit({ text: 'Thanks. From now on, always write the full caption yourself.' } as never)
  const band = await $.ui.mount({ plugin: 'reflect', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: /full caption/ })).toBeDefined()
  await band.press({ key: 'save' })
  await band.unmount()
  const inbox = written['/Users/c/Developer/claude-mods/rules-inbox.md'] ?? ''
  expect(inbox).toContain('always write the full caption')
  await $.prompt.submit({ text: 'what time is it in Tokyo' } as never)
  const quiet = await $.ui.mount({ plugin: 'reflect', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await quiet.find({ type: 'Button', key: 'save' })).toBeUndefined()
  await quiet.unmount()
})

test('a rule given twice, unchanged, is offered for promotion into CLAUDE.md', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const written: Record<string, string> = {
    '/Users/c/Developer/claude-mods/rules-inbox.md': '# Rules inbox\n\n- 2026-10-20 | Always write the full caption yourself.\n',
    '/Users/c/.claude/CLAUDE.md': '# Chris\n',
  }
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('fs.read', (_, e) => (written[e.path] !== undefined ? { value: written[e.path] } : Promise.reject(new Error('ENOENT'))) as never)
  on('fs.write', (_, e) => {
    written[e.path] = e.text
    return { value: undefined } as never
  })
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('ui.toast', () => ({ value: undefined }) as never)
  await $.prompt.submit({ text: 'Thanks. Always write the full caption yourself!' } as never)
  const band = await $.ui.mount({ plugin: 'reflect', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: /given this rule twice/ })).toBeDefined()
  await band.press({ key: 'promote' })
  await band.unmount()
  expect(written['/Users/c/.claude/CLAUDE.md'] ?? '').toContain('## Rules promoted from the inbox')
  expect(written['/Users/c/.claude/CLAUDE.md'] ?? '').toContain('Always write the full caption yourself! (promoted 2026-10-22)')
  expect(written['/Users/c/Developer/claude-mods/rules-inbox.md'] ?? '').toContain('[promoted]')
})
