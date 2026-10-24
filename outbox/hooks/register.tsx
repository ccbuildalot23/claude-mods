import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Held } from '../types'

// Outbox: holds anything that leaves this Mac in Chris's name (messages, replies, forwards, posts, comments,
// invites, shares, form submissions, deploys, git push, asset approvals) until he types /outbox release <id>.
// Drafts pass. Ported Oct 22, 2026 from the home-base mod (built and tested Oct 11, never installed); the
// poem lock and /rig live elsewhere now (blast-radius, labeau-ops). Uses no AI.

const held = atom({ plugin: 'outbox', key: 'held' } as const, [])
const released = atom({ plugin: 'outbox', key: 'released' } as const, [])

// One `<word>_` may sit before the verb, because some servers prefix their own name (Blotato's
// `blotato_create_post`). A read word is not a prefix, so get_/list_/search_ tools pass, and neither is
// `no_`, so a tool that says it sends nothing (`no_reply_needed`) passes too.
const OUTBOUND = /(^|__)((?!(get|list|search|read|fetch|find|resolve|go|view|show|no)_)[a-z0-9]+_)?(send_message|send_imessage|reply|forward|create_post|post_comment|send_|publish|create_event|respond_to_event|share_file|share_|submit_form|deploy|invite)/i

// Commands, not words inside quotes or a heredoc (home-base gaps G080, G082).
export function bare(cmd: string): string {
  return cmd
    .replace(/<<-?\s*['"]?(\w+)['"]?[^\n]*\n[\s\S]*?\n\1(?=\s|$)/g, '<<HEREDOC')
    .replace(/'[^']*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""')
}
export const runsPush = (cmd: string): boolean => /\bgit\s+(-C\s+\S+\s+)?push\b/.test(bare(cmd))
// In a cloud session a push to a claude/ branch only opens a pull request for review, so it passes there.
export const pushesReviewBranch = (cmd: string): boolean => /\bgit\s+(-C\s+\S+\s+)?push\b.*\bclaude\/[\w./-]+/.test(bare(cmd)) && !/\s(main|master)(\s|$)/.test(bare(cmd))
export const runsAssetApprove = (cmd: string): boolean => /\b(labeau\s+asset|asset_cmd\.py|asset_ledger(\.py)?)\b[^;&|\n]*\bapprove\b/.test(bare(cmd))

// An event on his own calendar with no guests reaches nobody, so it runs (his yes, Oct 15).
export function privateEvent(tool: string, e: Record<string, unknown>): boolean {
  if (!/(^|__)create_event$/i.test(tool)) return false
  const guests = [e.attendees, e.attendeeEmails].filter(v => v !== undefined)
  return guests.every(v => Array.isArray(v) && v.length === 0)
}

export function digestOf(e: Record<string, unknown>): string {
  // A Bash call is the command it runs; its description is a label (gap G262).
  const input = e.tool === 'Bash' && typeof e.command === 'string' ? { tool: 'Bash', command: e.command } : e
  const { tool_use_id: _a, consent: _b, agentId: _c, requestMeta: _d, ...rest } = input as Record<string, unknown>
  const text = JSON.stringify(rest, Object.keys(rest).sort())
  let h = 5381
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) >>> 0
  return h.toString(16)
}

export function summarize(e: Record<string, unknown>): string {
  const pick = ['to', 'recipient', 'recipients', 'cc', 'subject', 'account', 'accountId', 'platform', 'text', 'body', 'message', 'command']
  const parts = pick.filter(k => e[k] !== undefined).map(k => `${k}: ${String(JSON.stringify(e[k])).slice(0, 160)}`)
  return parts.join(' · ') || JSON.stringify(e).slice(0, 240)
}

// A yes in the engine's own question dialog is Chris's hand on every surface, the desktop app included,
// whose typed prompts are not stamped `composer`. The model cannot answer that dialog; with nobody there
// (a -p or scheduled run) it rejects, which counts as no. His yes, Oct 24.
export async function chrisSays($: EngineInterface, question: string, yes: string): Promise<boolean> {
  const answer = await $.ui.ask(question, { header: 'Outbox', options: [yes, 'Keep it held'] }).catch(() => '')
  return answer === yes
}

async function hold($: EngineInterface, e: Record<string, unknown>, label: string): Promise<{ deny: string } | undefined> {
  const digest = digestOf(e)
  if ((await read($, released)).includes(digest)) {
    await update($, released, r => r.filter(d => d !== digest))
    return undefined
  }
  // With Chris watching, he says yes on the spot instead of coming back later to release it.
  const isWatched = (await $.session.surfaces().catch(() => [])).length > 0
  if (isWatched && (await chrisSays($, `Outbox: send this ${label} now? ${summarize(e).slice(0, 300)}`, 'Send once'))) return undefined
  const at = new Date(await $.clock.now()).toISOString().slice(0, 16)
  const id = `OB-${digest.slice(0, 6)}`
  const item: Held = { id, tool: label, digest, summary: summarize(e), at }
  await update($, held, l => (l.some(h => h.id === id) ? l : [...l, item]))
  try {
    const home = (await $.env.get('HOME')) ?? '.'
    await $.fs.write(`${home}/Developer/claude-mods/outbox-held/${id}.json`, JSON.stringify({ ...item, payload: e }, null, 2))
  } catch {
    // The record on disk is a courtesy; the hold itself stands without it.
  }
  return { deny: `Held in the Outbox as ${id}: ${label}. ${item.summary}. Nothing was sent. Chris releases it by typing /outbox release ${id}; then the identical call runs once. Tell him it is waiting.` }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'outbox', description: 'Outbox: list held sends, posts and pushes, or release one you approve', argumentHint: '[list | release <id> | dismiss <id>]' })
    return next(e)
  })

  on('command.run', { command: 'outbox' }, async ($, e) => {
    const [verb, id] = e.args.trim().split(/\s+/)
    const list = await read($, held)
    if (verb === 'release' || verb === 'dismiss') {
      const item = list.find(h => h.id === id)
      if (item === undefined) return { text: `Outbox: nothing held as ${id ?? '(no id)'}.` }
      // Chris's Enter at a terminal counts as is; from anywhere else (the desktop app, a plugin, the model)
      // he confirms it in the question dialog.
      const label = verb === 'release' ? 'Release once' : 'Dismiss'
      if (e.origin?.kind !== 'composer' && !(await chrisSays($, `Outbox: ${verb} ${id} (${item.tool})? ${item.summary.slice(0, 300)}`, label))) {
        return { text: `Outbox: ${id} is still held. A ${verb} must come from Chris.` }
      }
      if (verb === 'release') await update($, released, r => [...r, item.digest])
      await update($, held, l => l.filter(h => h.id !== id))
      return { text: verb === 'release' ? `Outbox: ${id} released once. The identical ${item.tool} call may now run one time.` : `Outbox: ${id} dismissed. Nothing was sent; its record stays in ~/Developer/claude-mods/outbox-held/.` }
    }
    if (list.length === 0) return { text: 'Outbox: empty.' }
    return { text: list.map(h => `${h.id}  ${h.at}  ${h.tool}\n    ${h.summary}`).join('\n') }
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const isCloud = (await $.env.get('CLAUDE_CODE_REMOTE')) === 'true'
    if (runsPush(e.command) && !(isCloud && pushesReviewBranch(e.command))) {
      const v = await hold($, e as unknown as Record<string, unknown>, 'git push')
      if (v !== undefined) return v
    }
    if (runsAssetApprove(e.command)) {
      const v = await hold($, e as unknown as Record<string, unknown>, 'asset approval')
      if (v !== undefined) return v
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'outbox: its shell check failed, so the command is held. Ask Chris.' }))

  on('tool.call', async ($, e, next) => {
    const tool = e.tool
    if (tool.startsWith('mcp__') && OUTBOUND.test(tool) && !/draft/i.test(tool) && !privateEvent(tool, e as unknown as Record<string, unknown>)) {
      const v = await hold($, e as unknown as Record<string, unknown>, tool)
      if (v !== undefined) return v
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'outbox: its check failed, so the call is held. Ask Chris.' }))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const list = await read($, held)
    if (e.props.hasSurvey || list.length === 0) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="row">
        <Text color="yellow">Outbox: {list.length} held. </Text>
        <Text dimColor>Type /outbox to review, /outbox release {list[0]?.id} to send one.</Text>
      </Box>
    )
  })
}
