import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const state = atom({ plugin: 'handoff', key: 'state' } as const, { isOn: true, contextTokens: 0, lastTurnAt: 0, isDismissed: false, lastText: '', lastPath: '' })

const BIG = 250000
const COLD_MS = 60 * 60 * 1000

const ASK = `Write a handoff prompt so a brand-new Claude Code chat can pick up this work exactly where we are, with nothing lost. Use these headings:
1. Goal (what Chris is trying to get done, in one or two lines)
2. Where we are (done, in progress, not started)
3. Decisions made and why (include Chris's own words verbatim where he decided something)
4. Files read, created or changed (full paths) and what each is for
5. Skills, connectors, tools and links used
6. Open questions and anything waiting on Chris's yes
7. Rules that apply (pen rule: AI never writes or edits Chris's poems; nothing sent, posted or bought without his yes; no private life in public copy; changes to labeau-ops go through its Outbox)
8. The exact next step
Write it as a prompt addressed to the new chat. Do not include secrets, keys or recovery/health/legal details; name the category only.`

// /wrap closes a session (Oct 22, 2026, shortlist item 9). The closing question is for Chris to answer in
// his own words; the AI never answers it or writes diary lines for him.
const WRAP = `Close this session for Chris in under 15 lines, plain words, no headings beyond these three:
Done: what got finished this session (bullets, one line each, with file paths where useful).
Still open: what is unfinished or waiting on Chris's yes, and the one next step.
For you: one short question for Chris to answer in his own words about this session (what he learned, what felt off, what he'd change). Ask it; never answer it.
Do not include secrets, keys or recovery, health, legal or money details; name the category only.`

async function writeWrap($: EngineInterface): Promise<string> {
  const r = await $.model.fork({ prompt: WRAP })
  if (!r.isAnswered) return `The wrap could not be written (${r.reason}).`
  const home = (await $.env.get('HOME')) ?? '.'
  const stamp = new Date(await $.clock.now()).toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const path = `${home}/Developer/claude-mods/handoffs/wrap-${stamp}.md`
  await $.fs.write(path, r.text)
  return `${r.text}\n\nSaved to ${path}. Answer the question in your own words whenever you like; nothing else needs doing.`
}

async function writeHandoff($: EngineInterface): Promise<string> {
  const r = await $.model.fork({ prompt: ASK })
  if (!r.isAnswered) return `Handoff could not be written (${r.reason}).`
  const home = (await $.env.get('HOME')) ?? '.'
  const stamp = new Date(await $.clock.now()).toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const path = `${home}/Developer/claude-mods/handoffs/handoff-${stamp}.md`
  await $.fs.write(path, r.text)
  await update($, state, s => ({ ...s, lastText: r.text, lastPath: path, isDismissed: true }))
  return path
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'handoff', description: 'Write a detailed handoff prompt for a fresh chat (uses one AI call over this chat)' })
    await $.command.register({ name: 'wrap', description: 'Close this session: what got done, what is open, and one question for you (uses one AI call)' })
    await $.command.register({ name: 'handoff-mod', description: 'Handoff suggestions on or off', argumentHint: 'on|off', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'handoff-mod' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, state, s => ({ ...s, isOn: turnOn }))
    return { text: `Handoff suggestions are ${turnOn ? 'on' : 'off'}. /handoff still works either way.` }
  })

  on('command.run', { command: 'wrap' }, async $ => ({ text: await writeWrap($) }))

  on('command.run', { command: 'handoff' }, async $ => {
    const path = await writeHandoff($)
    const s = await read($, state)
    if (s.lastPath !== path) return { text: path }
    return { text: `Handoff saved to ${path}. Copy it with the button above the prompt, then open a new chat and paste it.\n\n${s.lastText}` }
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined) {
      const usage = await $.session.usage()
      const now = await $.clock.now()
      await update($, state, s => ({ ...s, contextTokens: usage.context.tokens ?? s.contextTokens, lastTurnAt: now }))
    }
    return done
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, state)
    if (e.props.hasSurvey || !s.isOn) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    if (s.lastText.length > 0) {
      return (
        <Box flexDirection="row">
          <Text dimColor>Handoff ready </Text>
          <Button
            key="copy"
            label="Copy handoff"
            onPress={async press => {
              // Where the app cannot take it onto the clipboard, say where the text is instead of failing quietly.
              const r = await $.ui.copy({ text: s.lastText, surface: press.surface })
              if (!r.isCopied) $.ui.toast(`Could not copy here; the handoff is in the /handoff reply and saved at ${s.lastPath}.`)
            }}
          />
          <Button key="clear" label="Done" onPress={() => update($, state, v => ({ ...v, lastText: '' }))} />
        </Box>
      )
    }
    const isBig = s.contextTokens > BIG
    const isCold = s.lastTurnAt > 0 && (await $.clock.now()) - s.lastTurnAt > COLD_MS
    if (s.isDismissed || (!isBig && !isCold)) return next(e)
    return (
      <Box flexDirection="row">
        <Text color="yellow">{isBig ? `This chat is past ${Math.round(s.contextTokens / 1000)}k tokens.` : 'This chat has gone cold.'} A fresh chat would be sharper and cheaper. </Text>
        <Button key="write" label="Write handoff" onPress={() => writeHandoff($)} />
        <Button key="dismiss" label="Not now" onPress={() => update($, state, v => ({ ...v, isDismissed: true }))} />
      </Box>
    )
  })
}
