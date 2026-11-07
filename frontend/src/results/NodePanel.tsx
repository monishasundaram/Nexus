import { STATE_COLORS } from '../graph/style'
import type { CapacityRow, NodeResult, SimEvent, SnapEdge, Trace } from '../types'
import { amount, deltaPts, pct } from './format'

export interface SupplierInput {
  edge: SnapEdge
  name: string
  baseline: number
  level: number
}

interface Props {
  node: NodeResult
  trace: Trace | undefined
  events: SimEvent[]
  suppliers: SupplierInput[]
  capacity: CapacityRow | undefined
  onSelect: (id: number) => void
}

function classify(n: NodeResult): { label: string; tone: string } {
  if (n.trend === 'better') return { label: 'Improved vs. baseline', tone: 'text-ok' }
  if (n.trend === 'worse') return n.impact === 'direct'
    ? { label: 'Directly affected', tone: 'text-danger' }
    : { label: 'Indirectly affected', tone: 'text-warn' }
  if (n.absorbed) return { label: 'Hit directly, but absorbed', tone: 'text-ok' }
  return { label: 'Not affected', tone: 'text-slate-300' }
}

export default function NodePanel({ node, trace, events, suppliers, capacity, onSelect }: Props) {
  const c = classify(node)
  const hits = events.filter((e) => node.event_ids.includes(e.id))
  return (
    <section className="space-y-3 rounded-xl border border-white/10 bg-card p-3 text-sm">
      <div>
        <h2 className="font-medium">{node.name}</h2>
        <p className="text-xs capitalize text-slate-400">{node.category} · importance {node.importance}</p>
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className={`font-medium ${c.tone}`}>{c.label}</span>
        <span className="flex items-center gap-1.5 text-xs capitalize text-slate-300">
          <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLORS[node.state] }} />
          {node.state}
        </span>
      </div>

      <div className="rounded-md bg-surface p-2 text-xs">
        Service level: <b>{pct(node.baseline_level)}</b> → <b>{pct(node.level)}</b>{' '}
        <span className="text-slate-400">({deltaPts(node.delta)})</span>
        {node.capacity > 0 && (
          <div className="mt-1 text-slate-400">
            Output {amount(node.output)} of capacity {amount(node.capacity)} (availability {pct(node.availability)})
          </div>
        )}
        {capacity && capacity.demand > 0 && (
          <div className="mt-1 text-slate-400">
            Dependents request {amount(capacity.demand)}{capacity.unit ? ` ${capacity.unit}` : ''}; unserved{' '}
            {amount(capacity.baseline_unserved)} → {amount(capacity.scenario_unserved)}
          </div>
        )}
      </div>

      {hits.length > 0 && (
        <div>
          <h3 className="mb-1 text-xs uppercase tracking-wide text-slate-400">Events on this node</h3>
          <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-300">
            {hits.map((e) => <li key={e.id}>{e.label}{e.duration !== null ? `, lasts ${e.duration} h` : ''}</li>)}
          </ul>
        </div>
      )}

      {trace ? (
        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-wide text-slate-400">Why was this affected?</h3>
          <p className="text-xs text-slate-300">{trace.explanation}</p>
          {trace.path.length > 1 && (
            <div className="flex flex-wrap items-center gap-1 text-xs">
              {trace.path.map((id, i) => (
                <span key={`${id}-${i}`} className="flex items-center gap-1">
                  {i > 0 && <span className="text-slate-500">→</span>}
                  <button className={`rounded px-1.5 py-0.5 ${id === node.node_id ? 'bg-accent/20 text-accent' : 'bg-white/5 hover:bg-white/10'}`}
                    onClick={() => onSelect(id)}>
                    {trace.path_names[i]}
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      ) : node.absorbed ? (
        <p className="text-xs text-slate-300">
          An event lowered this node&apos;s own capacity, but it still covers everything its dependents request, so service did not drop.
        </p>
      ) : node.trend === 'same' ? (
        <p className="text-xs text-slate-400">No supplier or event lowered this node&apos;s service level.</p>
      ) : null}

      <div>
        <h3 className="mb-1 text-xs uppercase tracking-wide text-slate-400">Inputs from suppliers</h3>
        {suppliers.length === 0 ? (
          <p className="text-xs text-slate-500">This node has no suppliers; only its own state and events matter.</p>
        ) : (
          <ul className="space-y-0.5">
            {suppliers.map((s) => (
              <li key={s.edge.id}>
                <button className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-white/5"
                  onClick={() => onSelect(s.edge.source_id)}>
                  <span className="truncate">{s.name}</span>
                  <span className="shrink-0 text-slate-500">
                    {s.edge.relationship_type} {s.edge.strength} · {pct(s.baseline)} → {pct(s.level)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[11px] text-slate-500">
          Formulas: docs/simulation-model.md. Required suppliers limit this node, partial suppliers multiply their losses, backups add to the supply.
        </p>
      </div>
    </section>
  )
}