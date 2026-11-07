import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatDate, type DashboardData, type Health } from '../api/client'
import { score } from '../results/format'

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
  const latest = data.recent_simulations.find((s) => s.impact_score !== null)

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
            Create one in <Link to="/environments" className="text-accent underline">Environments</Link> or load the NEXUS Campus demo.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          <section className="rounded-xl bg-card border border-white/10 p-4">
            <h2 className="font-medium mb-2">Latest simulation result</h2>
            {latest ? (
              <Link to={`/results/${latest.id}`} className="block rounded-md p-2 hover:bg-white/5">
                <div className="font-medium">{latest.scenario_name} <span className="text-xs text-slate-500">v{latest.scenario_version}</span></div>
                <div className="mt-1 text-sm text-slate-300">
                  Impact score <b className="text-accent">{score(latest.impact_score as number)}</b> · {latest.affected_nodes} nodes affected
                </div>
                <div className="text-xs text-slate-500">{formatDate(latest.started_at)}</div>
              </Link>
            ) : <p className="text-sm text-slate-400">No simulations run yet. Finalize a scenario and press Run simulation.</p>}
          </section>

          <section className="rounded-xl bg-card border border-white/10 p-4">
            <h2 className="font-medium mb-2">Most frequently affected nodes</h2>
            {data.most_affected_nodes.length === 0
              ? <p className="text-sm text-slate-400">Appears after your first simulation.</p>
              : (
                <>
                  <ul>
                    {data.most_affected_nodes.map((n) => (
                      <li key={n.name} className="flex justify-between text-sm py-0.5">
                        <span>{n.name} <span className="text-xs capitalize text-slate-500">{n.category}</span></span>
                        <span className="text-slate-400">{n.count} of {data.runs_counted} runs</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-slate-500">Counted over your latest {data.runs_counted} completed simulation(s).</p>
                </>
              )}
          </section>

          <section className="rounded-xl bg-card border border-white/10 p-4">
            <h2 className="font-medium mb-2">Recent simulations</h2>
            {data.recent_simulations.length === 0
              ? <p className="text-sm text-slate-400">No simulations run yet.</p>
              : data.recent_simulations.map((s) => (
                <Link key={s.id} to={`/results/${s.id}`} className="flex justify-between text-sm py-1 hover:text-accent">
                  <span>#{s.id} · {s.scenario_name} v{s.scenario_version}</span>
                  <span className="text-slate-400">{s.impact_score !== null ? score(s.impact_score) : s.status}</span>
                </Link>))}
          </section>

          <section className="rounded-xl bg-card border border-white/10 p-4">
            <h2 className="font-medium mb-2">Infrastructure categories</h2>
            {data.category_distribution.map((c) => (
              <div key={c.category} className="flex justify-between text-sm py-1">
                <span className="capitalize">{c.category}</span><span>{c.count}</span>
              </div>
            ))}
          </section>
        </div>
      )}
    </div>
  )
}