import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const state = atom({ plugin: 'reflect', key: 'state' } as const, { isOn: true, candidate: '', savedCount: 0 })

const RULE = /\b(never|always|from now on|going forward|every time|don'?t ever|do not ever|stop (doing|using|adding)|i don'?t want|make sure (you|to) always|rule:|no more)\b/i

// The sentence that holds the rule, not the whole prompt.
function pickRule(text: string): string | undefined {
  if (text.trim().startsWith('/')) return undefined
  const sentences = text.split(/(?<=[.!?\n])\s+/)
  const hit = sentences.find(s => RULE.test(s) && s.length >= 12 && s.length <= 400)
  return hit?.trim()
}

async function save($: EngineInterface, rule: string): Promise<void> {
  const home = (await $.env.get('HOME')) ?? '.'
  const path = `${home}/Developer/claude-mods/rules-inbox.md`
  let current = '# Rules inbox\nRules Chris gave in chat, caught by the reflect mod. Promote the keepers into CLAUDE.md or a skill by hand; delete the rest.\n\n'
  try {
    current = await $.fs.read(path)
  } catch {
    // first rule: start the file
  }
  const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
  await $.fs.write(path, `${current}- ${day} | ${rule.replace(/\n/g, ' ')}\n`)
  await update($, state, s => ({ ...s, candidate: '', savedCount: s.savedCount + 1 }))
  $.ui.toast(`Saved to ${path}`)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'reflect', description: 'Rule spotting on or off', argumentHint: 'on|off', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'reflect' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, state, s => ({ ...s, isOn: turnOn, candidate: turnOn ? s.candidate : '' }))
    return { text: `Reflect is ${turnOn ? 'on' : 'off'}.` }
  })

  on('prompt.submit', async ($, e, next) => {
    const s = await read($, state)
    if (s.isOn) {
      const rule = pickRule(e.text)
      if (rule !== undefined) await update($, state, v => ({ ...v, candidate: rule }))
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, state)
    if (e.props.hasSurvey || !s.isOn || s.candidate.length === 0) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    const rule = s.candidate
    return (
      <Box flexDirection="row">
        <Text color="cyan">Save as a lasting rule? </Text>
        <Text dimColor>"{rule.length > 90 ? rule.slice(0, 90) + '...' : rule}" </Text>
        <Button key="save" label="Save" onPress={() => save($, rule)} />
        <Button key="skip" label="Not a rule" onPress={() => update($, state, v => ({ ...v, candidate: '' }))} />
      </Box>
    )
  })
}
