import type { EngineInterface, Register } from 'claude-code'

// Pen rule: no AI writes inside these folders, ever. Matched anywhere in the path,
// any letter case (the Mac's disk treats Poems/ and poems/ as one folder).
const PEN_ZONES = /(^|\/)(poems|line-bank|public-copy|share-candidates|hierophant-lens)(\/|$)/i
// Settings files are Chris's hand.
const SETTINGS = /(^|\/)\.claude\/settings(\.local)?\.json$|(^|\/)\.claude\.json$/
// The same two, found inside a shell command's text.
const PEN_IN_COMMAND = /(^|[\s/'"=])(poems|line-bank|public-copy|share-candidates|hierophant-lens)(\/|[\s'";|&)]|$)/i
const SETTINGS_IN_COMMAND = /\.claude\/settings(\.local)?\.json\b|(^|[\s/'"])\.claude\.json\b/
// Shell that can write, move or delete: redirects, in-place edits, file verbs, scripts.
const SHELL_WRITES = /(^|[^0-9&])>{1,2}(?!&)|(^|[\s;&|(])(cp|mv|rm|rmdir|touch|tee|ln|install|rsync|dd|truncate|mkdir|chmod|chown|unlink|shred|srm|trash|patch|xargs|python3?|node|ruby|perl|osascript|ditto)\b|\bsed\b[^|;&]*\s-[a-zA-Z]*i|\bgit\s+(checkout|restore|apply|mv|rm|stash|reset|clean)\b/

type Risk = { label: string; targets: string[] }

const RULES: { test: RegExp; label: string }[] = [
  { test: /(^|[;&|(\s])rm\s/, label: 'delete (rm)' },
  { test: /\brmdir\b/, label: 'folder delete (rmdir)' },
  { test: /\bfind\b.*\s-delete\b/, label: 'find -delete' },
  { test: /\bfind\b.*-exec\s+rm\b/, label: 'find -exec rm' },
  { test: /\bgit\s+clean\s+-[a-zA-Z]*f/, label: 'git clean (removes untracked files)' },
  { test: /\bgit\s+reset\s+--hard\b/, label: 'git reset --hard (drops uncommitted work)' },
  { test: /\bgit\s+checkout\s+(--\s+)?\.(\s|$)/, label: 'git checkout . (drops uncommitted edits)' },
  { test: /\bgit\s+restore\s+(--staged\s+)?\.(\s|$)/, label: 'git restore . (drops uncommitted edits)' },
  { test: /\bgit\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease)/, label: 'force push (rewrites remote history)' },
  { test: /\bgit\s+branch\s+-D\b/, label: 'branch force-delete' },
  { test: /\brsync\b.*--delete\b/, label: 'rsync --delete' },
  { test: /\bdd\s+.*\bof=/, label: 'dd write' },
  { test: /\bmkfs\b|\bdiskutil\s+(erase|reformat)/, label: 'disk erase' },
  { test: /\bsrm\b|\bshred\b/, label: 'secure delete' },
  { test: /\btrash\b|\bmv\b.*\s~\/\.Trash/, label: 'move to Trash' },
]

function judge(command: string): Risk | undefined {
  const hit = RULES.find(rule => rule.test.test(command))
  if (hit === undefined) return undefined
  // Paths the command names: every word after the verb that is not a flag.
  const words = command.split(/\s+/).filter(w => w.length > 0)
  const targets = words
    .slice(1)
    .filter(w => !w.startsWith('-') && !/^(rm|rmdir|git|find|rsync|clean|reset|push|checkout|restore|branch|sudo|-exec|\{\}|\;|;|&&|\|\|)$/.test(w))
    .slice(0, 8)
  return { label: hit.label, targets }
}

async function preview($: EngineInterface, risk: Risk, cwd: string | undefined): Promise<string> {
  const lines: string[] = []
  for (const target of risk.targets) {
    try {
      const found = await $.process.run(['find', target, '-maxdepth', '6', '-type', 'f'], { cwd, timeoutMs: 5000 })
      if (found.exitCode !== 0) continue
      const files = found.stdout.split('\n').filter(f => f.length > 0)
      lines.push(`${target}: ${files.length} file${files.length === 1 ? '' : 's'}${files.length > 0 ? ' (' + files.slice(0, 5).join(', ') + (files.length > 5 ? ', ...' : '') + ')' : ''}`)
    } catch {
      // A target that is not a path (a branch, a remote) is shown as named.
    }
  }
  return lines.length > 0 ? lines.join('; ') : `targets: ${risk.targets.join(' ') || '(working tree)'}`
}

// Where a Write or Edit really lands, so a symlink into poems/ is caught too.
async function landsIn($: EngineInterface, path: string): Promise<string | undefined> {
  const own = await $.fs.stat(path, { resolve: true }).catch(() => undefined)
  if (own?.realPath !== undefined) return own.realPath
  const cut = path.lastIndexOf('/')
  if (cut <= 0) return undefined
  const folder = await $.fs.stat(path.slice(0, cut), { resolve: true }).catch(() => undefined)
  return folder?.realPath === undefined ? undefined : `${folder.realPath}/${path.slice(cut + 1)}`
}

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    // The pen rule holds for the shell too: no writing, moving or deleting in those folders.
    if (SHELL_WRITES.test(e.command)) {
      if (PEN_IN_COMMAND.test(e.command)) {
        return { deny: 'blast-radius: this command could write, move or delete inside a pen-rule folder (poems/, line-bank/, public-copy/, share-candidates/, hierophant-lens/). AI never changes those; read them with the Read tool and put metadata in a sidecar file outside.' }
      }
      if (SETTINGS_IN_COMMAND.test(e.command)) {
        return { deny: "blast-radius: this command could change a Claude settings file, which is Chris's hand. Draft the change in the Outbox and hand him the exact edit." }
      }
    }
    const risk = judge(e.command)
    if (risk === undefined) return next(e)

    const hits = await preview($, risk, undefined)
    $.ui.notice(e.tool_use_id, `Blast radius: ${risk.label}`)
    const answer = await $.ui.ask(
      `Blast radius: ${risk.label}. This would hit ${hits}. Run it?`,
      { header: 'Blast radius', options: ['Cancel', 'Proceed'] },
    )
    return answer === 'Proceed'
      ? next(e)
      : { deny: `blast-radius: the person cancelled "${e.command.slice(0, 80)}" (${risk.label}). Find a safer route or ask them.` }
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: 'blast-radius: could not get a person to confirm this risky command, so it was not run.' },
  )

  on('tool.call', async ($, e, next) => {
    const path =
      e.tool === 'Write' || e.tool === 'Edit' ? e.file_path
      : e.tool === 'NotebookEdit' ? e.notebook_path
      : undefined
    if (path === undefined) return next(e)
    const real = await landsIn($, path)
    if (PEN_ZONES.test(path) || (real !== undefined && PEN_ZONES.test(real))) {
      return { deny: `blast-radius: ${path} is inside a pen-rule folder (poems/, line-bank/, public-copy/, share-candidates/, hierophant-lens/). AI never writes there; put metadata in a sidecar file outside it.` }
    }
    if (SETTINGS.test(path)) {
      return { deny: `blast-radius: ${path} is a settings file, which is Chris's hand. Draft the change in the Outbox and hand him the exact edit.` }
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'blast-radius: its path guard failed, so the write was not made.' }))
}
