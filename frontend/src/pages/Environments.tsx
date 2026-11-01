import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, del, formatDate, post } from '../api/client'
import { btn, btnDanger, btnPrimary, inputClass } from '../components/formStyles'
import type { EnvironmentSummary } from '../types'

export default function Environments() {
  const nav = useNavigate()
  const [envs, setEnvs] = useState<EnvironmentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    api<EnvironmentSummary[]>('/environments').then(setEnvs).catch((e: Error) => setError(e.message))
  }, [tick])

  async function run(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function create(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    run(async () => {
      const env = await post<EnvironmentSummary>('/environments', { name })
      nav(`/environments/${env.id}`)
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Environments</h1>
        <button className={btn} disabled={busy}
          onClick={() => run(async () => {
            const env = await post<EnvironmentSummary>('/demo/campus')
            nav(`/environments/${env.id}`)
          })}>
          Load NEXUS Campus demo
        </button>
      </div>

      <form onSubmit={create} className="flex gap-2 max-w-xl">
        <input className={inputClass} placeholder="New environment name" value={name}
          onChange={(e) => setName(e.target.value)} maxLength={120} />
        <button className={btnPrimary} disabled={busy || !name.trim()}>Create</button>
      </form>

      {error && <div className="rounded-xl bg-danger/10 border border-danger/40 p-3 text-sm text-danger">{error}</div>}
      {!envs && !error && <p className="text-slate-400">Loading…</p>}

      {envs && envs.length === 0 && (
        <div className="rounded-xl bg-card border border-dashed border-white/20 p-8 text-center">
          <p className="font-medium">No environments yet</p>
          <p className="text-sm text-slate-400 mt-1">Create one above, or load the synthetic NEXUS Campus demo.</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {envs?.map((env) => (
          <div key={env.id} className="rounded-xl bg-card border border-white/10 p-4 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-medium">{env.name}</h2>
              {env.is_demo && (
                <span className="shrink-0 rounded-full bg-plasma/20 px-2 py-0.5 text-xs text-plasma">Synthetic demo</span>
              )}
            </div>
            <p className="text-sm text-slate-400 line-clamp-2">{env.description || 'No description'}</p>
            <p className="text-xs text-slate-500">
              {env.node_count} nodes · {env.edge_count} connections · updated {formatDate(env.updated_at)}
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Link to={`/environments/${env.id}`} className={btnPrimary}>Open</Link>
              <button className={btn} disabled={busy}
                onClick={() => run(async () => { await post(`/environments/${env.id}/duplicate`); setTick((t) => t + 1) })}>
                Duplicate
              </button>
              {confirmId === env.id ? (
                <>
                  <button className={btnDanger} disabled={busy}
                    onClick={() => run(async () => { await del(`/environments/${env.id}`); setConfirmId(null); setTick((t) => t + 1) })}>
                    Confirm delete
                  </button>
                  <button className={btn} onClick={() => setConfirmId(null)}>Cancel</button>
                </>
              ) : (
                <button className={btnDanger} onClick={() => setConfirmId(env.id)}>Delete</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}