import { expect, test } from 'claude-code/testing'
import { mask } from '../hooks/register'

test('masks emails, phones, money and listed names', () => {
  const out = mask('Email jane@ex.com or call 404-555-1234 about $12,500 with Dana', ['Dana'])
  expect(out.includes('jane@ex.com')).toBe(false)
  expect(out.includes('555-1234')).toBe(false)
  expect(out.includes('12,500')).toBe(false)
  expect(out.includes('Dana')).toBe(false)
  expect(out.includes('Email')).toBe(true)
})
