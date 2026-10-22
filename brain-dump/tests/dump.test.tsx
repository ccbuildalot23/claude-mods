import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const RAMBLE = 'so um I was thinking we should plan the week and maybe call the printer about the zine, '.repeat(10)
const CODE = Array.from({ length: 40 }, (_, i) => `  const value${i} = compute(${i});`).join('\n')
const BAND = { plugin: 'brain-dump', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 80, scroll: { offset: 0, bodyRows: 10 }, view: {} }, surface: 'terminal' } as const
const PANE = { plugin: 'brain-dump', component: 'Pane', requestId: 'brain-dumps', props: { title: 'Brain dumps', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} }, surface: 'terminal' } as const

type World = { reached: string[]; files: Map<string, string>; filled: string[]; modelCalls: number }

function engine(on: On): World {
  const world: World = { reached: [], files: new Map(), filled: [], modelCalls: 0 }
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22, 20, 0, 0) })
  mock.env(on, { HOME: '/Users/chris' })
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('prompt.submit', (_, e) => {
    world.reached.push(e.text)
    return { text: e.text }
  })
  on('prompt.fill', (_, e) => {
    world.filled.push(e.text)
    return { isFilled: true }
  })
  on('fs.write', (_, e) => {
    world.files.set(e.path, e.text)
    return { value: undefined }
  })
  on('fs.exists', (_, e) => ({ value: world.files.has(e.path) }))
  on('fs.read', (_, e) => ({ value: world.files.get(e.path) ?? '' }) as never)
  on('fs.list', (_, e) => ({ value: [...world.files.keys()].filter(p => p.startsWith(e.path + '/')).map(p => ({ name: p.slice(e.path.length + 1), kind: 'file' as const, size: 1, mtimeMs: 1, isLink: false })) }))
  on('model.complete', () => {
    world.modelCalls += 1
    return { value: { isAnswered: true, text: 'Task: plan the week\nTo-dos:\n- [ ] call the printer', usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } } as never
  })
  return world
}

const composer = (text: string) => ({ text, origin: { kind: 'composer' } }) as never
const run = (command: string, args = '') => ({ command, args }) as never

test('on by default: a spoken ramble is held, pasted code passes, tidy offers Edit first', async ($, on) => {
  const world = engine(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  await $.prompt.submit(composer(CODE))
  expect(world.reached.length).toBe(1)

  const held = await $.prompt.submit(composer(RAMBLE))
  expect(String((held as { drop?: string }).drop ?? '')).toContain('Held')
  expect(world.reached.length).toBe(1)

  const band = await $.ui.mount(BAND)
  await band.press({ key: 'tidy' })
  expect(await band.find({ type: 'Text', text: /plan the week/ })).toBeDefined()
  await band.press({ key: 'edit' })
  expect(world.filled[0]).toContain('call the printer')
  await band.unmount()

  // The edited tidy prompt goes straight through, even though it is long.
  await $.prompt.submit(composer(RAMBLE + ' edited'))
  expect(world.reached.at(-1)).toBe(RAMBLE + ' edited')
})

test('a Private: dump never reaches Claude and lands in the Voice Inbox', async ($, on) => {
  const world = engine(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  const held = await $.prompt.submit(composer('Private: rough day, writing it down so I let it go.'))
  expect(String((held as { drop?: string }).drop ?? '')).toContain('not gone to Claude')
  const band = await $.ui.mount(BAND)
  await band.press({ key: 'vault' })
  await band.unmount()

  expect(world.reached.length).toBe(0)
  expect(world.modelCalls).toBe(0)
  const [path, text] = [...world.files.entries()][0] ?? ['', '']
  expect(path.startsWith('/Users/chris/Voice Inbox/braindump-')).toBe(true)
  expect(text).toBe('Private\n\nrough day, writing it down so I let it go.\n')
})

test('a Line: dump goes to the line bank inbox word for word', async ($, on) => {
  const world = engine(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  await $.prompt.submit(composer('Line: the moon kept my name in its pocket'))
  const band = await $.ui.mount(BAND)
  await band.press({ key: 'line' })
  await band.unmount()

  expect(world.reached.length).toBe(0)
  expect([...world.files.values()][0]).toBe('Line\n\nthe moon kept my name in its pocket\n')
})

test('Save for later and /braindump save fill the /dumps pane; Work on this fills the prompt', async ($, on) => {
  const world = engine(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  await $.command.run(run('braindump', 'save email the venue about Saturday'))
  await $.prompt.submit(composer(RAMBLE))
  const band = await $.ui.mount(BAND)
  await band.press({ key: 'later' })
  await band.unmount()
  expect(world.reached.length).toBe(0)
  expect([...world.files.keys()].every(p => p.startsWith('/Users/chris/Developer/claude-mods/brain-dump/inbox/dump-'))).toBe(true)

  await $.command.run(run('dumps'))
  const pane = await $.ui.mount(PANE)
  expect(await pane.find({ type: 'Text', text: /email the venue/ })).toBeDefined()
  const name = [...world.files.keys()].map(p => p.split('/').pop() ?? '').find(n => (world.files.get(`/Users/chris/Developer/claude-mods/brain-dump/inbox/${n}`) ?? '').includes('venue')) ?? ''
  await pane.press({ key: `work-${name}` })
  expect(world.filled.at(-1)).toBe('email the venue about Saturday')
  await pane.unmount()
})

test('/braindump off lets rambles through but still holds Private:', async ($, on) => {
  const world = engine(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.command.run(run('braindump', 'off'))
  await $.prompt.submit(composer(RAMBLE))
  await $.prompt.submit(composer('Line: passes when the catcher is off'))
  await $.prompt.submit(composer('Private: held even when the catcher is off'))
  expect(world.reached.length).toBe(2)
})
