// The shared clock file, ~/Developer/claude-mods/config/clock.json (Oct 17 "one clock", Idea Register row 153).
// Pure functions: the hooks module reads the file, these answer what the day says right now.

export type Window = { days: string[]; from: string; to: string }
export type ClockFile = { aiWindows: Window[]; quietFrom: string; quietTo: string }

const DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
const mins = (hhmm: string): number => {
  const [h, m] = hhmm.split(':').map(Number)
  return (h ?? 0) * 60 + (m ?? 0)
}
const label = (m: number): string => {
  const h = Math.floor(m / 60) % 24
  const mm = String(m % 60).padStart(2, '0')
  return `${h % 12 === 0 ? 12 : h % 12}:${mm}${h < 12 ? 'am' : 'pm'}`
}

export function parseClock(text: string): ClockFile | undefined {
  try {
    const c = JSON.parse(text) as Partial<ClockFile>
    if (!Array.isArray(c.aiWindows) || typeof c.quietFrom !== 'string' || typeof c.quietTo !== 'string') return undefined
    return { aiWindows: c.aiWindows, quietFrom: c.quietFrom, quietTo: c.quietTo }
  } catch {
    return undefined
  }
}

export function isQuiet(c: ClockFile, at: Date): boolean {
  const now = at.getHours() * 60 + at.getMinutes()
  const from = mins(c.quietFrom)
  const to = mins(c.quietTo)
  return from > to ? now >= from || now < to : now >= from && now < to
}

// "AI window open till 4:00pm", "quiet hours", or "next AI window Wed 2:30pm".
export function describe(c: ClockFile, at: Date): { text: string; isOpen: boolean } {
  const now = at.getHours() * 60 + at.getMinutes()
  const today = DAYS[at.getDay()] ?? ''
  const open = c.aiWindows.find(w => w.days.includes(today) && now >= mins(w.from) && now < mins(w.to))
  if (open !== undefined) return { text: `AI window open till ${label(mins(open.to))}`, isOpen: true }
  if (isQuiet(c, at)) return { text: 'quiet hours', isOpen: false }
  for (let ahead = 0; ahead < 8; ahead++) {
    const day = DAYS[(at.getDay() + ahead) % 7] ?? ''
    const next = c.aiWindows
      .filter(w => w.days.includes(day) && (ahead > 0 || mins(w.from) > now))
      .sort((a, b) => mins(a.from) - mins(b.from))[0]
    if (next !== undefined) {
      const when = ahead === 0 ? 'today' : ahead === 1 ? 'tomorrow' : day[0]?.toUpperCase() + day.slice(1)
      return { text: `next AI window ${when} ${label(mins(next.from))}`, isOpen: false }
    }
  }
  return { text: 'no AI window set', isOpen: false }
}
