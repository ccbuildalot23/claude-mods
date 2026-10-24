import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

const state = atom({ plugin: 'heads-up', key: 'state' } as const, { isOn: true, note: '' })

const LONG = 1200
const ASK = `You read an AI assistant's reply on behalf of Chris, who skims. List at most 2 things he must not miss: money it would cost, anything irreversible, deadlines, anything waiting on his yes, security or privacy risks. One short line each, starting with "- ". If nothing qualifies, reply exactly NONE.`

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'headsup', description: 'Flags what you must not miss in long replies: /headsup on|off', argumentHint: 'on|off', immediate: true })
    const saved = await $.store.get('isOn')
    if (saved === false) await update($, state, v => ({ ...v, isOn: false }))
    return next(e)
  })

  on('command.run', { command: 'headsup' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, state, v => ({ ...v, isOn: turnOn, note: '' }))
    await $.store.set('isOn', turnOn)
    return { text: `Heads-up is ${turnOn ? 'on' : 'off'}.` }
  })

  on('prompt.submit', async ($, e, next) => {
    await update($, state, v => ({ ...v, note: '' }))
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    const s = await read($, state)
    if (!s.isOn || e.agentId !== undefined || e.answer.length < LONG) return done
    // In the background: the turn ends now and the note shows up a moment later, so Chris never waits on it.
    void (async () => {
      const r = await $.model.complete({ model: 'haiku', system: ASK, prompt: e.answer.slice(0, 30000), maxTokens: 200, effort: 'low' })
      if (r.isAnswered && !/^\s*NONE\s*$/i.test(r.text)) {
        await update($, state, v => ({ ...v, note: r.text.trim() }))
        $.ui.toast(`You should know:\n${r.text.trim()}`, { timeoutMs: 12000 })
      }
    })().catch(() => undefined)
    return done
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, state)
    if (e.props.hasSurvey || !s.isOn || s.note.length === 0) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    return (
      <Box flexDirection="row">
        <Text color="yellow">You should know: </Text>
        <Text>{s.note.replace(/\n/g, '  ')} </Text>
        <Button key="ok" label="Got it" onPress={() => update($, state, v => ({ ...v, note: '' }))} />
      </Box>
    )
  })
}
