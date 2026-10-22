import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { SwitchboardSeen } from '../types'

// Chris's suite: each answers `/<command> on|off`. Locked ones stay on.
const SUITE: { name: string; command?: string; what: string; isLocked?: boolean }[] = [
  { name: 'blast-radius', what: 'Stops risky deletes and resets until you press Proceed; pen-rule folders blocked', isLocked: true },
  { name: 'screen-share', command: 'screenshare', what: 'Gray bars over names, emails, money, keys' },
  { name: 'helper-desk', command: 'helperdesk', what: 'Progress bar and a panel of subagents' },
  { name: 'cache-clock', command: 'cacheclock', what: 'Countdown until the chat goes cold; /keepwarm' },
  { name: 'handoff', command: 'handoff-mod', what: 'Writes a fresh-chat handoff prompt' },
  { name: 'reflect', command: 'reflect', what: 'Spots rules you give and offers to save them' },
  { name: 'chat-inventory', command: 'inventory', what: 'Panel of tools, connectors, skills and files used' },
  { name: 'replay-theater', command: 'replay-mod', what: 'Steps through every file edit Claude made' },
  { name: 'brain-dump', command: 'braindump', what: 'Tidies long voice dumps into a clear prompt (uses AI)' },
  { name: 'heads-up', command: 'headsup', what: 'Pops up what you must not miss in long replies (uses AI)' },
  { name: 'skins', command: 'skin', what: 'Icons and colors for tool calls' },
  { name: 'browser-peek', what: 'Screenshot a page into a panel with /peek URL' },
]

const PANE = 'switchboard'
const off = atom({ plugin: 'switchboard', key: 'off' } as const, [])
const seen = atom({ plugin: 'switchboard', key: 'seen' } as const, [])
const blocked = atom({ plugin: 'switchboard', key: 'blocked' } as const, [])

const NEVER_BLOCK = new Set(['switchboard', 'blast-radius'])

async function toggle($: EngineInterface, name: string): Promise<void> {
  const mod = SUITE.find(m => m.name === name)
  if (mod === undefined || mod.command === undefined || mod.isLocked === true) return
  const isOff = (await read($, off)).includes(name)
  await $.command.run({ command: mod.command, args: isOff ? 'on' : 'off' })
  const next = isOff ? (await read($, off)).filter(n => n !== name) : [...(await read($, off)), name]
  await update($, off, () => next)
  await $.store.set('off', next)
}

async function toggleBlock($: EngineInterface, name: string): Promise<void> {
  if (NEVER_BLOCK.has(name)) return
  const list = await read($, blocked)
  const next = list.includes(name) ? list.filter(n => n !== name) : [...list, name]
  await update($, blocked, () => next)
  await $.store.set('blocked', next)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'mods', description: 'Open the switchboard: see and switch mods on or off', immediate: true })
    const savedBlocked = await $.store.get('blocked')
    if (Array.isArray(savedBlocked)) await update($, blocked, () => savedBlocked.filter((n): n is string => typeof n === 'string'))
    const savedOff = await $.store.get('off')
    if (Array.isArray(savedOff)) await update($, off, () => savedOff.filter((n): n is string => typeof n === 'string'))
    return next(e)
  })

  // Every hooks module that loads passes here; blocked ones are refused.
  on('plugin.register', async ($, e, next) => {
    const list: SwitchboardSeen = (await read($, seen)).filter(p => p.name !== e.name)
    await update($, seen, () => [...list, { name: e.name, provenance: e.provenance }])
    const saved = await $.store.get('blocked')
    if (Array.isArray(saved) && saved.includes(e.name) && !NEVER_BLOCK.has(e.name)) {
      return { refuse: `switchboard: ${e.name} is switched off. Turn it back on with /mods.` }
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('command.run', { command: 'mods' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Switchboard' })
    return { text: 'Switchboard opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const offList = await read($, off)
    const seenList = await read($, seen)
    const blockedList = await read($, blocked)
    const others = seenList.filter(p => !SUITE.some(m => m.name === p.name) && p.name !== 'switchboard')

    return (
      <Box flexDirection="column">
        <Text bold>Chris's mods</Text>
        {SUITE.map(mod => {
          const isOff = offList.includes(mod.name) || blockedList.includes(mod.name)
          return (
            <Box flexDirection="column">
              <Text>
                {mod.isLocked === true ? 'LOCKED ON ' : isOff ? 'off  ' : 'on   '}
                {mod.name} <Text dimColor>{mod.what}</Text>
              </Text>
              {mod.isLocked !== true && mod.command !== undefined && (
                <Button key={`t:${mod.name}`} label={isOff ? 'Turn on' : 'Turn off'} onPress={() => toggle($, mod.name)} />
              )}
            </Box>
          )
        })}
        <Text bold>Other plugins seen loading</Text>
        {others.length === 0 && <Text dimColor>None seen yet this session.</Text>}
        {others.map(p => (
          <Box flexDirection="column">
            <Text>
              {blockedList.includes(p.name) ? 'blocked ' : 'loaded  '}
              {p.name} <Text dimColor>{p.provenance}</Text>
            </Text>
            <Button key={`b:${p.name}`} label={blockedList.includes(p.name) ? 'Allow next load' : 'Block next load'} onPress={() => toggleBlock($, p.name)} />
          </Box>
        ))}
        <Text dimColor>Blocking takes effect at /reload-plugins or the next session. blast-radius stays on by design.</Text>
      </Box>
    )
  })
}
