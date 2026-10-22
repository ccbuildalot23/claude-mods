import { atom, read, update } from 'claude-code'
import type { Register, ModelUsage } from 'claude-code'

import type { Helper, HelperTodo } from '../types'

const PANE = 'helper-desk'
const isOn = atom({ plugin: 'helper-desk', key: 'isOn' } as const, true)
const todos = atom({ plugin: 'helper-desk', key: 'todos' } as const, [])
const helpers = atom({ plugin: 'helper-desk', key: 'helpers' } as const, [])

// API-equivalent list prices per million tokens; on a subscription this is a yardstick, not a bill.
function dollars(u: ModelUsage): number {
  return (u.input_tokens * 5 + u.output_tokens * 25 + u.cache_read_input_tokens * 0.5 + u.cache_creation_input_tokens * 6.25) / 1e6
}

function bar(done: number, total: number, width = 20): string {
  const filled = total === 0 ? 0 : Math.round((done / total) * width)
  return '█'.repeat(filled) + '░'.repeat(width - filled)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'helperdesk', description: 'Open the helpers panel, or /helperdesk on|off', argumentHint: '[on|off]', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'helperdesk' }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'off' || arg === 'on') {
      await update($, isOn, () => arg === 'on')
      if (arg === 'off') await $.ui.close({ id: PANE })
      return { text: `Helper desk is ${arg}.` }
    }
    await $.ui.open({ id: PANE, title: 'Helpers' })
    return { text: 'Helpers panel opened.' }
  })

  on('prompt.submit', async ($, e, next) => {
    // A new request starts a fresh board; finished helpers drop off.
    await update($, todos, () => [])
    await update($, helpers, list => list.filter(h => !h.isDone))
    return next(e)
  })

  on('tool.call', { tool: 'TodoWrite' }, async ($, e, next) => {
    const list: HelperTodo[] = e.todos.map((t, i) => ({ id: String(i), label: t.status === 'in_progress' ? t.activeForm : t.content, status: t.status }))
    await update($, todos, () => list)
    return next(e)
  })

  on('tool.call', { tool: 'TaskCreate' }, async ($, e, next) => {
    const ran = await next(e)
    const id = /#?(\d+)/.exec(ran.text ?? '')?.[1] ?? `t${Date.now()}`
    await update($, todos, list => [...list, { id, label: e.subject, status: 'pending' } as HelperTodo])
    return ran
  })

  on('tool.call', { tool: 'TaskUpdate' }, async ($, e, next) => {
    const status = e.status
    await update($, todos, list =>
      status === 'deleted'
        ? list.filter(t => t.id !== e.taskId)
        : list.map(t => (t.id === e.taskId ? { ...t, status: status ?? t.status, label: e.subject ?? t.label } : t)),
    )
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    const spawned = await next(e)
    if (spawned.agentId !== undefined) {
      const now = await $.clock.now()
      const helper: Helper = { id: spawned.agentId, label: e.description, type: e.subagentType, isDone: false, tokens: 0, dollars: 0, startedAt: now, endedAt: 0 }
      await update($, helpers, list => [...list, helper].slice(-30))
      if (await read($, isOn)) void $.ui.open({ id: PANE, title: 'Helpers' })
    }
    return spawned
  })

  on('turn.complete', async ($, e, next) => {
    const agentId = e.agentId
    if (agentId !== undefined) {
      const now = await $.clock.now()
      const u = e.usage
      await update($, helpers, list =>
        list.map(h =>
          h.id === agentId
            ? {
                ...h,
                isDone: true,
                endedAt: now,
                tokens: h.tokens + (u ? u.input_tokens + u.output_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens : 0),
                dollars: h.dollars + (u ? dollars(u) : 0),
              }
            : h,
        ),
      )
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || !(await read($, isOn))) return next(e)
    const list = await read($, todos)
    const crew = await read($, helpers)
    const running = crew.filter(h => !h.isDone).length
    if (list.length === 0 && running === 0) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    const done = list.filter(t => t.status === 'completed').length
    const current = list.find(t => t.status === 'in_progress')
    return (
      <Box flexDirection="row">
        {list.length > 0 && (
          <Text color="magenta">
            {bar(done, list.length)} {done}/{list.length}
          </Text>
        )}
        {current !== undefined && <Text dimColor> {current.label}</Text>}
        {running > 0 && <Text> · {running} helper{running === 1 ? '' : 's'} working </Text>}
        {crew.length > 0 && <Button key="open" label="Helpers" onPress={() => $.ui.open({ id: PANE, title: 'Helpers' })} />}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const crew = await read($, helpers)
    const now = await $.clock.now()
    const total = crew.reduce((sum, h) => sum + h.dollars, 0)
    return (
      <Box flexDirection="column">
        {crew.length === 0 && <Text dimColor>No helpers this session yet.</Text>}
        {crew.map(h => {
          const secs = Math.round(((h.isDone ? h.endedAt : now) - h.startedAt) / 1000)
          return (
            <Box flexDirection="column">
              <Text color={h.isDone ? 'green' : 'yellow'}>
                {h.isDone ? 'done ' : 'busy '} {h.label}
              </Text>
              <Text dimColor>
                {'   '}
                {h.type} · {secs}s · {Math.round(h.tokens / 1000)}k tokens · ≈${h.dollars.toFixed(2)}
              </Text>
            </Box>
          )
        })}
        {crew.length > 0 && <Text bold>Helpers total ≈${total.toFixed(2)} (API-equivalent; your plan covers it)</Text>}
      </Box>
    )
  })
}
