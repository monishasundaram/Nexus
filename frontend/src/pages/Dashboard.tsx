import { useEffect, useState } from 'react'
import { api, type DashboardData, type Health } from '../api/client'

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-card border border-white/10 p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className="text-3xl font-semibold text-accent mt-1">{value}</div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api<DashboardData>('/dashboard'), api<Health>('/health')])
      .then(([d, h]) => { setData(d); setHealth(h) })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="rounded-xl bg-danger/10 border border-danger/40 p-4 text-danger">
    Could not reach the backend: {error}. Is uvicorn running?</div>
  if (!data) return <div className="text-slate-400">Loading…</div>

  const empty = data.environments === 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-semibold">Overview</h1>
        {health && <span className="text-xs rounded-full bg-ok/15 text-ok px-3 py-1">
          API {health.status} · DB {health.database} · model v{health.model_version}</span>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Stat label="Environments" value={data.environments} />
        <Stat label="Scenarios" value={data.scenarios} />
        <Stat label="Completed simulations" value={data.completed_simulations} />
      </div>

      {empty ? (
        <div className="rounded-xl bg-card border border-dashed border-white/20 p-8 text-center">
          <p className="font-medium">No environments yet</p>
          <p className="text-sm text-slate-400 mt-1">
            Create one in the Environment Builder (Phase 2) or load the NEXUS Campus demo.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          <section className="rounded-xl bg-card border border-white/10 p-4">
            <h2 className="font-medium mb-2">Infrastructure categories</h2>
            {data.category_distribution.map((c) => (
              <div key={c.category} className="flex justify-between text-sm py-1">
                <span className="capitalize">{c.category}</span><span>{c.count}</span>
              </div>
            ))}
          </section>
          <section className="rounded-xl bg-card border border-white/10 p-4">
            <h2 className="font-medium mb-2">Recent simulations</h2>
            {data.recent_simulations.length === 0
              ? <p className="text-sm text-slate-400">No simulations run yet.</p>
              : data.recent_simulations.map((s) => (
                <div key={s.id} className="text-sm py-1">#{s.id} · {s.status}</div>))}
          </section>
        </div>
      )}
    </div>
  )
}