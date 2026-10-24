import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Blocked } from '../types'

// Privacy preflight: checks every write headed somewhere shared (the grok-bridge, the LaBeau site,
// Airtable, Blotato, Notion, Drive, email) before it lands. It blocks private names from Chris's own
// list, private-life words, keys, bridge timestamps later than now and bridge files that break the
// protocol's names. Built Oct 22, 2026 after private details reached shared bridge files on
// Oct 17, 20 and 21 (GLITCHES-AND-SECURITY.md). Locked on, like blast-radius. Uses no AI.

const blocked = atom({ plugin: 'privacy-preflight', key: 'blocked' } as const, [])
const allowed = atom({ plugin: 'privacy-preflight', key: 'allowed' } as const, [])

// Folders whose files other agents or the public read. Matched anywhere in the path.
const SHARED_PATH = /(^|\/)(grok-bridge|labeau-site[^/]*|public-copy|outbox\/assets)(\/|$)/i
// Shared-service tools that write: Airtable rows, Notion pages, Drive files, posts, comments, mail.
const SHARED_TOOL = /^mcp__.*(airtable.*(create|update)|notion.*(create|update|comment)|drive.*(create|update|copy)|blotato.*(create|post|send|comment)|gmail.*(create_draft|update_draft|send|reply|forward)|slack.*(send|post)|calendar.*(create|update))/i
// Shell that writes into a shared folder.
const SHELL_WRITES = /(^|[^0-9&])>{1,2}(?!&)|(^|[\s;&|(])(cp|mv|tee|rsync|install|ditto|python3?|node)\b|\bsed\b[^|;&]*\s-[a-zA-Z]*i/

// Private-life words that never go in shared text (categories only; Chris's own list adds more).
// The bridge protocol lets PACKET files carry them, for his Gmail draft alone.
const PRIVATE_WORDS = [
  'clean date', 'days clean', 'sobriety', 'sober', 'relapse', 'recovery program', 'NA meeting', 'AA meeting',
  'rehab', 'detox', 'therapy', 'therapist', 'counselor', 'diagnosis', 'diagnosed', 'medication', 'prescription',
  'bankruptcy', 'chapter 7', 'chapter 13', 'credit counseling', 'overdraft', 'unemployment', 'divorce', 'custody',
]

const SECRETS: { label: string; re: RegExp }[] = [
  { label: 'an API key (sk-)', re: /\bsk-(ant-|proj-)?[A-Za-z0-9_-]{20,}/ },
  { label: 'a GitHub token', re: /\b(ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}/ },
  { label: 'an AWS key', re: /\bAKIA[0-9A-Z]{16}\b/ },
  { label: 'a Slack token', re: /\bxox[abprs]-[A-Za-z0-9-]{10,}/ },
  { label: 'an Airtable token', re: /\bpat[A-Za-z0-9]{14}\.[a-f0-9]{40,}/ },
  { label: 'a Google key', re: /\bAIza[0-9A-Za-z_-]{35}\b/ },
  { label: 'a private key', re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/ },
  { label: 'a password or key assignment', re: /\b(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['"]?[A-Za-z0-9_\-/+]{16,}/i },
]

const STATUSES = new Set(['new', 'acked', 'claimed', 'done', 'blocked', 'rejected'])
// <S>2<R>-YYYY-MM-DD-NNN-short-slug.md, PROTOCOL v2.1 section 2. MOVED- stubs are the bridge's own.
const MESSAGE_NAME = /^[CGHM]2[CGHM]-\d{4}-\d{2}-\d{2}-\d{3}-[a-z0-9-]+\.md$/
const MESSAGE_FOLDER = /(^|\/)grok-bridge\/(to-claude|to-grok|to-hermes|to-muse|from-hermes|from-muse)\/[^/]+$/

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const wordRe = (w: string) => new RegExp(`(^|[^A-Za-z])${escape(w)}([^A-Za-z]|$)`, 'i')

async function base($: EngineInterface): Promise<string> {
  return `${(await $.env.get('HOME')) ?? '.'}/Developer/claude-mods`
}

async function lines($: EngineInterface, path: string): Promise<string[]> {
  try {
    return (await $.fs.read(path)).split('\n').map(l => l.trim()).filter(l => l.length > 1 && !l.startsWith('#'))
  } catch {
    return []
  }
}

// Status-log and created_et stamps are the writer's real clock (PROTOCOL section 2); a later one is a glitch.
export function futureStamp(text: string, now: number): string | undefined {
  const re = /(?:^|\n)\s*(?:-\s*|created_et:\s*|\|\s*)(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const at = new Date(`${m[1]}T${m[2]}:${m[3]}:00`).getTime()
    if (Number.isFinite(at) && at > now + 10 * 60 * 1000) return `${m[1]} ${m[2]}:${m[3]}`
  }
  return undefined
}

export function protocolProblem(path: string, text: string, isNew: boolean): string | undefined {
  if (!MESSAGE_FOLDER.test(path)) return undefined
  const name = path.slice(path.lastIndexOf('/') + 1)
  if (isNew && !name.startsWith('MOVED-') && !MESSAGE_NAME.test(name)) {
    return `the file name ${name} is not <S>2<R>-YYYY-MM-DD-NNN-slug.md (PROTOCOL section 2)`
  }
  const status = /^status:\s*([a-z]+)/m.exec(text)
  if (status !== null && !STATUSES.has(status[1] ?? '')) return `status "${status[1]}" is not one of new, acked, claimed, done, blocked, rejected`
  return undefined
}

export async function findProblem($: EngineInterface, text: string, path: string | undefined, isNew: boolean): Promise<string | undefined> {
  const root = await base($)
  for (const name of await lines($, `${root}/config/private-names.txt`)) {
    if (wordRe(name).test(text)) return `it names someone on your private list (${name})`
  }
  const isPacket = path !== undefined && /grok-bridge/.test(path) && /^type:\s*packet\b/m.test(text)
  if (!isPacket) {
    for (const w of [...PRIVATE_WORDS, ...(await lines($, `${root}/config/private-words.txt`))]) {
      if (wordRe(w).test(text)) return `it carries a private-life word ("${w}")`
    }
  }
  for (const s of SECRETS) if (s.re.test(text)) return `it looks like it holds ${s.label}`
  if (path !== undefined && /grok-bridge/.test(path)) {
    const stamp = futureStamp(text, await $.clock.now())
    if (stamp !== undefined) return `the time ${stamp} is later than now; take every stamp from the clock at the moment of writing (LESSONS, Oct 17)`
    const p = protocolProblem(path, text, isNew)
    if (p !== undefined) return p
  }
  return undefined
}

function digestOf(text: string): string {
  let h = 5381
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) >>> 0
  return h.toString(16)
}

async function verdict($: EngineInterface, where: string, text: string, path: string | undefined, isNew: boolean): Promise<{ deny: string } | undefined> {
  const problem = await findProblem($, text, path, isNew)
  if (problem === undefined) return undefined
  const digest = digestOf(where + text)
  if ((await read($, allowed)).includes(digest)) {
    await update($, allowed, a => a.filter(d => d !== digest))
    return undefined
  }
  const id = `PF-${digest.slice(0, 6)}`
  const item: Blocked = { id, where, problem, digest }
  await update($, blocked, l => (l.some(b => b.id === id) ? l : [...l, item].slice(-20)))
  return { deny: `privacy-preflight: not written to ${where}, because ${problem}. Rewrite it without that detail (name the category only, or describe by count). If Chris wants it as is, he types /preflight allow ${id}, then the identical write runs once.` }
}

async function realPath($: EngineInterface, path: string): Promise<{ real: string; isNew: boolean }> {
  const own = await $.fs.stat(path, { resolve: true }).catch(() => undefined)
  if (own?.realPath !== undefined) return { real: own.realPath, isNew: false }
  const cut = path.lastIndexOf('/')
  const dir = cut > 0 ? await $.fs.stat(path.slice(0, cut), { resolve: true }).catch(() => undefined) : undefined
  return { real: dir?.realPath === undefined ? path : `${dir.realPath}/${path.slice(cut + 1)}`, isNew: true }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'preflight', description: 'Privacy preflight: list what it blocked, or let one blocked write through once', argumentHint: '[list | allow <id>]' })
    return next(e)
  })

  on('command.run', { command: 'preflight' }, async ($, e) => {
    const [verb, id] = e.args.trim().split(/\s+/)
    const list = await read($, blocked)
    if (verb === 'allow') {
      const item = list.find(b => b.id === id)
      if (item === undefined) return { text: `Preflight: nothing blocked as ${id ?? '(no id)'}.` }
      // Chris's Enter at a terminal counts as is. From the desktop app (whose prompts are not stamped
      // `composer`) or anywhere else, he confirms in the question dialog, which the model cannot answer.
      if (e.origin?.kind !== 'composer') {
        const answer = await $.ui.ask(`Preflight: let ${id} through to ${item.where} once? It was blocked because ${item.problem}.`, { header: 'Preflight', options: ['Allow once', 'Keep blocked'] }).catch(() => '')
        if (answer !== 'Allow once') return { text: 'Preflight: only Chris can let a blocked write through; it stays blocked.' }
      }
      await update($, allowed, a => [...a, item.digest])
      await update($, blocked, l => l.filter(b => b.id !== id))
      return { text: `Preflight: ${id} allowed once. The identical write may now run one time.` }
    }
    if (list.length === 0) return { text: 'Preflight: nothing blocked this session. Your lists: ~/Developer/claude-mods/config/private-names.txt and private-words.txt (one per line, never committed).' }
    return { text: list.map(b => `${b.id}  ${b.where}\n    ${b.problem}`).join('\n') }
  })

  on('tool.call', async ($, e, next) => {
    if (e.tool === 'Write' || e.tool === 'Edit' || e.tool === 'NotebookEdit') {
      const path = e.tool === 'NotebookEdit' ? e.notebook_path : e.file_path
      const { real, isNew } = await realPath($, path)
      if (!SHARED_PATH.test(path) && !SHARED_PATH.test(real)) return next(e)
      const text =
        e.tool === 'Write' ? e.content
        : e.tool === 'Edit' ? e.new_string
        : e.new_source
      let whole = text
      if (e.tool !== 'Write' && !isNew) {
        // A status line edited in place still lands in the whole file; protocol checks read the result.
        whole = await $.fs.read(real).catch(() => text)
        if (e.tool === 'Edit') whole = whole.split(e.old_string).join(e.new_string)
      }
      const v = await verdict($, real, `${text}\n${e.tool === 'Write' ? '' : whole.match(/^status:.*$/m)?.[0] ?? ''}`, real, isNew)
      return v ?? next(e)
    }
    if (e.tool === 'Bash') {
      if (!SHELL_WRITES.test(e.command) || !SHARED_PATH.test(e.command)) return next(e)
      const v = await verdict($, 'a shared folder (shell)', e.command, 'grok-bridge (shell)', false)
      return v ?? next(e)
    }
    if (e.tool.startsWith('mcp__') && SHARED_TOOL.test(e.tool)) {
      const { tool_use_id: _id, ...input } = e as unknown as Record<string, unknown>
      const v = await verdict($, e.tool, JSON.stringify(input), undefined, false)
      return v ?? next(e)
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'privacy-preflight: its check failed, so the shared write was not made. Try again, or ask Chris.' }))
}
