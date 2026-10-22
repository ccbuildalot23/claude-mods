import { expect, test } from 'claude-code/testing'

import { describe, isQuiet } from '../hooks/clock'

const c = { aiWindows: [{ days: ['mon', 'wed', 'fri'], from: '14:30', to: '16:00' }, { days: ['sun'], from: '14:00', to: '16:00' }], quietFrom: '17:00', quietTo: '08:40' }

test('the day reads right across windows, quiet hours and the week', async () => {
  expect(describe(c, new Date('2026-10-21T15:10:00')).text).toBe('AI window open till 4:00pm')
  expect(describe(c, new Date('2026-10-21T18:00:00')).text).toBe('quiet hours')
  expect(isQuiet(c, new Date('2026-10-22T07:00:00'))).toBe(true)
  expect(describe(c, new Date('2026-10-22T10:00:00')).text).toBe('next AI window tomorrow 2:30pm')
  expect(describe(c, new Date('2026-10-24T10:00:00')).text).toBe('next AI window tomorrow 2:00pm')
  expect(describe(c, new Date('2026-10-21T09:00:00')).text).toBe('next AI window today 2:30pm')
})
