import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Replay } from '../types'

const PANE = 'replay-theater'
const START: Replay = { isOn: true, edits: [], turn: 0, at: 0, lastTurnEdits: 0 }
const replay = atom({ plugin: 'replay-theater', key: 'replay' } as const, START)

const CAP = 6000

function diff(path: string, before: string, after: string): string {
  const a = before.length > CAP ? before.slice(0, CAP).split('\n').concat(['... (cut)']) : before.split('\n')
  const b = after.length > CAP ? after.slice(0, CAP).split('\n').concat(['... (cut)']) : after.split('\n')
  const head = `--- a/${path}\n+++ b/${path}\n@@ -1,${a.length} +1,${b.length} @@\n`
  return head + a.map(l => `-${l}`).join('\n') + '\n' + b.map(l => `+${l}`).join('\n')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'replay', description: 'Step through the file edits Claude made in its last reply', immediate: true })
    await $.command.register({ name: 'replay-mod', description: 'Replay theater on or off', argumentHint: 'on|off', immediate: true })
    return next(e)
  })

  on('command.run', { command: 'replay-mod' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, replay, r => ({ ...r, isOn: turnOn }))
    return { text: `Replay theater is ${turnOn ? 'on' : 'off'}.` }
  })

  on('command.run', { command: 'replay' }, async $ => {
    const r = await read($, replay)
    const mine = r.edits.filter(x => x.turn === r.turn)
    if (mine.length === 0) return { text: 'No file edits in the last reply to replay.' }
    await update($, replay, v => ({ ...v, at: 0 }))
    await $.ui.open({ id: PANE, title: 'Replay theater' })
    return { text: `Replaying ${mine.length} edit${mine.length === 1 ? '' : 's'}.` }
  })

  on('prompt.submit', async ($, e, next) => {
    if (!e.text.trim().startsWith('/')) await update($, replay, r => ({ ...r, turn: r.turn + 1, lastTurnEdits: 0 }))
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const r0 = await read($, replay)
    if (!r0.isOn || (e.tool !== 'Edit' && e.tool !== 'Write')) return next(e)
    let before = ''
    if (e.tool === 'Write') {
      try {
        before = await $.fs.read(e.file_path)
      } catch {
        before = ''
      }
    }
    const ran = await next(e)
    if (ran.deny !== undefined || ran.isError === true) return ran
    const text = e.tool === 'Edit' ? diff(e.file_path, e.old_string, e.new_string) : diff(e.file_path, before, e.content)
    await update($, replay, r => ({ ...r, edits: [...r.edits, { path: e.file_path, diff: text, turn: r.turn }].slice(-200), lastTurnEdits: r.lastTurnEdits + 1 }))
    return ran
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const r = await read($, replay)
    if (e.props.hasSurvey || !r.isOn || r.lastTurnEdits === 0) return next(e)
    const { Box, Text, Button } = $.ui.resolve(e)
    return (
      <Box flexDirection="row">
        <Text dimColor>{r.lastTurnEdits} file edit{r.lastTurnEdits === 1 ? '' : 's'} this reply </Text>
        <Button key="replay" label="Replay" onPress={async () => {
          await update($, replay, v => ({ ...v, at: 0 }))
          await $.ui.open({ id: PANE, title: 'Replay theater' })
        }} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Code } = $.ui.resolve(e)
    const r = await read($, replay)
    const mine = r.edits.filter(x => x.turn === r.turn)
    const list = mine.length > 0 ? mine : r.edits
    const at = Math.min(r.at, Math.max(0, list.length - 1))
    const edit = list[at]
    if (edit === undefined) return <Text dimColor>No edits to replay.</Text>
    return (
      <Box flexDirection="column">
        <Text bold>
          Edit {at + 1} of {list.length}: {edit.path}
        </Text>
        <Box flexDirection="row">
          <Button key="prev" label="Prev" onPress={() => update($, replay, v => ({ ...v, at: Math.max(0, at - 1) }))} />
          <Button key="next" label="Next" onPress={() => update($, replay, v => ({ ...v, at: Math.min(list.length - 1, at + 1) }))} />
        </Box>
        <Code source={edit.diff} format="diff" />
      </Box>
    )
  })
}
