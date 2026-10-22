import { expect, mock, test } from 'claude-code/testing'

test('/lightweek adds essentials-only guidance to every prompt until it ends', async ($, on) => {
  mock.store(on)
  const clock = mock.clock(on, { now: Date.UTC(2026, 9, 22, 18) })
  const files: Record<string, string> = {}
  on('env.get', () => ({ value: '/Users/c' }) as never)
  on('fs.read', (_, e) => (files[e.path] !== undefined ? { value: files[e.path] } : Promise.reject(new Error('ENOENT'))) as never)
  on('fs.write', (_, e) => {
    files[e.path] = e.text
    return { value: undefined } as never
  })
  on('command.run', () => ({ text: 'engine' }))
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'You are Claude.', scope: 'shared' }] }) as never)
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const before = await $.prompt.compose({ model: 'claude-test', promptModel: 'claude-test', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [] } as never)
  expect(before.sections.length).toBe(1)
  const r = await $.command.run({ command: 'lightweek', args: '' } as never)
  expect(r.text ?? '').toContain('7 days')
  expect(files['/Users/c/Developer/claude-mods/config/lightweek.json'] ?? '').toContain('"days": 7')
  const during = await $.prompt.compose({ model: 'claude-test', promptModel: 'claude-test', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [] } as never)
  expect(during.sections.at(-1)?.text ?? '').toContain('Keep to essentials')
  const band = await $.ui.mount({ plugin: 'lightweek', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: /7 days left/ })).toBeDefined()
  await band.unmount()
  await clock.advance(8 * 24 * 60 * 60 * 1000)
  const after = await $.prompt.compose({ model: 'claude-test', promptModel: 'claude-test', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [] } as never)
  expect(after.sections.length).toBe(1)
})
