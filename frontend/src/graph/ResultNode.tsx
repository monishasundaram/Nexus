import { Handle, Position, type NodeProps } from '@xyflow/react'
import { pct } from '../results/format'
import type { ResultFlowNode } from '../results/graphData'
import { CATEGORY_COLORS, STATE_COLORS } from './style'

export default function ResultNode({ data }: NodeProps<ResultFlowNode>) {
  const r = data.result
  const ring = data.mark === 'selected' ? '#22D3EE' : data.mark === 'path' ? '#8B5CF6'
    : r.impact === 'direct' ? '#FFFFFF' : 'rgba(255,255,255,0.14)'
  return (
    <div
      className="relative w-44 rounded-lg border-2 bg-card py-2 pl-4 pr-3 text-xs shadow-lg transition-opacity"
      style={{ borderColor: ring, opacity: data.dim ? 0.2 : 1 }}
    >
      <span className="absolute left-0 top-0 h-full w-1.5 rounded-l-md" style={{ background: CATEGORY_COLORS[r.category] }} />
      <Handle type="target" position={Position.Left} isConnectable={false} style={{ background: '#22D3EE' }} />
      <div className="truncate font-medium text-slate-100">{r.name}</div>
      <div className="mt-1 flex items-center gap-1.5 text-slate-400">
        <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLORS[r.state] }} />
        <span className="capitalize">{r.state}</span>
        <span>·</span>
        <span className="text-slate-200">{pct(r.level)}</span>
      </div>
      {r.trend !== 'same' && (
        <div className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-500">
          {r.impact === 'none' ? (r.trend === 'better' ? 'improved' : '') : r.impact}
          {r.baseline_level !== r.level && ` · was ${pct(r.baseline_level)}`}
        </div>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} style={{ background: '#8B5CF6' }} />
    </div>
  )
}