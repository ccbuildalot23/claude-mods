import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { SkinName } from '../types'

const skin = atom({ plugin: 'skins', key: 'skin' } as const, 'labeau')

type Theme = { read: string; write: string; shell: string; web: string; agent: string; mcp: string; other: string; words: string[] }

const THEMES: Record<Exclude<SkinName, 'off'>, Theme> = {
  labeau: { read: 'magenta', write: 'yellow', shell: 'cyan', web: 'blue', agent: 'magenta', mcp: 'green', other: 'white', words: ['Gathering', 'Listening', 'Weaving', 'Tending', 'Arranging'] },
  noir: { read: 'gray', write: 'white', shell: 'gray', web: 'white', agent: 'white', mcp: 'gray', other: 'gray', words: ['Investigating', 'Tailing', 'Piecing together', 'Working the case'] },
  tokyo: { read: 'blue', write: 'magenta', shell: 'cyan', web: 'blue', agent: 'magenta', mcp: 'cyan', other: 'blue', words: ['Compiling', 'Routing', 'Syncing', 'Rendering'] },
}

function kind(tool: string): { icon: string; slot: keyof Omit<Theme, 'words'> } {
  if (tool === 'Read' || tool === 'Glob' || tool === 'Grep') return { icon: '◉', slot: 'read' }
  if (tool === 'Write' || tool === 'Edit' || tool === 'NotebookEdit') return { icon: '✎', slot: 'write' }
  if (tool === 'Bash') return { icon: '❯', slot: 'shell' }
  if (tool === 'WebFetch' || tool === 'WebSearch') return { icon: '☁', slot: 'web' }
  if (tool === 'Agent' || tool === 'Task') return { icon: '✦', slot: 'agent' }
  if (tool.startsWith('mcp__')) return { icon: '⦿', slot: 'mcp' }
  return { icon: '•', slot: 'other' }
}

function summary(input: unknown): string {
  if (typeof input !== 'object' || input === null) return ''
  const r = input as Record<string, unknown>
  const v = r.file_path ?? r.command ?? r.url ?? r.query ?? r.pattern ?? r.description ?? r.prompt
  return typeof v === 'string' ? v.split('\n')[0]?.slice(0, 100) ?? '' : ''
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'skin', description: 'Change how tool calls look: /skin labeau | noir | tokyo | off', argumentHint: 'labeau|noir|tokyo|off', immediate: true })
    const saved = await $.store.get('skin')
    if (saved === 'labeau' || saved === 'noir' || saved === 'tokyo' || saved === 'off') await update($, skin, () => saved)
    return next(e)
  })

  on('command.run', { command: 'skin' }, async ($, e) => {
    const want = e.args.trim().toLowerCase()
    const pick: SkinName = want === 'noir' || want === 'tokyo' || want === 'off' ? want : 'labeau'
    await update($, skin, () => pick)
    await $.store.set('skin', pick)
    $.ui.invalidate('ui.render')
    return { text: pick === 'off' ? 'Skins off.' : `Skin set to ${pick}.` }
  })

  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    const s = await read($, skin)
    if (s === 'off' || e.props.isExpanded === true || e.props.isErrored || e.props.isInterrupted) return next(e)
    const theme = THEMES[s]
    const { icon, slot } = kind(e.props.tool)
    const { Text } = $.ui.resolve(e)
    const name = e.props.tool.startsWith('mcp__') ? e.props.tool.split('__').slice(1).join(' ') : e.props.tool
    return (
      <Text color={theme[slot]}>
        {icon} {name}
        <Text dimColor> {summary(e.props.input)}{e.props.isRunning ? ' …' : ''}</Text>
      </Text>
    )
  })

  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    const s = await read($, skin)
    if (s === 'off' || e.props.message !== null) return next(e)
    const words = THEMES[s].words
    const word = words[e.props.word.length % words.length] ?? e.props.word
    return next({ ...e, props: { ...e.props, word } })
  })
}
