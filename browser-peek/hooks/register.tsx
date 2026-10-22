import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const PANE = 'browser-peek'
const peek = atom({ plugin: 'browser-peek', key: 'peek' } as const, { url: '', file: '', shotAt: 0, error: '' })

async function shoot($: EngineInterface, chrome: string, url: string): Promise<void> {
  const now = await $.clock.now()
  const file = `/tmp/browser-peek-${now}.png`
  const profile = `/tmp/browser-peek-profile`
  try {
    const r = await $.process.run(
      [chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', `--user-data-dir=${profile}`, '--window-size=1280,900', `--screenshot=${file}`, url],
      { timeoutMs: 45000 },
    )
    await update($, peek, () => ({ url, file, shotAt: now, error: r.exitCode === 0 ? '' : r.stderr.slice(0, 300) }))
  } catch (err) {
    await update($, peek, () => ({ url, file: '', shotAt: now, error: String(err).slice(0, 300) }))
  }
}

export const register: Register = (on, options) => {
  const chrome = typeof options.chromePath === 'string' && options.chromePath.length > 0 ? options.chromePath : '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'peek', description: 'Screenshot a web page into a panel: /peek https://...', argumentHint: 'URL' })
    return next(e)
  })

  on('command.run', { command: 'peek' }, async ($, e) => {
    const raw = e.args.trim()
    const url = /^(https?:|file:)/.test(raw) ? raw : raw.length > 0 ? `https://${raw}` : (await read($, peek)).url
    if (url.length === 0) return { text: 'Give me a page: /peek https://example.com' }
    await shoot($, chrome, url)
    await $.ui.open({ id: PANE, title: `Peek: ${url.slice(0, 60)}` })
    const p = await read($, peek)
    return { text: p.error.length > 0 ? `Could not capture ${url}: ${p.error}` : `Captured ${url} (${p.file}).` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const p = await read($, peek)
    if (e.surface === 'terminal') {
      const { Box, Text, Button, Image } = $.ui.resolve(e)
      const cols = Math.max(20, Math.min(255, e.props.bodyColumns))
      const rows = Math.max(8, Math.min(255, Math.round(cols * 0.35)))
      return (
        <Box flexDirection="column">
          <Text dimColor>{p.url}</Text>
          {p.file.length > 0 && p.error.length === 0 && <Image source={{ file: p.file, format: 'png', generation: p.shotAt }} columns={cols} rows={rows} alt={`Screenshot of ${p.url}`} />}
          {p.error.length > 0 && <Text color="red">{p.error}</Text>}
          <Button key="again" label="Refresh" onPress={() => shoot($, chrome, p.url)} />
        </Box>
      )
    }
    const { Box, Text, Button } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        <Text dimColor>{p.url}</Text>
        <Text>{p.error.length > 0 ? p.error : `Screenshot saved: ${p.file} (pictures draw in the terminal app)`}</Text>
        <Button key="again" label="Refresh" onPress={() => shoot($, chrome, p.url)} />
      </Box>
    )
  })
}
