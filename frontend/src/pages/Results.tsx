import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, del, formatDate } from '../api/client'
import { btn, btnDanger, inputClass } from '../components/formStyles'
import { score } from '../results/format'
import type { SimulationRow } from '../types'

export default function Results() {
  const [rows, setRows] = useState<SimulationRow[] | null>(null)
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    api<SimulationRow[]>('/simulations?limit=200')
      .then((r) => { if (!cancelled) setRows(r) })
      .catch((e: Error) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [tick])

  async function remove(id: number) {
    try {
      await del(`/simulations/${id}`)
      setConfirmId(null)
      setTick((t) => t + 1)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const term = q.trim().toLowerCase()
  const shown = (rows ?? []).filter((r) =>
    !term || r.scenario_name.toLowerCase().includes(term) || r.environment_name.toLowerCase().includes(term))

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Simulation Results</h1>
      <div className="w-64">
        <input className={inputClass} placeholder="Search by scenario or environment" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {error && <div className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
      {!rows && !error && <p className="text-slate-400">Loading…</p>}

      {rows && rows.length === 0 && (
        <div className="rounded-xl border border-dashed border-white/20 bg-card p-8 text-center">
          <p className="font-medium">No simulations yet</p>
          <p className="mt-1 text-sm text-slate-400">
            Open a final scenario in <Link to="/scenarios" className="text-accent underline">Scenarios</Link> and press Run simulation.
          </p>
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full min-w-190 text-left text-sm">
            <thead className="bg-surface text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-3 py-2">#</th><th className="px-3 py-2">Scenario</th><th className="px-3 py-2">Environment</th>
                <th className="px-3 py-2">Run</th><th className="px-3 py-2">Status</th><th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right">Affected</th><th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 && <tr><td colSpan={8} className="px-3 py-6 text-center text-slate-400">No simulations match.</td></tr>}
              {shown.map((r) => (
                <tr key={r.id} className="border-t border-white/5">
                  <td className="px-3 py-1.5 text-slate-500">{r.id}</td>
                  <td className="px-3 py-1.5 font-medium">{r.scenario_name || `#${r.scenario_id}`} <span className="text-xs text-slate-500">v{r.scenario_version}</span></td>
                  <td className="px-3 py-1.5 text-slate-400">{r.environment_name}</td>
                  <td className="px-3 py-1.5 text-xs text-slate-400">{formatDate(r.started_at)}</td>
                  <td className="px-3 py-1.5"><span className={r.status === 'completed' ? 'text-ok' : 'text-danger'}>{r.status}</span></td>
                  <td className="px-3 py-1.5 text-right">{r.metrics ? score(r.metrics.impact_score) : '—'}</td>
                  <td className="px-3 py-1.5 text-right">{r.metrics ? `${r.metrics.affected_nodes} / ${r.node_count}` : '—'}</td>
                  <td className="whitespace-nowrap px-3 py-1.5 text-right">
                    {r.status === 'completed' && <Link to={`/results/${r.id}`} className={btn}>Open</Link>}{' '}
                    {confirmId === r.id ? (
                      <>
                        <button className={btnDanger} onClick={() => remove(r.id)}>Confirm</button>{' '}
                        <button className={btn} onClick={() => setConfirmId(null)}>Cancel</button>
                      </>
                    ) : (
                      <button className={btnDanger} onClick={() => setConfirmId(r.id)}>Delete</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}