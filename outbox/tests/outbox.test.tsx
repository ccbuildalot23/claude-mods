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
  expect((await $.tool.call({ tool: 'mcp__hearthbot__no_reply_needed', reason: 'nothing_to_add' } as never)).deny).toBeUndefined()
  expect((await $.tool.call({ tool: 'Bash', command: 'git push origin main' })).deny ?? '').toContain('git push')
  expect((await $.tool.call({ tool: 'Bash', command: 'git commit -m "notes about git push"' })).deny).toBeUndefined()
  expect(ran).toBe(4)

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

test('in the desktop app Chris says yes on the spot, and a release from there goes through the dialog', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 10, 24, 6) })
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/Users/c' : undefined }) as never)
  on('fs.write', () => ({ value: undefined }) as never)
  on('session.surfaces', () => ({ value: ['desktop'] }) as never)
  let answer = 'Keep it held'
  let asked = 0
  let ran = 0
  on('tool.call', (_, e) => {
    if (e.tool === 'AskUserQuestion') {
      asked += 1
      return { result: { questions: e.questions, answers: { [e.questions[0]?.question ?? '']: answer } } }
    }
    ran += 1
    return { result: {} }
  })
  const push = { tool: 'Bash', command: 'git push origin main' } as const
  const held = await $.tool.call(push)
  expect(held.deny ?? '').toContain('Held in the Outbox')
  expect(asked).toBe(1)
  expect(ran).toBe(0)
  const id = /OB-[0-9a-f]+/.exec(held.deny ?? '')?.[0] ?? ''

  // A release typed in the desktop app arrives as the SDK's: the dialog decides.
  expect((await $.command.run({ command: 'outbox', args: `release ${id}`, origin: { kind: 'sdk' } } as never)).text).toContain('still held')
  answer = 'Release once'
  expect((await $.command.run({ command: 'outbox', args: `release ${id}`, origin: { kind: 'sdk' } } as never)).text).toContain('released once')
  expect((await $.tool.call(push)).deny).toBeUndefined()
  expect(ran).toBe(1)

  answer = 'Send once'
  expect((await $.tool.call({ tool: 'mcp__Gmail__send_message', to: 'a@b.c', body: 'hi' } as never)).deny).toBeUndefined()
  expect(ran).toBe(2)
})

test('with nobody watching (a -p or scheduled run) nothing asks and the hold stands', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 10, 24, 6) })
  on('env.get', () => ({ value: undefined }) as never)
  on('fs.write', () => ({ value: undefined }) as never)
  on('session.surfaces', () => ({ value: [] }) as never)
  let asked = 0
  on('tool.call', (_, e) => {
    if (e.tool === 'AskUserQuestion') asked += 1
    return { result: {} }
  })
  expect((await $.tool.call({ tool: 'Bash', command: 'git push origin main' })).deny ?? '').toContain('Held')
  expect(asked).toBe(0)
})
