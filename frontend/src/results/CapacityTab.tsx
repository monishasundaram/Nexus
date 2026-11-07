import type { CapacityRow } from '../types'
import { amount, pct } from './format'

export default function CapacityTab({ rows }: { rows: CapacityRow[] }) {
  if (rows.length === 0)
    return (
      <p className="rounded-xl border border-dashed border-white/20 bg-card p-6 text-center text-sm text-slate-400">
        No resource node (electricity, water or communication) has capacity in this environment.
      </p>
    )
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-2">Resource node</th><th className="px-3 py-2">Unit</th>
              <th className="px-3 py-2 text-right">Capacity</th><th className="px-3 py-2 text-right">Output</th>
              <th className="px-3 py-2 text-right">Requested</th><th className="px-3 py-2 text-right">Unserved</th>
              <th className="px-3 py-2 text-right">Service level</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const worse = r.scenario_unserved > r.baseline_unserved
              return (
                <tr key={r.node_id} className="border-t border-white/5">
                  <td className="px-3 py-1.5"><div className="font-medium">{r.name}</div><div className="text-xs capitalize text-slate-500">{r.category}</div></td>
                  <td className="px-3 py-1.5 text-slate-400">{r.unit || '—'}</td>
                  <td className="px-3 py-1.5 text-right">{amount(r.nominal_capacity)}</td>
                  <td className="px-3 py-1.5 text-right">{amount(r.baseline_output)} → {amount(r.scenario_output)}</td>
                  <td className="px-3 py-1.5 text-right">{r.demand > 0 ? amount(r.demand) : '—'}</td>
                  <td className={`px-3 py-1.5 text-right ${worse ? 'text-danger' : ''}`}>
                    {r.demand > 0 ? `${amount(r.baseline_unserved)} → ${amount(r.scenario_unserved)}` : '—'}
                  </td>
                  <td className="px-3 py-1.5 text-right">{r.demand > 0 ? `${pct(r.baseline_level)} → ${pct(r.scenario_level)}` : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        Requested = the demand that dependent nodes declare on this resource (nominal; it is not reduced when a dependent is down).
        Output = capacity × availability. Unserved = max(0, requested − output).
      </p>
    </div>
  )
}