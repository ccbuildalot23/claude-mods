import type { EngineInterface, Register } from 'claude-code'

// Pen rule: no AI writes inside these folders, ever. Matched anywhere in the path.
const PEN_ZONES = /(^|\/)(poems|line-bank|public-copy)(\/|$)/
// Settings files are Chris's hand.
const SETTINGS = /(^|\/)\.claude\/settings(\.local)?\.json$|(^|\/)\.claude\.json$/

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

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
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
    if (PEN_ZONES.test(path)) {
      return { deny: `blast-radius: ${path} is inside a pen-rule folder (poems/, line-bank/, public-copy/). AI never writes there; put metadata in a sidecar file outside it.` }
    }
    if (SETTINGS.test(path)) {
      return { deny: `blast-radius: ${path} is a settings file, which is Chris's hand. Draft the change in the Outbox and hand him the exact edit.` }
    }
    return next(e)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'blast-radius: its path guard failed, so the write was not made.' }))
}
