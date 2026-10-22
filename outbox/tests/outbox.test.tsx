import { expect, mock, test } from 'claude-code/testing'

test('sends and pushes are held until Chris releases them; drafts and reads pass', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22, 20) })
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/Users/c' : undefined }) as never)
  on('fs.write', () => ({ value: undefined }) as never)
  on('command.run', () => ({ text: 'engine' }))
  let ran = 0
  on('tool.call', () => {
    ran += 1
    return { result: {} }
  })
  const post = { tool: 'mcp__Blotato__blotato_create_post', accountId: 'a1', text: 'hello' } as never
  const held = await $.tool.call(post)
  expect(held.deny ?? '').toContain('Held in the Outbox')
  const id = /OB-[0-9a-f]+/.exec(held.deny ?? '')?.[0] ?? ''
  expect((await $.tool.call({ tool: 'mcp__Gmail__create_draft', to: 'x@y.z', body: 'hi' } as never)).deny).toBeUndefined()
  expect((await $.tool.call({ tool: 'mcp__Blotato__blotato_list_posts' } as never)).deny).toBeUndefined()
  expect((await $.tool.call({ tool: 'Bash', command: 'git push origin main' })).deny ?? '').toContain('git push')
  expect((await $.tool.call({ tool: 'Bash', command: 'git commit -m "notes about git push"' })).deny).toBeUndefined()
  expect(ran).toBe(3)

  const band = await $.ui.mount({ plugin: 'outbox', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' })
  expect(await band.find({ type: 'Text', text: /2 held/ })).toBeDefined()
  await band.unmount()

  expect((await $.command.run({ command: 'outbox', args: `release ${id}` } as never)).text).toContain('must come from Chris')
  expect((await $.command.run({ command: 'outbox', args: `release ${id}`, origin: { kind: 'composer' } } as never)).text).toContain('released once')
  expect((await $.tool.call(post)).deny).toBeUndefined()
  expect((await $.tool.call(post)).deny ?? '').toContain('Held')
})

test('in a cloud session a push to a claude/ review branch passes', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22, 20) })
  on('env.get', (_, e) => ({ value: e.name === 'CLAUDE_CODE_REMOTE' ? 'true' : '/root' }) as never)
  on('fs.write', () => ({ value: undefined }) as never)
  on('tool.call', () => ({ result: {} }))
  expect((await $.tool.call({ tool: 'Bash', command: 'git push -u origin claude/project-thread-x' })).deny).toBeUndefined()
  expect((await $.tool.call({ tool: 'Bash', command: 'git push origin main' })).deny ?? '').toContain('Held')
})
