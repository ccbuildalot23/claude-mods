import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { isQuiet, parseClock } from './clock'

// Needs-you ping: a desktop notification when Claude finishes a long turn or is waiting on Chris (a permission
// prompt, an idle prompt), so a job never sits stalled while he's in another window (LESSONS, Oct 20: runs held
// on approvals blocked the scheduler for a day). Silent in quiet hours from the shared clock file; what came in
// is summed up once quiet hours end. Replaces the old done-chime hook. Uses no AI.

const isOn = atom({ plugin: 'needs-you', key: 'isOn' } as const, true)

const LONG_TURN_MS = 60 * 1000

async function quietNow($: EngineInterface): Promise<boolean> {
  try {
    const home = (await $.env.get('HOME')) ?? '.'
    const c = parseClock(await $.fs.read(`${home}/Developer/claude-mods/config/clock.json`))
    return c !== undefined && isQuiet(c, new Date(await $.clock.now()))
  } catch {
    return false
  }
}

async function ping($: EngineInterface, text: string): Promise<void> {
  if (!(await read($, isOn))) return
  if (await quietNow($)) {
    const queued = ((await $.store.get('queued')) as string[] | undefined) ?? []
    await $.store.set('queued', [...queued, text].slice(-20))
    return
  }
  const sent = await $.ui.notify(text, { title: 'Claude needs you' }).catch(() => ({ isSent: false }))
  if (!sent.isSent) $.ui.toast(text, { timeoutMs: 10000 })
}

async function drain($: EngineInterface): Promise<void> {
  const queued = ((await $.store.get('queued')) as string[] | undefined) ?? []
  if (queued.length === 0 || (await quietNow($))) return
  await $.store.set('queued', [])
  const text = `While it was quiet: ${queued.length === 1 ? queued[0] : `${queued.length} things waited. Latest: ${queued.at(-1)}`}`
  const sent = await $.ui.notify(text, { title: 'Claude needs you' }).catch(() => ({ isSent: false }))
  if (!sent.isSent) $.ui.toast(text, { timeoutMs: 12000 })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'needsyou', description: 'Desktop ping when Claude finishes or waits on you: /needsyou on|off', argumentHint: 'on|off', immediate: true })
    if ((await $.store.get('isOn')) === false) await update($, isOn, () => false)
    $.clock.every(60000, () => drain($))
    return next(e)
  })

  on('command.run', { command: 'needsyou' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, isOn, () => turnOn)
    await $.store.set('isOn', turnOn)
    return { text: `Needs-you pings are ${turnOn ? 'on' : 'off'}.` }
  })

  on('classic.Notification', async ($, e, next) => {
    const done = await next(e)
    if (e.notification_type !== 'plugin_notification') await ping($, e.message)
    return done
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined && !e.isAborted && e.durationMs >= LONG_TURN_MS) {
      const first = e.answer.trim().split('\n')[0] ?? ''
      await ping($, `Done after ${Math.round(e.durationMs / 60000)} min: ${first.slice(0, 120)}`)
    }
    return done
  })
}
