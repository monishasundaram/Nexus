import type { SimMetrics, SimResult } from '../types'
import { amount, hours, score } from './format'

function Card({ title, value, sub, tone }: { title: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-card p-3">
      <div className="text-xs text-slate-400">{title}</div>
      <div className={`mt-1 text-2xl font-semibold ${tone ?? 'text-accent'}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

function recovery(m: SimMetrics): { value: string; sub: string } {
  if (m.impact_score === 0) return { value: 'No loss', sub: 'Nothing lost service at the peak step.' }
  const hoursText = `Impact-hours: ${m.impact_hours} (score × hours, up to the last event change).`
  if (m.recovered_at !== null) return { value: `At ${hours(m.recovered_at)}`, sub: `Service returns to baseline. ${hoursText}` }
  return { value: 'Not restored', sub: `Still impacted at the last event change (t=${hours(m.final_time)}). ${hoursText}` }
}

export default function SummaryCards({ result }: { result: SimResult }) {
  const m = result.metrics
  const rec = recovery(m)
  const unserved = Object.entries(result.unserved)
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Card title="Modelled impact score" value={score(m.impact_score)}
        sub={`0 to 1, at the peak step (t=${hours(m.peak_time)}). A modelled index, not a probability.`} />
      <Card title="Affected nodes" value={`${m.affected_nodes} of ${m.total_nodes}`}
        sub={`${m.direct_nodes} direct · ${m.indirect_nodes} indirect`} tone="text-warn" />
      <Card title="Failed / degraded" value={`${m.failed_nodes} / ${m.degraded_nodes}`}
        sub="Among the nodes that lost service" tone="text-danger" />
      <div className="rounded-xl border border-white/10 bg-card p-3">
        <div className="text-xs text-slate-400">Unserved demand (baseline → scenario)</div>
        {unserved.length === 0 ? (
          <div className="mt-1 text-sm text-slate-500">No resource node has declared demand.</div>
        ) : (
          <ul className="mt-1 space-y-0.5 text-sm">
            {unserved.map(([k, v]) => (
              <li key={k} className="flex justify-between gap-2">
                <span className="truncate text-slate-300">{k}</span>
                <span className={v.scenario > v.baseline ? 'text-danger' : 'text-ok'}>
                  {amount(v.baseline)} → {amount(v.scenario)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Card title="Recovery" value={rec.value} sub={rec.sub} tone="text-ok" />
    </div>
  )
}