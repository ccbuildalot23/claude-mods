import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const dump = atom({ plugin: 'brain-dump', key: 'dump' } as const, { isOn: false, original: '', tidy: '', isWorking: false, bypass: '' })

const LONG = 900

const SYSTEM = `You turn a person's messy spoken brain dump into a clear prompt for Claude Code. Fix obvious transcription errors and order the thoughts, using these headings: Task, Why, Guardrails, What done looks like, Open questions. Keep the person's meaning and decisions; add nothing they did not say. Hard rule: any poem lines, lyrics or creative writing in the dump are copied verbatim inside quotes, never edited, completed or improved. Output only the prompt.`

async function tidy($: EngineInterface): Promise<void> {
  const d = await read($, dump)
  await update($, dump, v => ({ ...v, isWorking: true }))
  const r = await $.model.complete({ model: 'haiku', system: SYSTEM, prompt: d.original, maxTokens: 2000 })
  await update($, dump, v => ({ ...v, isWorking: false, tidy: r.isAnswered ? r.text : '' }))
  if (!r.isAnswered) $.ui.toast(`brain-dump: could not tidy (${r.reason}); send the original or try again.`)
}

async function send($: EngineInterface, text: string): Promise<void> {
  await update($, dump, v => ({ ...v, original: '', tidy: '', bypass: text }))
  await $.prompt.submit({ text, asUser: true })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'braindump', description: 'Catch long brain dumps and offer a tidy prompt: /braindump on|off', argumentHint: 'on|off', immediate: true })
    const saved = await $.store.get('isOn')
    if (saved === true) await update($, dump, v => ({ ...v, isOn: true }))
    return next(e)
  })

  on('command.run', { command: 'braindump' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, dump, v => ({ ...v, isOn: turnOn }))
    await $.store.set('isOn', turnOn)
    return { text: `Brain dump catcher is ${turnOn ? 'on' : 'off'}.` }
  })

  on('prompt.submit', async ($, e, next) => {
    const d = await read($, dump)
    const text = e.text
    if (text === d.bypass) {
      await update($, dump, v => ({ ...v, bypass: '' }))
      return next(e)
    }
    if (!d.isOn || text.length < LONG || text.trim().startsWith('/') || e.origin.kind !== 'composer') return next(e)
    await update($, dump, v => ({ ...v, original: text, tidy: '' }))
    return { drop: 'Held your brain dump: choose Tidy it or Send as is above the prompt.' }
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const d = await read($, dump)
    if (e.props.hasSurvey || d.original.length === 0) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    if (d.isWorking) return <Text dimColor>Tidying your brain dump...</Text>
    if (d.tidy.length > 0) {
      const tidyText = d.tidy
      return (
        <Box flexDirection="column">
          <Text dimColor>{tidyText.length > 600 ? tidyText.slice(0, 600) + '...' : tidyText}</Text>
          <Box flexDirection="row">
            <Button key="send-tidy" variant="primary" label="Send tidy" onPress={() => send($, tidyText)} />
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
      </Box>
    )
  })
}
