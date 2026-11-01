import { MarkerType, type Edge, type Node } from '@xyflow/react'
import type { NexusEdge, NexusNode } from '../types'

export type InfraData = {
  node: NexusNode
  dim?: boolean
  mark?: 'selected' | 'upstream' | 'downstream' | 'issue'
}
export type InfraFlowNode = Node<InfraData, 'infra'>
export type NexusFlowEdge = Edge<{ edge: NexusEdge }>

export function toFlowNode(n: NexusNode, extra: Omit<InfraData, 'node'> = {}): InfraFlowNode {
  return {
    id: String(n.id),
    type: 'infra',
    position: { x: n.pos_x, y: n.pos_y },
    data: { node: n, ...extra },
  }
}

export function toFlowEdge(e: NexusEdge, color?: string, dim = false): NexusFlowEdge {
  const stroke = color ?? (e.relationship_type === 'backup' ? '#8B5CF6' : '#64748B')
  return {
    id: String(e.id),
    source: String(e.source_id),
    target: String(e.destination_id),
    data: { edge: e },
    markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
    style: {
      stroke,
      strokeWidth: color ? 2.5 : 1.5,
      opacity: dim ? 0.12 : 1,
      strokeDasharray:
        e.relationship_type === 'partial' ? '6 4' : e.relationship_type === 'backup' ? '2 4' : undefined,
    },
  }
}