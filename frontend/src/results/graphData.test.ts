import { describe, expect, it } from 'vitest'
import type { NodeResult, SnapEdge, SnapNode, Snapshot, Trace } from '../types'
import { buildGraph, EDGE_COLORS } from './graphData'

const sn = (id: number, name: string): SnapNode => ({
  id, name, category: 'generic', state: 'operational', capacity: 0, demand: 0, importance: 0.5,
  meta: {}, pos_x: id * 100, pos_y: 0,
})
const se = (id: number, s: number, d: number, t: SnapEdge['relationship_type'] = 'required'): SnapEdge => ({
  id, source_id: s, destination_id: d, relationship_type: t, strength: 1, capacity: null,
})
const nr = (id: number, trend: NodeResult['trend']): NodeResult => ({
  node_id: id, name: `N${id}`, category: 'generic', importance: 0.5, baseline_level: 1,
  level: trend === 'worse' ? 0 : 1, delta: trend === 'worse' ? -1 : 0, baseline_state: 'operational',
  state: trend === 'worse' ? 'failed' : 'operational', impact: trend === 'worse' ? 'indirect' : 'none',
  trend, absorbed: false, event_ids: [], availability: 1, output: 0, capacity: 0,
})

// 1 -> 2 -> 3, and 4 hangs off 1 with a backup edge; 1 and 2 are affected
const snapshot: Snapshot = {
  environment: { id: 1, name: 'E', model_version: '1.0.0' },
  scenario: { id: 1, name: 'S', version: 1, description: '', assumptions: [] },
  nodes: [sn(1, 'N1'), sn(2, 'N2'), sn(3, 'N3'), sn(4, 'N4')],
  edges: [se(10, 1, 2), se(11, 2, 3), se(12, 1, 4, 'backup'), se(13, 3, 99)],
  events: [],
}
const results = [nr(1, 'worse'), nr(2, 'worse'), nr(3, 'same'), nr(4, 'same')]
const trace: Trace = {
  node_id: 2, node_name: 'N2', impact: 'indirect', baseline_level: 1, level: 0, event_ids: [],
  path: [1, 2], path_names: ['N1', 'N2'], edge_ids: [10], explanation: '',
}
const opts = { selected: null, trace: undefined, focusAffected: false }

describe('buildGraph', () => {
  it('builds one node per result and skips edges that point at unknown nodes', () => {
    const g = buildGraph(snapshot, results, opts)
    expect(g.nodes.map((n) => n.id)).toEqual(['1', '2', '3', '4'])
    expect(g.edges.map((e) => e.id)).toEqual(['10', '11', '12'])
    expect(g.nodes[1].position).toEqual({ x: 200, y: 0 })
  })
  it('colours loss-carrying edges and leaves the rest neutral', () => {
    const g = buildGraph(snapshot, results, opts)
    const color = (id: string) => g.edges.find((e) => e.id === id)?.style?.stroke
    expect(color('10')).toBe(EDGE_COLORS.spread)   // 1 and 2 are both worse
    expect(color('11')).toBe(EDGE_COLORS.base)     // 3 is unaffected
    expect(g.edges.find((e) => e.id === '12')?.style?.strokeDasharray).toBe('2 4') // backup edge is dotted
  })
  it('highlights the trace path and marks the selected node', () => {
    const g = buildGraph(snapshot, results, { selected: 2, trace, focusAffected: false })
    expect(g.edges.find((e) => e.id === '10')?.style?.stroke).toBe(EDGE_COLORS.path)
    expect(g.nodes.find((n) => n.id === '2')?.data.mark).toBe('selected')
    expect(g.nodes.find((n) => n.id === '1')?.data.mark).toBe('path')
    expect(g.nodes.find((n) => n.id === '3')?.data.mark).toBeUndefined()
  })
  it('dims unaffected nodes only when asked to', () => {
    const dimmed = (focus: boolean) =>
      buildGraph(snapshot, results, { ...opts, focusAffected: focus }).nodes.filter((n) => n.data.dim).map((n) => n.id)
    expect(dimmed(false)).toEqual([])
    expect(dimmed(true)).toEqual(['3', '4'])
  })
  it('never dims the selected node or nodes on its path', () => {
    const g = buildGraph(snapshot, results, { selected: 3, trace, focusAffected: true })
    expect(g.nodes.find((n) => n.id === '3')?.data.dim).toBe(false)
  })
})