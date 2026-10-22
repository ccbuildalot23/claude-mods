import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const isOn = atom({ plugin: 'cache-clock', key: 'isOn' } as const, true)
const clock = atom({ plugin: 'cache-clock', key: 'clock' } as const, { lastTurnAt: 0, contextTokens: 0, keepWarmUntil: 0, pings: 0 })

const KEEP_WARM_MS = 2 * 60 * 60 * 1000
const PING_LEAD_MS = 3 * 60 * 1000

async function paint($: EngineInterface, ttlMs: number): Promise<void> {
  if (!(await read($, isOn))) {
    $.ui.status(undefined)
    return
  }
  const c = await read($, clock)
  if (c.lastTurnAt === 0) return
  const left = c.lastTurnAt + ttlMs - (await $.clock.now())
  const warm = c.keepWarmUntil > (await $.clock.now()) ? ' · keeping warm' : ''
  $.ui.status(left > 0 ? `cache warm ${Math.ceil(left / 60000)}m left${warm}` : `cache cold (${Math.round(c.contextTokens / 1000)}k tokens re-read on next message)`)
}

async function ping($: EngineInterface): Promise<void> {
  const c = await read($, clock)
  const now = await $.clock.now()
  if (c.keepWarmUntil < now) return
  const r = await $.model.fork({ prompt: 'Keep-alive ping from the cache-clock mod. Reply with only: ok' })
  if (r.isAnswered) {
    await update($, clock, v => ({ ...v, lastTurnAt: now, pings: v.pings + 1 }))
  } else {
    $.ui.toast(`cache-clock: keep-warm ping did not land (${r.reason})`)
  }
}


export const register: Register = (on, options) => {
  const ttlMs = (typeof options.ttlMinutes === 'number' && options.ttlMinutes > 0 ? options.ttlMinutes : 60) * 60 * 1000

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'keepwarm', description: 'Keep this chat warm for up to 2 hours while you step away (small cost per ping)', argumentHint: '[off]', immediate: true })
    await $.command.register({ name: 'cacheclock', description: 'Cache countdown on or off', argumentHint: 'on|off', immediate: true })
    $.clock.every(30000, async () => {
      await paint($, ttlMs)
      const c = await read($, clock)
      const now = await $.clock.now()
      if (c.keepWarmUntil > now && c.lastTurnAt + ttlMs - now < PING_LEAD_MS) await ping($)
      if (c.keepWarmUntil > 0 && c.keepWarmUntil <= now) await update($, clock, v => ({ ...v, keepWarmUntil: 0 }))
    })
    return next(e)
  })

  on('command.run', { command: 'cacheclock' }, async ($, e) => {
    const turnOn = e.args.trim().toLowerCase() !== 'off'
    await update($, isOn, () => turnOn)
    if (!turnOn) await update($, clock, v => ({ ...v, keepWarmUntil: 0 }))
    await paint($, ttlMs)
    return { text: `Cache clock is ${turnOn ? 'on' : 'off'}.` }
  })

  on('command.run', { command: 'keepwarm' }, async ($, e) => {
    const now = await $.clock.now()
    if (e.args.trim().toLowerCase() === 'off') {
      await update($, clock, v => ({ ...v, keepWarmUntil: 0 }))
      await paint($, ttlMs)
      return { text: 'Keep-warm stopped.' }
    }
    const c = await read($, clock)
    if (c.lastTurnAt === 0 || c.lastTurnAt + ttlMs < now) return { text: 'The cache is already cold (or no reply yet), so there is nothing to keep warm.' }
    await update($, clock, v => ({ ...v, keepWarmUntil: now + KEEP_WARM_MS, pings: 0 }))
    await paint($, ttlMs)
    return { text: 'Keeping this chat warm for up to 2 hours. A tiny ping goes out a few minutes before it would go cold; it stops when you send your next message.' }
  })

  on('prompt.submit', async ($, e, next) => {
    const c = await read($, clock)
    const now = await $.clock.now()
    if ((await read($, isOn)) && c.lastTurnAt > 0 && c.lastTurnAt + ttlMs < now && c.contextTokens > 50000) {
      $.ui.toast(`Cache is cold: this message re-reads about ${Math.round(c.contextTokens / 1000)}k tokens at full price. Consider /handoff to a fresh chat.`, { timeoutMs: 8000 })
    }
    if (c.keepWarmUntil > 0) await update($, clock, v => ({ ...v, keepWarmUntil: 0 }))
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined) {
      const usage = await $.session.usage()
      const now = await $.clock.now()
      await update($, clock, v => ({ ...v, lastTurnAt: now, contextTokens: usage.context.tokens ?? v.contextTokens }))
      await paint($, ttlMs)
    }
    return done
  })
}
