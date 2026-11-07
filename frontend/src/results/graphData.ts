import type { Edge, MarkerType, Node } from '@xyflow/react'
import type { NodeResult, SnapNode, Snapshot, Trace } from '../types'
import { layoutPositions } from './format'

export type ResultData = {
  result: NodeResult
  snap: SnapNode
  dim: boolean
  mark?: 'selected' | 'path'
}
export type ResultFlowNode = Node<ResultData, 'result'>

export interface GraphOptions {
  selected: number | null
  trace: Trace | undefined
  focusAffected: boolean
}

export const EDGE_COLORS = { base: '#64748B', spread: '#F87171', path: '#22D3EE' } as const

export function buildGraph(snapshot: Snapshot, results: NodeResult[], opts: GraphOptions) {
  const byId = new Map(results.map((r) => [r.node_id, r]))
  const pos = layoutPositions(snapshot.nodes)
  const pathNodes = new Set(opts.trace?.path ?? [])
  const pathEdges = new Set(opts.trace?.edge_ids ?? [])

  const nodes: ResultFlowNode[] = []
  for (const n of snapshot.nodes) {
    const result = byId.get(n.id)
    if (!result) continue
    const onPath = pathNodes.has(n.id)
    const mark = n.id === opts.selected ? 'selected' : onPath ? 'path' : undefined
    nodes.push({
      id: String(n.id),
      type: 'result',
      position: pos.get(n.id) ?? { x: 0, y: 0 },
      data: { result, snap: n, mark, dim: opts.focusAffected && result.trend === 'same' && !onPath && n.id !== opts.selected },
    })
  }

  const edges: Edge[] = []
  for (const e of snapshot.edges) {
    const s = byId.get(e.source_id)
    const d = byId.get(e.destination_id)
    if (!s || !d) continue
    const onPath = pathEdges.has(e.id)
    const spread = s.trend === 'worse' && d.trend === 'worse'
    const color = onPath ? EDGE_COLORS.path : spread ? EDGE_COLORS.spread : EDGE_COLORS.base
    edges.push({
      id: String(e.id),
      source: String(e.source_id),
      target: String(e.destination_id),
      markerEnd: { type: 'arrowclosed' as MarkerType, color },
      style: {
        stroke: color,
        strokeWidth: onPath ? 3 : spread ? 1.8 : 1.2,
        opacity: onPath ? 1 : spread ? 0.85 : opts.focusAffected ? 0.15 : 0.45,
        strokeDasharray: e.relationship_type === 'partial' ? '6 4' : e.relationship_type === 'backup' ? '2 4' : undefined,
      },
    })
  }
  return { nodes, edges }
}