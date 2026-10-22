import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Inventory, InventoryFile } from '../types'

const PANE = 'chat-inventory'
const EMPTY: Inventory = { isOn: true, goal: '', connectors: {}, skills: [], links: [], files: [], commands: 0 }
const inv = atom({ plugin: 'chat-inventory', key: 'inv' } as const, EMPTY)

function touch(files: InventoryFile[], path: string, next: InventoryFile['state']): InventoryFile[] {
  const at = files.findIndex(f => f.path === path)
  if (at === -1) return [...files, { path, state: next }].slice(-300)
  const was = files[at]
  // A changed file stays changed even if read again.
  const state = was !== undefined && was.state === 'changed' && next === 'read' ? 'changed' : next
  return files.map((f, i) => (i === at ? { path, state } : f))
}

function inputPath(input: unknown): string | undefined {
  if (typeof input !== 'object' || input === null) return undefined
  const record = input as Record<string, unknown>
  const p = record.file_path ?? record.notebook_path ?? record.path
  return typeof p === 'string' ? p : undefined
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'inventory', description: 'Open the In this chat panel, or /inventory on|off', argumentHint: '[on|off]', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'inventory' }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'off' || arg === 'on') {
      await update($, inv, v => ({ ...v, isOn: arg === 'on' }))
      if (arg === 'off') await $.ui.close({ id: PANE })
      return { text: `Chat inventory is ${arg}.` }
    }
    await $.ui.open({ id: PANE, title: 'In this chat' })
    return { text: 'In this chat panel opened.' }
  })

  on('prompt.submit', async ($, e, next) => {
    const text = e.text.trim()
    if (!text.startsWith('/')) await update($, inv, v => (v.goal.length > 0 ? v : { ...v, goal: text.slice(0, 200) }))
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const tool = String(e.tool)
    const path = inputPath(e)
    const isEdit = tool === 'Write' || tool === 'Edit' || tool === 'NotebookEdit'
    await update($, inv, v => {
      let out = { ...v }
      if (tool.startsWith('mcp__')) {
        const server = tool.split('__')[1] ?? tool
        out = { ...out, connectors: { ...out.connectors, [server]: (out.connectors[server] ?? 0) + 1 } }
      }
      if (tool === 'Skill' && 'skill' in e && typeof e.skill === 'string' && !out.skills.includes(e.skill)) out = { ...out, skills: [...out.skills, e.skill] }
      if (tool === 'WebFetch' && 'url' in e && typeof e.url === 'string') out = { ...out, links: [...out.links.filter(l => l !== e.url), e.url].slice(-30) }
      if (tool === 'Bash') out = { ...out, commands: out.commands + 1 }
      if (path !== undefined && (tool === 'Read' || isEdit)) out = { ...out, files: touch(out.files, path, isEdit ? 'editing' : 'read') }
      return out
    })
    const ran = await next(e)
    if (path !== undefined && isEdit) {
      const isChanged = ran.deny === undefined && ran.isError !== true
      await update($, inv, v => ({ ...v, files: touch(v.files, path, isChanged ? 'changed' : 'read') }))
    }
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const v = await read($, inv)
    const dirs = new Map<string, InventoryFile[]>()
    for (const f of v.files) {
      const cut = f.path.lastIndexOf('/')
      const dir = cut > 0 ? f.path.slice(0, cut) : '.'
      dirs.set(dir, [...(dirs.get(dir) ?? []), f])
    }
    const mark = (s: InventoryFile['state']) => (s === 'changed' ? '✓' : s === 'editing' ? '✎' : '·')
    const color = (s: InventoryFile['state']) => (s === 'changed' ? 'green' : s === 'editing' ? 'yellow' : undefined)
    const connectors = Object.entries(v.connectors)
    return (
      <Box flexDirection="column">
        <Text bold>Goal</Text>
        <Text dimColor>{v.goal.length > 0 ? v.goal : 'Not set yet.'}</Text>
        <Text bold>Connectors</Text>
        {connectors.length === 0 ? <Text dimColor>None called.</Text> : connectors.map(([name, n]) => <Text>  {name} ×{n}</Text>)}
        <Text bold>Skills</Text>
        <Text dimColor>{v.skills.length > 0 ? v.skills.join(', ') : 'None used.'}</Text>
        {v.links.length > 0 && <Text bold>Links fetched</Text>}
        {v.links.map(l => <Text dimColor>  {l}</Text>)}
        <Text bold>Files ({v.files.filter(f => f.state === 'changed').length} changed, {v.files.length} touched) · {v.commands} shell commands</Text>
        {[...dirs.entries()].map(([dir, files]) => (
          <Box flexDirection="column">
            <Text dimColor>{dir}/</Text>
            {files.map(f => (
              <Text color={color(f.state)}>  {mark(f.state)} {f.path.slice(dir.length + 1)}</Text>
            ))}
          </Box>
        ))}
      </Box>
    )
  })
}
