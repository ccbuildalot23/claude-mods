import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

// Lighter-week switch (Idea Register row 135): /lightweek tells every Claude session on this Mac, Rig seats
// and scheduled runs included, to drop to essentials for seven days. The switch is a file,
// ~/Developer/claude-mods/config/lightweek.json, so every session reads the same answer. Uses no AI.

const until = atom({ plugin: 'lightweek', key: 'until' } as const, 0)

const DAY = 24 * 60 * 60 * 1000

async function file($: EngineInterface): Promise<string> {
  return `${(await $.env.get('HOME')) ?? '.'}/Developer/claude-mods/config/lightweek.json`
}

async function refresh($: EngineInterface): Promise<number> {
  try {
    const v = JSON.parse(await $.fs.read(await file($))) as { until?: string }
    const t = v.until === undefined ? 0 : Date.parse(v.until)
    const live = Number.isFinite(t) && t > (await $.clock.now()) ? t : 0
    await update($, until, () => live)
    return live
  } catch {
    await update($, until, () => 0)
    return 0
  }
}

export function guidance(endsOn: string): string {
  return `Light week (Chris's switch, until ${endsOn}). Keep to essentials: posts already scheduled, anything with a deadline before ${endsOn}, and fixes to things that broke. Do not start new builds, new routines or new research; if a request would start one, say it can wait until after ${endsOn} and offer the smallest useful step instead. Keep replies short, one ask at a time.`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'lightweek', description: 'Tell every session to keep to essentials for a while: /lightweek [days, default 7] or /lightweek off', argumentHint: '[days | off]', immediate: true })
    await refresh($)
    return next(e)
  })

  on('command.run', { command: 'lightweek' }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'off') {
      await $.fs.write(await file($), JSON.stringify({ until: null, endedAt: new Date(await $.clock.now()).toISOString() }, null, 2))
      await update($, until, () => 0)
      return { text: 'Light week is off. Sessions are back to normal from their next message.' }
    }
    if (arg === 'status') {
      const t = await refresh($)
      return { text: t === 0 ? 'Light week is off.' : `Light week until ${new Date(t).toDateString()}.` }
    }
    const days = Math.min(Math.max(Number.parseInt(arg, 10) || 7, 1), 30)
    const t = (await $.clock.now()) + days * DAY
    await $.fs.write(await file($), JSON.stringify({ until: new Date(t).toISOString(), days, setAt: new Date(await $.clock.now()).toISOString() }, null, 2))
    await update($, until, () => t)
    return { text: `Light week is on for ${days} days, until ${new Date(t).toDateString()}. Every session on this Mac keeps to essentials. /lightweek off ends it early.` }
  })

  on('prompt.compose', async ($, e, next) => {
    const r = await next(e)
    // Re-read the switch each time: another session may have turned it on or off.
    const t = await refresh($)
    if (t === 0) return r
    return { sections: [...r.sections, { id: 'lightweek:guidance', text: guidance(new Date(t).toDateString()), scope: 'session' as const }] }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const t = await read($, until)
    if (e.props.hasSurvey || t === 0) return next(e)
    const left = Math.ceil((t - (await $.clock.now())) / DAY)
    if (left <= 0) return next(e)
    const { Text } = $.ui.resolve(e)
    return <Text dimColor>Light week · {left} day{left === 1 ? '' : 's'} left · /lightweek off to end</Text>
  })
}
