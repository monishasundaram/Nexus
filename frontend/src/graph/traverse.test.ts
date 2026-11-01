import { describe, expect, it } from 'vitest'
import { reach } from './traverse'

const links = [
  { source: 'a', target: 'b' },
  { source: 'b', target: 'c' },
  { source: 'x', target: 'c' },
]

describe('reach', () => {
  it('finds downstream dependents', () => {
    expect([...reach('a', links, 'down')].sort()).toEqual(['b', 'c'])
  })
  it('finds upstream suppliers', () => {
    expect([...reach('c', links, 'up')].sort()).toEqual(['a', 'b', 'x'])
  })
  it('returns nothing for a leaf', () => {
    expect(reach('c', links, 'down').size).toBe(0)
  })
  it('handles cycles without looping forever', () => {
    const cyc = [{ source: 'a', target: 'b' }, { source: 'b', target: 'a' }]
    expect([...cyc.length ? reach('a', cyc, 'down') : []]).toEqual(['b'])
  })
})