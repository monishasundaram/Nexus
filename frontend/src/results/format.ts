import type { Category, NodeResult, SnapNode } from '../types'

/** A percentage that never lies about being exactly 0% or 100%. */
export function pct(x: number): string {
  if (x <= 0) return '0%'
  if (x >= 1) return '100%'
  const r = Math.round(x * 100)
  if (r === 0) return '<1%'
  if (r === 100) return '>99%'
  return `${r}%`
}

/** Change in service level, in percentage points. */
export function deltaPts(delta: number): string {
  const r = Math.round(delta * 100)
  if (r === 0) return delta === 0 ? '0 pts' : delta < 0 ? '<1 pt lower' : '<1 pt higher'
  return `${r > 0 ? '+' : ''}${r} pts`
}

export const score = (x: number) => x.toFixed(3)

export function hours(h: number): string {
  return `${Number.isInteger(h) ? h : +h.toFixed(2)} h`
}

export function amount(x: number): string {
  return Number.isInteger(x) ? String(x) : String(+x.toFixed(1))
}

// ---------- node table ----------
export type ImpactFilter = 'all' | 'affected' | 'direct' | 'indirect' | 'none'
export type NodeSort = 'delta' | 'name' | 'importance'
export interface NodeFilter {
  query: string
  impact: ImpactFilter
  category: 'all' | Category
}

export function filterNodes(rows: NodeResult[], f: NodeFilter, sort: NodeSort): NodeResult[] {
  const q = f.query.trim().toLowerCase()
  const keep = rows.filter((r) => {
    if (q && !r.name.toLowerCase().includes(q)) return false
    if (f.category !== 'all' && r.category !== f.category) return false
    if (f.impact === 'affected') return r.trend === 'worse'
    if (f.impact === 'direct') return r.impact === 'direct'
    if (f.impact === 'indirect') return r.impact === 'indirect'
    if (f.impact === 'none') return r.impact === 'none'
    return true
  })
  const byName = (a: NodeResult, b: NodeResult) => a.name.localeCompare(b.name)
  return keep.sort((a, b) => {
    if (sort === 'name') return byName(a, b)
    if (sort === 'importance') return b.importance - a.importance || byName(a, b)
    return a.delta - b.delta || byName(a, b)
  })
}

// ---------- graph layout ----------
export interface Point { x: number; y: number }

/**
 * Uses the positions saved in the snapshot. Older snapshots, or snapshots where every node sits on the same
 * spot, get a simple grid so the graph is still readable.
 */
export function layoutPositions(nodes: SnapNode[]): Map<number, Point> {
  const has = (n: SnapNode) => Number.isFinite(n.pos_x) && Number.isFinite(n.pos_y)
  const usable =
    nodes.length > 0 &&
    nodes.every(has) &&
    (nodes.length === 1 || new Set(nodes.map((n) => `${n.pos_x},${n.pos_y}`)).size > 1)
  const out = new Map<number, Point>()
  if (usable) {
    for (const n of nodes) out.set(n.id, { x: n.pos_x as number, y: n.pos_y as number })
    return out
  }
  const cols = Math.max(1, Math.ceil(Math.sqrt(nodes.length)))
  ;[...nodes].sort((a, b) => a.id - b.id).forEach((n, i) => {
    out.set(n.id, { x: (i % cols) * 240, y: Math.floor(i / cols) * 110 })
  })
  return out
}