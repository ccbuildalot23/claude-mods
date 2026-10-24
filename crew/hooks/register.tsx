import { atom, read, update } from 'claude-code'
import type { ModelUsage, Register } from 'claude-code'

import type { CrewMate, CrewTodo } from '../types'

const PANE = 'crew'
const isOn = atom({ plugin: 'crew', key: 'isOn' } as const, true)
const mates = atom({ plugin: 'crew', key: 'mates' } as const, [])
const hired = atom({ plugin: 'crew', key: 'hired' } as const, 0)

// One character per subagent; colors are picked to stay apart from each other on dark and light themes.
const CAST = [
  { glyph: '🦊', name: 'Ember', color: '#FF7A45' },
  { glyph: '🦉', name: 'Sage', color: '#B388FF' },
  { glyph: '🐙', name: 'Inky', color: '#FF4FA3' },
  { glyph: '🐢', name: 'Moss', color: '#4CAF50' },
  { glyph: '🦅', name: 'Talon', color: '#E0A526' },
  { glyph: '🐬', name: 'Wave', color: '#3FA9F5' },
  { glyph: '🐝', name: 'Buzz', color: '#D4B400' },
  { glyph: '🦎', name: 'Zip', color: '#14B8A6' },
  { glyph: '🐺', name: 'Ash', color: '#94A3B8' },
  { glyph: '🦋', name: 'Iris', color: '#E879F9' },
  { glyph: '🐻', name: 'Bruno', color: '#C68B59' },
  { glyph: '🐧', name: 'Pip', color: '#6366F1' },
] as const

function bar(done: number, total: number, width = 10): string {
  const filled = total === 0 ? 0 : Math.round((done / total) * width)
  return '█'.repeat(filled) + '░'.repeat(width - filled)
}

// API-equivalent list prices per million tokens; on a subscription this is a yardstick, not a bill.
export function dollars(u: ModelUsage): number {
  return (u.input_tokens * 5 + u.output_tokens * 25 + u.cache_read_input_tokens * 0.5 + u.cache_creation_input_tokens * 6.25) / 1e6
}

function clip(text: string, max: number): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat
}

function base(path: unknown): string {
  return typeof path === 'string' ? (path.split('/').pop() ?? path) : 'a file'
}

function host(url: unknown): string {
  return typeof url === 'string' ? (/^\w+:\/\/([^/]+)/.exec(url)?.[1] ?? url) : 'a page'
}

// A plain-words line for what one tool call is doing.
function describe(tool: string, input: Record<string, unknown>): string {
  const str = (k: string) => (typeof input[k] === 'string' ? (input[k] as string) : '')
  switch (tool) {
    case 'Read': return `Reading ${base(input.file_path)}`
    case 'Edit': case 'MultiEdit': return `Editing ${base(input.file_path)}`
    case 'Write': return `Writing ${base(input.file_path)}`
    case 'NotebookEdit': return `Editing ${base(input.notebook_path)}`
    case 'Bash': return str('description') ? clip(str('description'), 48) : `Running ${clip(str('command'), 40)}`
    case 'Grep': return `Searching for “${clip(str('pattern'), 30)}”`
    case 'Glob': return `Finding ${clip(str('pattern'), 30)}`
    case 'WebFetch': return `Reading ${host(input.url)}`
    case 'WebSearch': return `Searching the web: ${clip(str('query'), 34)}`
    case 'Agent': case 'Task': return `Briefing a helper: ${clip(str('description'), 30)}`
    case 'TodoWrite': return 'Updating its plan'
    default: return `Using ${tool.replace(/^mcp__([^_]+)__/, '$1: ')}`
  }
}

function seconds(m: CrewMate, now: number): string {
  const s = Math.max(0, Math.round(((m.status === 'working' ? now : m.endedAt) - m.startedAt) / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`
}

function progress(m: CrewMate): string {
  if (m.todos.length === 0) return `step ${m.steps}`
  const done = m.todos.filter(t => t.status === 'completed').length
  return `${bar(done, m.todos.length)} ${done}/${m.todos.length}`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'crew', description: 'Open the subagent crew panel, or /crew on|off', argumentHint: '[on|off]', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'crew' }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'off' || arg === 'on') {
      await update($, isOn, () => arg === 'on')
      if (arg === 'off') await $.ui.close({ id: PANE })
      return { text: `Crew is ${arg}.` }
    }
    await $.ui.open({ id: PANE, title: 'Crew' })
    return { text: 'Crew panel opened.' }
  })

  on('agent.spawn', async ($, e, next) => {
    const spawned = await next(e)
    const id = spawned.agentId
    if (id === undefined) return spawned
    const now = await $.clock.now()
    const count = await read($, hired)
    const busy = new Set((await read($, mates)).filter(m => m.status === 'working').map(m => m.name))
    // Next character in the cast that nobody working is already wearing.
    let pick = count % CAST.length
    for (let i = 0; i < CAST.length && busy.has(CAST[pick]!.name); i++) pick = (pick + 1) % CAST.length
    const who = CAST[pick]!
    await update($, hired, n => n + 1)
    const mate: CrewMate = {
      id,
      name: e.name !== undefined ? `${who.name} (${e.name})` : who.name,
      glyph: who.glyph,
      color: who.color,
      task: e.description ?? clip(e.prompt, 60),
      type: e.subagentType ?? 'general-purpose',
      doing: 'Getting started',
      steps: 0,
      todos: [],
      status: 'working',
      startedAt: now,
      endedAt: 0,
    }
    await update($, mates, list => [...list.filter(m => m.id !== id), mate].slice(-30))
    return spawned
  })

  on('tool.call', async ($, e, next) => {
    const agentId = e.agentId
    if (agentId === undefined) return next(e)
    const input = e as unknown as Record<string, unknown>
    let todos: CrewTodo[] | undefined
    let doing = describe(e.tool, input)
    if (e.tool === 'TodoWrite') {
      todos = e.todos.map(t => ({ label: t.status === 'in_progress' ? t.activeForm : t.content, status: t.status }))
      const current = todos.find(t => t.status === 'in_progress')
      if (current !== undefined) doing = current.label
    }
    await update($, mates, list =>
      list.map(m => (m.id === agentId ? { ...m, status: 'working', doing, steps: m.steps + 1, todos: todos ?? m.todos } : m)),
    )
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const agentId = e.agentId
    if (agentId !== undefined) {
      const now = await $.clock.now()
      const status = e.isAborted ? 'failed' : 'done'
      const u = e.usage
      const used = u ? u.input_tokens + u.output_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens : 0
      await update($, mates, list =>
        list.map(m =>
          m.id === agentId
            ? { ...m, status, endedAt: now, doing: status === 'done' ? 'Finished' : 'Stopped', tokens: (m.tokens ?? 0) + used, dollars: (m.dollars ?? 0) + (u ? dollars(u) : 0) }
            : m,
        ),
      )
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || !(await read($, isOn))) return next(e)
    const working = (await read($, mates)).filter(m => m.status === 'working')
    if (working.length === 0) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const now = await $.clock.now()
    const room = Math.max(1, e.props.maxRows - 1)
    const shown = working.length > room ? working.slice(0, room - 1) : working
    return (
      <Box flexDirection="column">
        {shown.map(m => (
          <Box flexDirection="row">
            <Text color={m.color} bold>
              {m.glyph} {m.name}
            </Text>
            <Text color={m.color}> {progress(m)}</Text>
            <Text dimColor>
              {' · '}
              {clip(m.doing, 50)} · {seconds(m, now)}
            </Text>
          </Box>
        ))}
        {shown.length < working.length && <Text dimColor>+{working.length - shown.length} more on /crew</Text>}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const crew = await read($, mates)
    const now = await $.clock.now()
    const working = crew.filter(m => m.status === 'working').length
    const total = crew.reduce((sum, m) => sum + (m.dollars ?? 0), 0)
    return (
      <Box flexDirection="column">
        {crew.length === 0 && <Text dimColor>No subagents yet this session. They show up here as soon as one starts.</Text>}
        {crew.length > 0 && (
          <Text bold>
            {working} working · {crew.length - working} finished
          </Text>
        )}
        {crew.map(m => (
          <Box flexDirection="column" marginTop={1}>
            <Text color={m.color} bold>
              {m.glyph} {m.name} {m.status === 'working' ? '· working' : m.status === 'done' ? '· done ✓' : '· stopped'}
            </Text>
            <Text>   {m.task}</Text>
            <Text color={m.color}>   {progress(m)} · {seconds(m, now)} · {m.steps} step{m.steps === 1 ? '' : 's'}</Text>
            <Text dimColor>
              {'   '}
              {m.type} · {clip(m.doing, 60)}
              {(m.tokens ?? 0) > 0 ? ` · ${Math.round((m.tokens ?? 0) / 1000)}k tokens · ≈$${(m.dollars ?? 0).toFixed(2)}` : ''}
            </Text>
            {m.todos.map(t => (
              <Text dimColor={t.status !== 'in_progress'} color={t.status === 'in_progress' ? m.color : undefined}>
                {'     '}
                {t.status === 'completed' ? '✓' : t.status === 'in_progress' ? '▸' : '○'} {t.label}
              </Text>
            ))}
          </Box>
        ))}
        {total > 0 && <Text bold>Crew total ≈${total.toFixed(2)} (API-equivalent; your plan covers it)</Text>}
      </Box>
    )
  })
}
