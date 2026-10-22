import type { EngineInterface, Register } from 'claude-code'

// Action log: one line per tool call, from every session this Mac runs (scheduled runs included), in
// ~/Developer/claude-mods/logs/actions-YYYY-MM-DD.log. The line is written before the call runs; if it
// cannot be written, the call does not run (fail closed, harness-addons-v2 TONIGHT item 2). A second line
// records how it ended. Paths and commands only, never file contents, and keys are masked. Uses no AI.

const KEYS = /\b(sk-(ant-|proj-)?[A-Za-z0-9_-]{12,}|(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{12,}|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{8,}|AIza[0-9A-Za-z_-]{30,})/g
const ASSIGN = /\b(api[_-]?key|secret|password|passwd|token)(\s*[:=]\s*)['"]?[^\s'"]{8,}/gi

export function mask(text: string): string {
  return text.replace(KEYS, '[key]').replace(ASSIGN, '$1$2[hidden]').replace(/\s+/g, ' ')
}

export function target(e: Record<string, unknown>): string {
  const pick = e.command ?? e.file_path ?? e.notebook_path ?? e.path ?? e.url ?? e.pattern ?? e.query ?? e.prompt
  if (typeof pick === 'string') return mask(pick).slice(0, 180)
  const { tool: _t, tool_use_id: _i, content: _c, new_string: _n, old_string: _o, ...rest } = e
  return mask(JSON.stringify(rest)).slice(0, 180)
}

const pad = (n: number) => String(n).padStart(2, '0')

async function append($: EngineInterface, line: string): Promise<void> {
  const home = (await $.env.get('HOME')) ?? '.'
  const d = new Date(await $.clock.now())
  const path = `${home}/Developer/claude-mods/logs/actions-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.log`
  const r = await $.process.run(['/bin/sh', '-c', 'mkdir -p "$(dirname "$2")" && printf "%s\\n" "$1" >> "$2"', 'sh', line, path], { timeoutMs: 5000 })
  if (r.exitCode !== 0) throw new Error(`log write failed (${r.exitCode})`)
}

async function stamp($: EngineInterface): Promise<string> {
  const d = new Date(await $.clock.now())
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'log', description: "Show today's action log (every tool call, every session)", argumentHint: '[lines, default 40]', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'log' }, async ($, e) => {
    const home = (await $.env.get('HOME')) ?? '.'
    const d = new Date(await $.clock.now())
    const path = `${home}/Developer/claude-mods/logs/actions-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.log`
    const n = Math.min(Math.max(Number.parseInt(e.args, 10) || 40, 1), 400)
    try {
      const all = (await $.fs.read(path)).trimEnd().split('\n')
      return { text: `${path} (${all.filter(l => !l.startsWith(' ')).length} calls today)\n${all.slice(-n).join('\n')}` }
    } catch {
      return { text: `Nothing logged yet today (${path}).` }
    }
  })

  on('tool.call', async ($, e, next) => {
    const sid = String(await $.session.id()).slice(0, 8)
    const who = e.agentId === undefined ? 'main' : `agent ${String(e.agentId).slice(0, 6)}`
    await append($, `${await stamp($)} ${sid} ${who} ${e.tool}: ${target(e as unknown as Record<string, unknown>)}`)
    const result = await next(e)
    const end = result.deny !== undefined ? `blocked: ${mask(result.deny).slice(0, 140)}` : 'ran'
    await append($, `         └ ${e.tool} ${end}`).catch(() => undefined)
    return result
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'action-log: could not write the action log, so the call did not run (fail closed). Check that ~/Developer/claude-mods/logs is writable, or turn the action-log mod off in /mods.' }))
}
