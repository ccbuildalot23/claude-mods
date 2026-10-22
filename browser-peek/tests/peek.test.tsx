import { expect, mock, test } from 'claude-code/testing'

test('/peek runs headless Chrome with a fresh profile and opens the panel', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  on('command.run', () => ({ text: 'engine' }))
  let argv: readonly string[] = []
  on('fs.exists', () => ({ value: true }))
  mock.env(on, { HOME: '/Users/c' })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argv = (e as { argv: readonly string[] }).argv
    return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  const r = await $.command.run({ command: 'peek', args: 'example.com' })
  expect(r.text ?? '').toContain('Captured https://example.com')
  expect(argv.join(' ')).toContain('--headless=new')
  expect(argv.join(' ')).toContain('--user-data-dir=')
  expect(argv.includes('--no-sandbox')).toBe(false)
  expect(argv[0]).toContain('Google Chrome')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'browser-peek', component: 'Pane', requestId: 'browser-peek', props: { title: "x", isFocused: false, bodyColumns: 60, placement: "dock", scroll: { offset: 0, bodyRows: 40 }, view: {} }, surface })
    expect(await ui.find({ type: 'Text', text: /example.com/ })).toBeDefined()
    await ui.unmount()
  }
})

test('in a cloud session it falls back to the bundled Chromium without the sandbox', async ($, on) => {
  mock.store(on)
  mock.clock(on, { now: Date.UTC(2026, 9, 22) })
  mock.env(on, { HOME: '/root' })
  let argv: readonly string[] = []
  on('fs.exists', (_, e) => ({ value: e.path === '/opt/pw-browsers/chromium' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argv = (e as { argv: readonly string[] }).argv
    return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  await $.command.run({ command: 'peek', args: 'https://example.com' })
  expect(argv[0]).toBe('/opt/pw-browsers/chromium')
  expect(argv.includes('--no-sandbox')).toBe(true)
})
