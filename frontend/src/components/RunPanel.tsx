import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, formatDate, post } from '../api/client'
import { btnPrimary } from './formStyles'
import { score } from '../results/format'
import type { SimulationDetail, SimulationRow } from '../types'

export default function RunPanel({ scenarioId, status }: { scenarioId: number; status: 'draft' | 'final' }) {
  const nav = useNavigate()
  const [runs, setRuns] = useState<SimulationRow[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<SimulationRow[]>(`/simulations?scenario_id=${scenarioId}&limit=5`)
      .then((r) => { if (!cancelled) setRuns(r) })
      .catch(() => { if (!cancelled) setRuns([]) })
    return () => { cancelled = true }
  }, [scenarioId])

  async function run() {
    setBusy(true)
    setError(null)
    try {
      const sim = await post<SimulationDetail>(`/scenarios/${scenarioId}/simulate`)
      nav(`/results/${sim.id}`)
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  return (
    <section className="space-y-2 rounded-xl border border-white/10 bg-card p-3">
      <h2 className="font-medium">Simulation</h2>
      {status === 'final' ? (
        <button className={btnPrimary} disabled={busy} onClick={run}>{busy ? 'Running…' : 'Run simulation'}</button>
      ) : (
        <p className="text-xs text-slate-400">Finalize this version to run it, so every simulation stays tied to an exact scenario version.</p>
      )}
      {error && <p className="text-xs text-danger">{error}</p>}
      {runs && runs.length > 0 && (
        <div>
          <h3 className="mb-1 text-xs uppercase tracking-wide text-slate-400">Latest runs of this version and others</h3>
          <ul className="space-y-0.5 text-xs">
            {runs.map((r) => (
              <li key={r.id}>
                <Link to={`/results/${r.id}`} className="flex justify-between gap-2 rounded px-2 py-1 hover:bg-white/5">
                  <span>#{r.id} · v{r.scenario_version} · {formatDate(r.started_at)}</span>
                  <span className="text-slate-400">{r.metrics ? score(r.metrics.impact_score) : r.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}