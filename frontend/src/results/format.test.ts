import { describe, expect, it } from 'vitest'
import type { NodeResult, SnapNode } from '../types'
import { amount, deltaPts, filterNodes, hours, layoutPositions, pct } from './format'

const row = (over: Partial<NodeResult>): NodeResult => ({
  node_id: 1, name: 'A', category: 'building', importance: 0.5, baseline_level: 1, level: 1, delta: 0,
  baseline_state: 'operational', state: 'operational', impact: 'none', trend: 'same', absorbed: false,
  event_ids: [], availability: 1, output: 0, capacity: 0, ...over,
})

describe('pct', () => {
  it('rounds normally', () => {
    expect(pct(0.405063)).toBe('41%')
    expect(pct(0.5)).toBe('50%')
  })
  it('never shows 0% or 100% for values that are not exactly that', () => {
    expect(pct(0)).toBe('0%')
    expect(pct(1)).toBe('100%')
    expect(pct(0.001)).toBe('<1%')
    expect(pct(0.997)).toBe('>99%')
  })
})

describe('deltaPts / hours / amount', () => {
  it('formats changes', () => {
    expect(deltaPts(-0.7281)).toBe('-73 pts')
    expect(deltaPts(0.3)).toBe('+30 pts')
    expect(deltaPts(0)).toBe('0 pts')
    expect(deltaPts(-0.001)).toBe('<1 pt lower')
  })
  it('formats numbers', () => {
    expect(hours(5)).toBe('5 h')
    expect(hours(2.5)).toBe('2.5 h')
    expect(amount(127.468354)).toBe('127.5')
    expect(amount(470)).toBe('470')
  })
})

describe('filterNodes', () => {
  const rows = [
    row({ node_id: 1, name: 'Grid', category: 'electricity', impact: 'direct', trend: 'worse', delta: -1, importance: 1 }),
    row({ node_id: 2, name: 'Hall', impact: 'indirect', trend: 'worse', delta: -0.7, importance: 0.6 }),
    row({ node_id: 3, name: 'Lab', impact: 'indirect', trend: 'worse', delta: -0.7, importance: 0.9 }),
    row({ node_id: 4, name: 'Road', category: 'road' }),
  ]
  const all = { query: '', impact: 'all' as const, category: 'all' as const }
  it('sorts worst first, ties by name', () => {
    expect(filterNodes(rows, all, 'delta').map((r) => r.name)).toEqual(['Grid', 'Hall', 'Lab', 'Road'])
  })
  it('sorts by importance and name', () => {
    expect(filterNodes(rows, all, 'importance').map((r) => r.name)).toEqual(['Grid', 'Lab', 'Hall', 'Road'])
    expect(filterNodes(rows, all, 'name').map((r) => r.name)).toEqual(['Grid', 'Hall', 'Lab', 'Road'])
  })
  it('filters by impact class, category and text', () => {
    expect(filterNodes(rows, { ...all, impact: 'direct' }, 'delta').map((r) => r.name)).toEqual(['Grid'])
    expect(filterNodes(rows, { ...all, impact: 'affected' }, 'delta')).toHaveLength(3)
    expect(filterNodes(rows, { ...all, impact: 'none' }, 'delta').map((r) => r.name)).toEqual(['Road'])
    expect(filterNodes(rows, { ...all, category: 'road' }, 'delta').map((r) => r.name)).toEqual(['Road'])
    expect(filterNodes(rows, { ...all, query: ' HA' }, 'delta').map((r) => r.name)).toEqual(['Hall'])
  })
  it('does not modify the input', () => {
    const copy = [...rows]
    filterNodes(rows, all, 'name')
    expect(rows).toEqual(copy)
  })
})

describe('layoutPositions', () => {
  const n = (id: number, x?: number, y?: number): SnapNode => ({
    id, name: `N${id}`, category: 'generic', state: 'operational', capacity: 0, demand: 0, importance: 0.5,
    meta: {}, pos_x: x, pos_y: y,
  })
  it('uses saved positions', () => {
    const p = layoutPositions([n(1, 10, 20), n(2, 30, 40)])
    expect(p.get(2)).toEqual({ x: 30, y: 40 })
  })
  it('falls back to a grid for old snapshots without positions', () => {
    const p = layoutPositions([n(3), n(1), n(2), n(4)])
    expect(p.get(1)).toEqual({ x: 0, y: 0 })
    expect(p.get(2)).toEqual({ x: 240, y: 0 })
    expect(p.get(3)).toEqual({ x: 0, y: 110 })
  })
  it('falls back when every node sits on the same spot', () => {
    const p = layoutPositions([n(1, 0, 0), n(2, 0, 0)])
    expect(p.get(2)).toEqual({ x: 240, y: 0 })
  })
  it('keeps a single node where it is', () => {
    expect(layoutPositions([n(1, 5, 6)]).get(1)).toEqual({ x: 5, y: 6 })
  })
})