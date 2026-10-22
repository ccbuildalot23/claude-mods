import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

const isOn = atom({ plugin: 'screen-share', key: 'isOn' } as const, false)
const names = atom({ plugin: 'screen-share', key: 'names' } as const, [])

const BAR = '▇▇▇▇▇'

const PATTERNS: RegExp[] = [
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, // emails
  /(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b/g, // phone numbers
  /[$€£]\s?\d[\d,]*(\.\d+)?\s?(k|K|m|M|bn|million|thousand)?/g, // money
  /\b\d[\d,]*(\.\d+)?\s?(dollars|USD|usd)\b/g,
  /\b(sk|pk|rk|ghp|gho|github_pat|xox[abp]|AKIA)[-_A-Za-z0-9]{12,}\b/g, // keys and tokens
  /\b\d{3}-\d{2}-\d{4}\b/g, // SSN shape
  /\b(?:\d[ -]?){13,16}\b/g, // card-number shape
]

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function mask(text: string, people: readonly string[]): string {
  let out = text
  for (const pattern of PATTERNS) out = out.replace(pattern, BAR)
  for (const name of people) {
    if (name.trim().length < 2) continue
    out = out.replace(new RegExp(`\\b${escape(name.trim())}\\b`, 'gi'), BAR)
  }
  return out
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'screenshare',
      description: 'Hide private details on screen: /screenshare [on|off|add NAME|remove NAME|list]',
      argumentHint: '[on|off|add NAME|remove NAME|list]',
      immediate: true,
    })
    const saved = await $.store.get('names')
    if (Array.isArray(saved)) await update($, names, () => saved.filter((n): n is string => typeof n === 'string'))
    return next(e)
  })

  on('command.run', { command: 'screenshare' }, async ($, e) => {
    const args = e.args.trim()
    const verb = args.split(/\s+/)[0]?.toLowerCase() ?? ''
    const rest = args.slice(verb.length).trim()
    const people = await read($, names)

    if (verb === 'add' && rest.length > 1) {
      const next = [...people.filter(n => n.toLowerCase() !== rest.toLowerCase()), rest]
      await update($, names, () => next)
      await $.store.set('names', next)
      return { text: `Screen share will hide "${rest}" (${next.length} names on the list).` }
    }
    if (verb === 'remove' && rest.length > 0) {
      const next = people.filter(n => n.toLowerCase() !== rest.toLowerCase())
      await update($, names, () => next)
      await $.store.set('names', next)
      return { text: `Removed "${rest}" from the screen share list.` }
    }
    if (verb === 'list') {
      return { text: people.length === 0 ? 'No names on the list yet. Add one with /screenshare add NAME.' : `Hidden names: ${people.length} (not shown here, for safety).` }
    }
    const turnOn = verb === 'on' ? true : verb === 'off' ? false : !(await read($, isOn))
    await update($, isOn, () => turnOn)
    $.ui.status(turnOn ? 'SCREEN SHARE ON: private details hidden' : undefined)
    $.ui.invalidate('ui.render')
    return { text: turnOn ? 'Screen share mode is on. Names, emails, phone numbers, money and keys show as gray bars; tool details are hidden.' : 'Screen share mode is off.' }
  })

  on('ui.render', { component: 'UserMessage' }, async ($, e, next) => {
    if (!(await read($, isOn))) return next(e)
    return next({ ...e, props: { ...e.props, text: mask(e.props.text, await read($, names)) } })
  })

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    if (!(await read($, isOn))) return next(e)
    return next({ ...e, props: { ...e.props, text: mask(e.props.text, await read($, names)) } })
  })

  on('ui.render', { component: 'CommandOutput' }, async ($, e, next) => {
    if (!(await read($, isOn)) || e.props.command === 'screenshare') return next(e)
    return next({ ...e, props: { ...e.props, text: mask(e.props.text, await read($, names)) } })
  })

  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    if (!(await read($, isOn))) return next(e)
    const { Text } = $.ui.resolve(e)
    return <Text dimColor>{e.props.tool} {BAR} (details hidden for screen share)</Text>
  })

  on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
    if (!(await read($, isOn))) return next(e)
    const { Text } = $.ui.resolve(e)
    return <Text dimColor>  {BAR} output hidden</Text>
  })
}
