import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, del, formatDate, post } from '../api/client'
import { btn, btnDanger, btnPrimary, inputClass } from '../components/formStyles'
import type { EnvironmentSummary, EventTypeInfo, Scenario } from '../types'

export default function Scenarios() {
  const nav = useNavigate()
  const [scenarios, setScenarios] = useState<Scenario[] | null>(null)
  const [envs, setEnvs] = useState<EnvironmentSummary[]>([])
  const [types, setTypes] = useState<EventTypeInfo[]>([])
  const [q, setQ] = useState('')
  const [envFilter, setEnvFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [archived, setArchived] = useState(false)
  const [newEnv, setNewEnv] = useState('')
  const [newName, setNewName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    Promise.all([api<EnvironmentSummary[]>('/environments'), api<EventTypeInfo[]>('/event-types')])
      .then(([e, t]) => {
        setEnvs(e)
        setTypes(t)
        if (e.length) setNewEnv(String(e[0].id))
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    let cancelled = false
    const p = new URLSearchParams()
    if (q.trim()) p.set('q', q.trim())
    if (envFilter) p.set('environment_id', envFilter)
    if (typeFilter) p.set('event_type', typeFilter)
    if (archived) p.set('archived', 'true')
    api<Scenario[]>(`/scenarios?${p}`)
      .then((s) => { if (!cancelled) setScenarios(s) })
      .catch((e: Error) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [q, envFilter, typeFilter, archived, tick])

  async function run(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    setInfo(null)
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const refresh = () => setTick((t) => t + 1)
  const label = (t: string) => types.find((x) => x.type === t)?.label ?? t

  function create(e: FormEvent) {
    e.preventDefault()
    if (!newName.trim() || !newEnv) return
    run(async () => {
      const s = await post<Scenario>(`/environments/${newEnv}/scenarios`, { name: newName })
      nav(`/scenarios/${s.id}`)
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Scenario Library</h1>

      {envs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/20 bg-card p-6 text-sm text-slate-400">
          Scenarios belong to an environment. Create one or load the demo in{' '}
          <Link to="/environments" className="text-accent underline">Environments</Link> first.
        </div>
      ) : (
        <form onSubmit={create} className="flex flex-wrap items-center gap-2">
          <select className={`${inputClass} w-52`} value={newEnv} onChange={(e) => setNewEnv(e.target.value)} aria-label="Environment for the new scenario">
            {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <div className="w-64">
            <input className={inputClass} placeholder="New scenario name" value={newName} maxLength={120}
              onChange={(e) => setNewName(e.target.value)} />
          </div>
          <button className={btnPrimary} disabled={busy || !newName.trim()}>Create scenario</button>
          <button type="button" className={btn} disabled={busy}
            title="Adds the 4 sample scenarios to the selected environment (needs the NEXUS Campus nodes)"
            onClick={() => run(async () => {
              const made = await post<Scenario[]>(`/environments/${newEnv}/demo-scenarios`)
              setInfo(`Added ${made.length} sample scenarios.`)
              refresh()
            })}>
            Add sample scenarios
          </button>
        </form>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-52">
          <input className={inputClass} placeholder="Search by name" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className={`${inputClass} w-48`} value={envFilter} onChange={(e) => setEnvFilter(e.target.value)} aria-label="Environment filter">
          <option value="">All environments</option>
          {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <select className={`${inputClass} w-52`} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Event type filter">
          <option value="">All event types</option>
          {types.map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          Show archived only
        </label>
      </div>

      {error && <div className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
      {info && <div className="rounded-xl border border-ok/40 bg-ok/10 p-3 text-sm text-ok">{info}</div>}
      {!scenarios && !error && <p className="text-slate-400">Loading…</p>}

      {scenarios && scenarios.length === 0 && (
        <div className="rounded-xl border border-dashed border-white/20 bg-card p-8 text-center">
          <p className="font-medium">{archived ? 'No archived scenarios' : 'No scenarios found'}</p>
          <p className="mt-1 text-sm text-slate-400">Create one above, or add the sample scenarios for NEXUS Campus.</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {scenarios?.map((s) => (
          <div key={s.id} className="space-y-2 rounded-xl border border-white/10 bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h2 className="font-medium">{s.name}</h2>
              <div className="flex gap-1.5">
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs">v{s.version}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs ${s.status === 'final' ? 'bg-ok/15 text-ok' : 'bg-warn/15 text-warn'}`}>
                  {s.status === 'final' ? 'Final' : 'Draft'}
                </span>
              </div>
            </div>
            <p className="text-xs text-slate-500">{s.environment_name}</p>
            <p className="line-clamp-2 text-sm text-slate-400">{s.description || 'No description'}</p>
            <div className="flex flex-wrap gap-1">
              {[...new Set(s.events.map((e) => e.event_type))].map((t) => (
                <span key={t} className="rounded bg-plasma/15 px-1.5 py-0.5 text-xs text-plasma">{label(t)}</span>
              ))}
              {s.events.length === 0 && <span className="text-xs text-slate-500">No events yet</span>}
            </div>
            <p className="text-xs text-slate-500">
              {s.events.length} events · {s.simulation_count} simulations · updated {formatDate(s.updated_at)}
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Link to={`/scenarios/${s.id}`} className={btnPrimary}>Open</Link>
              <button className={btn} disabled={busy}
                onClick={() => run(async () => { const n = await post<Scenario>(`/scenarios/${s.id}/new-version`); nav(`/scenarios/${n.id}`) })}>
                New version
              </button>
              <button className={btn} disabled={busy}
                onClick={() => run(async () => { await post(`/scenarios/${s.id}/duplicate`); refresh() })}>
                Duplicate
              </button>
              <button className={btn} disabled={busy}
                onClick={() => run(async () => { await post(`/scenarios/${s.id}/${s.is_archived ? 'unarchive' : 'archive'}`); refresh() })}>
                {s.is_archived ? 'Unarchive' : 'Archive'}
              </button>
              {confirmId === s.id ? (
                <>
                  <button className={btnDanger} disabled={busy}
                    onClick={() => run(async () => {
                      await del(`/scenarios/${s.id}${s.simulation_count ? '?force=true' : ''}`)
                      setConfirmId(null)
                      refresh()
                    })}>
                    {s.simulation_count ? `Delete with ${s.simulation_count} simulations` : 'Confirm delete'}
                  </button>
                  <button className={btn} onClick={() => setConfirmId(null)}>Cancel</button>
                </>
              ) : (
                <button className={btnDanger} onClick={() => setConfirmId(s.id)}>Delete</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}