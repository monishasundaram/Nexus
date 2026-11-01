import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { InfraFlowNode } from './convert'
import { CATEGORY_COLORS, MARK_COLORS, STATE_COLORS } from './style'

export default function InfraNode({ data, selected }: NodeProps<InfraFlowNode>) {
  const n = data.node
  const ring = data.mark ? MARK_COLORS[data.mark] : selected ? '#22D3EE' : 'rgba(255,255,255,0.14)'
  return (
    <div
      className="relative w-44 rounded-lg border-2 bg-card py-2 pl-4 pr-3 text-xs shadow-lg transition-opacity"
      style={{ borderColor: ring, opacity: data.dim ? 0.2 : 1 }}
    >
      <span className="absolute left-0 top-0 h-full w-1.5 rounded-l-md"
        style={{ background: CATEGORY_COLORS[n.category] }} />
      <Handle type="target" position={Position.Left} style={{ background: '#22D3EE' }} />
      <div className="truncate font-medium text-slate-100">{n.name}</div>
      <div className="mt-1 flex items-center gap-1.5 text-slate-400">
        <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLORS[n.state] }} />
        <span className="capitalize">{n.category}</span>
        <span>·</span>
        <span>{n.state}</span>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#8B5CF6' }} />
    </div>
  )
}