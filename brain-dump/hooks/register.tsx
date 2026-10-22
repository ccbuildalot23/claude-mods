import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { DumpKind, SavedDump } from '../types'

const dump = atom({ plugin: 'brain-dump', key: 'dump' } as const, { isOn: true, kind: 'dump' as DumpKind, original: '', tidy: '', isWorking: false, bypass: '', passNext: false, notice: '' })
const saved = atom({ plugin: 'brain-dump', key: 'saved' } as const, [] as SavedDump[])

const PANE = 'brain-dumps'
const LONG = 600

// First word routes the dump, the same words the Voice Inbox router reads.
const PRIVATE = /^\s*(private|vault|journal|recovery)\s*[:\-—]\s*/i
const LINE = /^\s*(line bank|poem line|line|labeau)\s*[:\-—]\s*/i

const SYSTEM = `You rewrite Chris's spoken brain dump into the best possible prompt for Claude Code, so Claude can act on it right away without asking for things the dump already answers. Follow Anthropic prompt-engineering practice: say exactly what is wanted, give context and the reason, separate parts with XML tags, list success criteria Claude can check, keep his own words where they carry decisions, and say what to do when something is unclear.

Background, use only what fits this dump: Chris runs LaBeau (faceless poetry and art brand: Substack, TikTok then Instagram, YouTube, a Facebook group) and Harmoniq (IT risk and GRC consulting). His system: repo labeau-ops, the agent bridge ~/Developer/grok-bridge (Grok chief of staff, Claude Code builder, Hermes overnight librarian, Muse for Meta), mods in ~/Developer/claude-mods, connectors such as Airtable, Blotato, Google Drive, Gmail, Calendar, Canva, Notion, and skills such as labeau-brand-voice, labeau-marketing and caldwell-executive-assistant. Standing rules to include when they apply: never write or change words in his poems; nothing sent, posted or bought without his yes; no private life in public copy; private or recovery material only goes to his Recovery vault; agents write full captions; he commits on the Mac himself, so hand him exact paste blocks.

Write it in first person as Chris, plain words, with these tags in this order, leaving out any that would be empty: <goal> (one or two sentences), <context> (bulleted), <what_i_said> (every concrete detail, grouped and bulleted, his wording for decisions, names, dates, numbers), <tasks> (numbered, in order), <tools> (only ones that fit), <rules> (only ones that apply), <verbatim_lines> (any poem lines or lyrics copied exactly, in quotes; never edited, completed or improved), <done_when> (a checklist), <open_questions> (only what is truly unclear; tell Claude to make its best call on the rest and say which), <how_to_reply> (short, bulleted, result first, end with my one next step). Add nothing he did not say or imply. Output only the prompt.`

// Pasted code, logs and stack traces are long too; only speech-like text is held.
function looksLikeDump(text: string): boolean {
  if (text.length < LONG || text.trim().startsWith('/') || text.includes('```')) return false
  const lines = text.split('\n').filter(l => l.trim().length > 0)
  const codey = lines.filter(l => /[{};]\s*$|^\s*(at |\$ |>>>|import |export |def |function |const |let |<\/?[a-z]+[ >])/.test(l)).length
  if (codey > Math.max(2, lines.length * 0.2)) return false
  const words = text.split(/\s+/).filter(w => /^[a-z']+[,.!?]?$/i.test(w)).length
  return words > text.split(/\s+/).length * 0.7
}

async function home($: EngineInterface): Promise<string> {
  return (await $.env.get('HOME')) ?? '.'
}

async function stamp($: EngineInterface): Promise<string> {
  return new Date(await $.clock.now()).toISOString().replace(/[:.]/g, '-').slice(0, 19)
}

// Two saves in the same second must not overwrite each other.
async function freshPath($: EngineInterface, base: string, ext: string): Promise<string> {
  let path = `${base}${ext}`
  for (let n = 2; await $.fs.exists(path).catch(() => false); n += 1) path = `${base}-${n}${ext}`
  return path
}

async function inboxDir($: EngineInterface): Promise<string> {
  return `${await home($)}/Developer/claude-mods/brain-dump/inbox`
}

// Hands a dump to the Voice Inbox router, which files Line dumps into the line bank
// word for word and everything else into the Recovery vault. Nothing goes to Claude.
async function toVoiceInbox($: EngineInterface, trigger: 'Private' | 'Line', body: string): Promise<string> {
  const path = await freshPath($, `${await home($)}/Voice Inbox/braindump-${await stamp($)}`, '.txt')
  await $.fs.write(path, `${trigger}\n\n${body}\n`)
  return path
}

async function saveForLater($: EngineInterface, text: string): Promise<string> {
  const path = await freshPath($, `${await inboxDir($)}/dump-${await stamp($)}`, '.md')
  await $.fs.write(path, `${text}\n`)
  await refreshSaved($)
  return path
}

async function refreshSaved($: EngineInterface): Promise<void> {
  const dir = await inboxDir($)
  const done = ((await $.store.get('done')) as string[] | undefined) ?? []
  const entries = await $.fs.list(dir).catch(() => [])
  const files = entries.filter(f => f.kind === 'file' && f.name.endsWith('.md') && !done.includes(f.name)).sort((a, b) => b.mtimeMs - a.mtimeMs).slice(0, 20)
  const list: SavedDump[] = []
  for (const f of files) {
    const text = await $.fs.read(`${dir}/${f.name}`).catch(() => '')
    list.push({ path: `${dir}/${f.name}`, name: f.name, preview: text.replace(/\s+/g, ' ').trim().slice(0, 120), mtimeMs: f.mtimeMs })
  }
  await update($, saved, () => list)
}

async function clear($: EngineInterface, notice: string): Promise<void> {
  await update($, dump, v => ({ ...v, kind: 'dump' as const, original: '', tidy: '', notice }))
}

async function tidy($: EngineInterface): Promise<void> {
  const d = await read($, dump)
  await update($, dump, v => ({ ...v, isWorking: true }))
  const r = await $.model.complete({ model: 'haiku', system: SYSTEM, prompt: d.original, maxTokens: 2000 })
  await update($, dump, v => ({ ...v, isWorking: false, tidy: r.isAnswered ? r.text : '' }))
  if (!r.isAnswered) $.ui.toast(`brain-dump: could not tidy (${r.reason}); send the original or try again.`)
}

async function send($: EngineInterface, text: string): Promise<void> {
  await update($, dump, v => ({ ...v, kind: 'dump' as const, original: '', tidy: '', notice: '', bypass: text }))
  await $.prompt.submit({ text, asUser: true })
}

async function editFirst($: EngineInterface, text: string): Promise<void> {
  const r = await $.prompt.fill({ text })
  if (!r.isFilled) {
    $.ui.toast('brain-dump: could not put it in the prompt box; use Copy instead.')
    return
  }
  await update($, dump, v => ({ ...v, kind: 'dump' as const, original: '', tidy: '', notice: '', passNext: true }))
}

async function file($: EngineInterface, trigger: 'Private' | 'Line'): Promise<void> {
  const d = await read($, dump)
  const body = d.original.replace(trigger === 'Private' ? PRIVATE : LINE, '')
  const path = await toVoiceInbox($, trigger, body).catch(() => '')
  if (path.length === 0) {
    $.ui.toast('brain-dump: could not write to ~/Voice Inbox. Your dump is still held; copy it to keep it.')
    return
  }
  await clear($, trigger === 'Private' ? 'Sent to the Recovery vault inbox. Claude never saw it.' : 'Sent to the line bank inbox, word for word.')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'braindump', description: 'Brain dump catcher: /braindump on|off|status (Private: is always held), or /braindump save TEXT to keep a thought for later', argumentHint: 'on|off|status|save TEXT', immediate: true })
    await $.command.register({ name: 'dumps', description: 'Open your saved brain dumps beside the chat', immediate: true })
    const isOn = await $.store.get('isOn')
    await update($, dump, v => ({ ...v, isOn: isOn !== false }))
    await refreshSaved($)
    return next(e)
  })

  on('command.run', { command: 'braindump' }, async ($, e) => {
    const args = e.args.trim()
    const word = args.split(/\s+/)[0]?.toLowerCase() ?? ''
    if (word === 'save') {
      const text = args.slice(4).trim()
      if (text.length === 0) return { text: 'Usage: /braindump save your thought here' }
      const path = await saveForLater($, text)
      return { text: `Saved for later: ${path}. /dumps shows it.` }
    }
    if (word === 'status') {
      const d = await read($, dump)
      const list = await read($, saved)
      return { text: `Brain dump catcher is ${d.isOn ? 'on' : 'off'}; ${list.length} saved dump${list.length === 1 ? '' : 's'} waiting (/dumps).` }
    }
    const turnOn = word !== 'off'
    await update($, dump, v => ({ ...v, isOn: turnOn }))
    await $.store.set('isOn', turnOn)
    return { text: `Brain dump catcher is ${turnOn ? 'on' : 'off'}.` }
  })

  on('command.run', { command: 'dumps' }, async $ => {
    await refreshSaved($)
    await $.ui.open({ id: PANE, title: 'Brain dumps' })
    return { text: 'Brain dumps opened.' }
  })

  on('prompt.submit', async ($, e, next) => {
    const d = await read($, dump)
    const text = e.text
    if (text === d.bypass) {
      await update($, dump, v => ({ ...v, bypass: '' }))
      return next(e)
    }
    if (e.origin.kind !== 'composer') return next(e)
    if (d.passNext) {
      await update($, dump, v => ({ ...v, passNext: false }))
      return next(e)
    }
    // The private guard stays on even with the catcher off: Private: never reaches Claude.
    if (PRIVATE.test(text)) {
      await update($, dump, v => ({ ...v, kind: 'private' as const, original: text, tidy: '', notice: '' }))
      return { drop: 'Held a private dump. It has not gone to Claude: choose Send to vault or Discard above the prompt.' }
    }
    if (!d.isOn) return next(e)
    if (LINE.test(text)) {
      await update($, dump, v => ({ ...v, kind: 'line' as const, original: text, tidy: '', notice: '' }))
      return { drop: 'Held your line: choose To line bank or Send to Claude above the prompt.' }
    }
    if (!looksLikeDump(text)) return next(e)
    await update($, dump, v => ({ ...v, kind: 'dump' as const, original: text, tidy: '', notice: '' }))
    return { drop: 'Held your brain dump: choose Tidy it, Send as is or Save for later above the prompt.' }
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const d = await read($, dump)
    if (e.props.hasSurvey) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    if (d.original.length === 0) {
      if (d.notice.length === 0) return next(e)
      return (
        <Box flexDirection="row">
          <Text color="green">{d.notice} </Text>
          <Button key="ok" label="OK" onPress={() => update($, dump, v => ({ ...v, notice: '' }))} />
        </Box>
      )
    }
    if (d.kind === 'private') {
      return (
        <Box flexDirection="row">
          <Text color="magenta">Private dump held ({d.original.length} chars). Claude has not seen it. </Text>
          <Button key="vault" variant="primary" label="Send to vault" onPress={() => file($, 'Private')} />
          <Button key="discard" label="Discard" onPress={() => clear($, 'Private dump discarded.')} />
        </Box>
      )
    }
    if (d.kind === 'line') {
      return (
        <Box flexDirection="row">
          <Text color="yellow">Line held, kept word for word. </Text>
          <Button key="line" variant="primary" label="To line bank" onPress={() => file($, 'Line')} />
          <Button key="as-is" label="Send to Claude" onPress={() => send($, d.original)} />
        </Box>
      )
    }
    if (d.isWorking) return <Text dimColor>Tidying your brain dump...</Text>
    if (d.tidy.length > 0) {
      const tidyText = d.tidy
      return (
        <Box flexDirection="column">
          <Text dimColor>{tidyText.length > 600 ? tidyText.slice(0, 600) + '...' : tidyText}</Text>
          <Box flexDirection="row">
            <Button key="send-tidy" variant="primary" label="Send tidy" onPress={() => send($, tidyText)} />
            <Button key="edit" label="Edit first" onPress={() => editFirst($, tidyText)} />
            <Button key="send-orig" label="Send original" onPress={() => send($, d.original)} />
            <Button key="copy" label="Copy tidy" onPress={press => $.ui.copy({ text: tidyText, surface: press.surface })} />
          </Box>
        </Box>
      )
    }
    return (
      <Box flexDirection="row">
        <Text color="cyan">Long brain dump caught ({d.original.length} chars). </Text>
        <Button key="tidy" variant="primary" label="Tidy it" onPress={() => tidy($)} />
        <Button key="as-is" label="Send as is" onPress={() => send($, d.original)} />
        <Button key="later" label="Save for later" onPress={async () => {
          const path = await saveForLater($, d.original)
          await clear($, `Saved for later (${path.split('/').pop()}). /dumps shows it.`)
        }} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const list = await read($, saved)
    const room = Math.max(1, Math.floor(((e.viewport?.rows ?? 24) - 3) / 3))
    return (
      <Box flexDirection="column">
        {list.length === 0 && <Text dimColor>No saved dumps. Press Save for later on a held dump, or /braindump save TEXT.</Text>}
        {list.slice(0, room).map(one => (
          <Box key={one.name} flexDirection="column">
            <Text>{one.preview}</Text>
            <Box flexDirection="row">
              <Button key={`work-${one.name}`} label="Work on this" onPress={async () => {
                const text = await $.fs.read(one.path).catch(() => '')
                if (text.length > 0) await editFirst($, text.trim())
              }} />
              <Button key={`done-${one.name}`} label="Done" onPress={async () => {
                const done = ((await $.store.get('done')) as string[] | undefined) ?? []
                await $.store.set('done', [...done, one.name].slice(-500))
                await refreshSaved($)
              }} />
            </Box>
          </Box>
        ))}
      </Box>
    )
  })
}
