import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const state = atom({ plugin: 'reflect', key: 'state' } as const, { isOn: true, candidate: '', savedCount: 0, promote: '' })

const RULE = /\b(never|always|from now on|going forward|every time|don'?t ever|do not ever|stop (doing|using|adding)|i don'?t want|make sure (you|to) always|rule:|no more)\b/i

// The sentence that holds the rule, not the whole prompt.
function pickRule(text: string): string | undefined {
  if (text.trim().startsWith('/')) return undefined
  const sentences = text.split(/(?<=[.!?\n])\s+/)
  const hit = sentences.find(s => RULE.test(s) && s.length >= 12 && s.length <= 400)
  return hit?.trim()
}

// The accepted-twice rule (Idea Register row 117): a rule Chris gives a second time, unchanged, is offered for
// promotion into his CLAUDE.md. Unchanged means the same words once case, spacing and end punctuation are set aside.
export const same = (a: string): string => a.toLowerCase().replace(/[\s"'.,!;:]+/g, ' ').trim()

async function inboxPath($: EngineInterface): Promise<string> {
  return `${(await $.env.get('HOME')) ?? '.'}/Developer/claude-mods/rules-inbox.md`
}

async function givenBefore($: EngineInterface, rule: string): Promise<boolean> {
  const inbox = await $.fs.read(await inboxPath($)).catch(() => '')
  return inbox.split('\n').some(l => /^- \d{4}-\d{2}-\d{2} \| /.test(l) && !l.endsWith('[promoted]') && same(l.replace(/^- \d{4}-\d{2}-\d{2} \| /, '')) === same(rule))
}

async function promote($: EngineInterface, rule: string): Promise<void> {
  const home = (await $.env.get('HOME')) ?? '.'
  const target = `${home}/.claude/CLAUDE.md`
  const day = new Date(await $.clock.now()).toISOString().slice(0, 10)
  let doc = await $.fs.read(target).catch(() => '')
  const heading = '## Rules promoted from the inbox'
  if (!doc.includes(heading)) doc = `${doc.trimEnd()}\n\n${heading}\nRules Chris gave twice, unchanged, promoted by his press of Promote (reflect mod).\n`
  await $.fs.write(target, `${doc.trimEnd()}\n- ${rule.replace(/\n/g, ' ')} (promoted ${day})\n`)
  const inboxFile = await inboxPath($)
  const inbox = await $.fs.read(inboxFile).catch(() => '')
  await $.fs.write(inboxFile, inbox.split('\n').map(l => (/^- \d{4}-\d{2}-\d{2} \| /.test(l) && same(l.replace(/^- \d{4}-\d{2}-\d{2} \| /, '')) === same(rule) ? `${l} [promoted]` : l)).join('\n'))
  await update($, state, s => ({ ...s, promote: '', candidate: '' }))
  $.ui.toast(`Promoted to ${target}`)
}

async function save($: EngineInterface, rule: string): Promise<void> {
  const path = await inboxPath($)
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
      if (rule !== undefined) {
        const twice = await givenBefore($, rule)
        await update($, state, v => ({ ...v, candidate: twice ? '' : rule, promote: twice ? rule : '' }))
      }
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, state)
    if (e.props.hasSurvey || !s.isOn) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    if (s.promote.length > 0) {
      const rule = s.promote
      return (
        <Box flexDirection="column">
          <Text color="cyan">You've given this rule twice, unchanged. Promote it to ~/.claude/CLAUDE.md?</Text>
          <Text dimColor>+ - {rule.length > 140 ? rule.slice(0, 140) + '...' : rule}</Text>
          <Box flexDirection="row">
            <Button key="promote" label="Promote" onPress={() => promote($, rule)} />
            <Button key="later" label="Not yet" onPress={() => update($, state, v => ({ ...v, promote: '' }))} />
          </Box>
        </Box>
      )
    }
    if (s.candidate.length === 0) return next(e)
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
