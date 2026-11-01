import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, post, put } from '../api/client'
import Field from '../components/Field'
import ScenarioValidationPanel from '../components/ScenarioValidationPanel'
import { btn, btnDanger, btnPrimary, inputClass } from '../components/formStyles'
import { newDraft, toDrafts, toPayload, type Draft } from '../scenarios/draft'
import type {
  Category, EnvironmentDetail, EventType, EventTypeInfo, NexusNode,
  Scenario, ScenarioIssue, ScenarioValidationReport,
} from '../types'

const MAX_EVENTS = 50
const RING = { error: 'border-danger/60', warning: 'border-warn/60', info: 'border-accent/40' } as const
const RANK = { error: 3, warning: 2, info: 1 } as const

export default function ScenarioEditor() {
  const { scenarioId } = useParams()
  return <Editor key={scenarioId} id={Number(scenarioId)} />
}

function Editor({ id }: { id: number }) {
  const nav = useNavigate()
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [types, setTypes] = useState<Record<string, EventTypeInfo>>({})
  const [nodes, setNodes] = useState<NexusNode[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [assumptions, setAssumptions] = useState('')
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [dirty, setDirty] = useState(false)
  const [report, setReport] = useState<ScenarioValidationReport | null>(null)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const applyScenario = useCallback((s: Scenario, map: Record<string, EventTypeInfo>) => {
    setScenario(s)
    setName(s.name)
    setDescription(s.description)
    setAssumptions(s.assumptions.join('\n'))
    setDrafts(toDrafts(s.events, map))
    setDirty(false)
    setReport(null)
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([api<Scenario>(`/scenarios/${id}`), api<EventTypeInfo[]>('/event-types')])
      .then(async ([s, list]) => {
        const env = await api<EnvironmentDetail>(`/environments/${s.environment_id}`)
        if (cancelled) return
        const map = Object.fromEntries(list.map((t) => [t.type, t]))
        setTypes(map)
        setNodes(env.nodes)
        applyScenario(s, map)
      })
      .catch((e: Error) => { if (!cancelled) setLoadError(e.message) })
    return () => { cancelled = true }
  }, [id, applyScenario])

  const locked = scenario?.status === 'final'
  const sortedNodes = useMemo(() => [...nodes].sort((a, b) => a.name.localeCompare(b.name)), [nodes])

  const flagged = useMemo(() => {
    const m = new Map<number, ScenarioIssue['level']>()
    for (const i of report?.issues ?? []) {
      for (const eid of i.event_ids) {
        const cur = m.get(eid)
        if (!cur || RANK[i.level] > RANK[cur]) m.set(eid, i.level)
      }
    }
    return m
  }, [report])

  // ---------- editing ----------
  function updateDraft(key: string, patch: Partial<Draft>) {
    setDrafts((ds) => ds.map((d) => (d.key === key ? { ...d, ...patch } : d)))
    setDirty(true)
  }

  function changeType(d: Draft, t: EventType) {
    const info = types[t]
    const cat = nodes.find((n) => String(n.id) === d.target)?.category
    const targetOk = !d.target || !info.targets || (cat !== undefined && info.targets.includes(cat as Category))
    updateDraft(d.key, {
      event_type: t,
      target: targetOk ? d.target : '',
      pct: info.param ? d.pct : '',
      duration: info.duration === 'forbidden' ? '' : d.duration,
    })
  }

  const eligible = (info: EventTypeInfo) =>
    sortedNodes.filter((n) => !info.targets || info.targets.includes(n.category))

  // ---------- server actions ----------
  async function guarded(fn: () => Promise<void>) {
    setBusy(true)
    setMsg(null)
    try {
      await fn()
    } catch (e) {
      setMsg({ kind: 'error', text: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    if (locked || !dirty) return
    if (!name.trim()) throw new Error('The scenario needs a name.')
    const saved = await put<Scenario>(`/scenarios/${id}`, {
      name,
      description,
      assumptions: assumptions.split('\n').map((l) => l.trim()).filter(Boolean),
      events: toPayload(drafts, types),
    })
    applyScenario(saved, types)
  }

  const saveDraft = () => guarded(async () => {
    await save()
    setMsg({ kind: 'ok', text: 'Draft saved.' })
  })

  const validate = () => guarded(async () => {
    await save()
    setReport(await post<ScenarioValidationReport>(`/scenarios/${id}/validate`))
  })

  const finalize = () => {
    if (!window.confirm('Finalizing locks this version so simulations stay reproducible. You can still create a new version later. Continue?')) return
    guarded(async () => {
      await save()
      const s = await post<Scenario>(`/scenarios/${id}/finalize`)
      applyScenario(s, types)
      setMsg({ kind: 'ok', text: 'Scenario finalized and locked.' })
    })
  }

  const newVersion = () => guarded(async () => {
    await save()
    const s = await post<Scenario>(`/scenarios/${id}/new-version`)
    nav(`/scenarios/${s.id}`)
  })

  function focusIssue(issue: ScenarioIssue) {
    const d = drafts.find((x) => x.id !== undefined && issue.event_ids.includes(x.id))
    if (d) document.getElementById(`event-${d.key}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  if (loadError)
    return (
      <div className="rounded-xl border border-danger/40 bg-danger/10 p-4 text-danger">
        {loadError} <Link to="/scenarios" className="underline">Back to scenarios</Link>
      </div>
    )
  if (!scenario) return <div className="text-slate-400">Loading…</div>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/scenarios" className="text-sm text-slate-400 hover:text-accent">← Scenarios</Link>
        <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs">v{scenario.version}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${locked ? 'bg-ok/15 text-ok' : 'bg-warn/15 text-warn'}`}>
          {locked ? 'Final (locked)' : 'Draft'}
        </span>
        <span className="text-xs text-slate-400">Environment: {scenario.environment_name}</span>
        {dirty && <span className="text-xs text-warn">Unsaved changes</span>}
      </div>

      {locked && (
        <div className="rounded-xl border border-ok/30 bg-ok/10 p-3 text-sm text-slate-200">
          This version is final and read-only. Use <b>New version</b> to change it; simulations keep pointing at this exact version.
        </div>
      )}
      {msg && (
        <div className={`rounded-xl border p-3 text-sm ${msg.kind === 'ok' ? 'border-ok/40 bg-ok/10 text-ok' : 'border-danger/40 bg-danger/10 text-danger'}`}>
          {msg.text}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!locked && <button className={btnPrimary} disabled={busy || !dirty} onClick={saveDraft}>Save draft</button>}
        <button className={btn} disabled={busy} onClick={validate}>Validate</button>
        {!locked && <button className={btn} disabled={busy} onClick={finalize}>Finalize</button>}
        <button className={btn} disabled={busy} onClick={newVersion}>New version</button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <fieldset disabled={locked} className="min-w-0 space-y-4 disabled:opacity-70">
          <section className="space-y-3 rounded-xl border border-white/10 bg-card p-4">
            <Field label="Name">
              <input className={inputClass} value={name} maxLength={120}
                onChange={(e) => { setName(e.target.value); setDirty(true) }} />
            </Field>
            <Field label="Description">
              <textarea rows={2} className={inputClass} value={description} maxLength={2000}
                onChange={(e) => { setDescription(e.target.value); setDirty(true) }} />
            </Field>
            <Field label="Assumptions (one per line)">
              <textarea rows={3} className={inputClass} value={assumptions}
                onChange={(e) => { setAssumptions(e.target.value); setDirty(true) }} />
            </Field>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Events ({drafts.length})</h2>
              <button type="button" className={btnPrimary} disabled={drafts.length >= MAX_EVENTS}
                onClick={() => { setDrafts((ds) => [...ds, newDraft()]); setDirty(true) }}>
                + Add event
              </button>
            </div>

            {drafts.length === 0 && (
              <div className="rounded-xl border border-dashed border-white/20 bg-card p-6 text-center text-sm text-slate-400">
                No events yet. Add one to describe what changes, where, and when.
                Events that start at the same time are simultaneous.
              </div>
            )}

            {drafts.map((d, i) => {
              const info = types[d.event_type]
              const level = d.id !== undefined ? flagged.get(d.id) : undefined
              return (
                <div key={d.key} id={`event-${d.key}`}
                  className={`space-y-2 rounded-xl border bg-card p-3 ${level ? RING[level] : 'border-white/10'}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">Event {i + 1}</span>
                    <button type="button" className="text-xs text-danger hover:underline"
                      onClick={() => { setDrafts((ds) => ds.filter((x) => x.key !== d.key)); setDirty(true) }}>
                      Remove
                    </button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Field label="Event type">
                      <select className={inputClass} value={d.event_type}
                        onChange={(e) => changeType(d, e.target.value as EventType)}>
                        {Object.values(types).map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
                      </select>
                    </Field>
                    <Field label="Target node">
                      <select className={inputClass} value={d.target}
                        onChange={(e) => updateDraft(d.key, { target: e.target.value })}>
                        <option value="">Choose a node…</option>
                        {eligible(info).map((n) => <option key={n.id} value={n.id}>{n.name} ({n.category})</option>)}
                      </select>
                    </Field>
                  </div>
                  <p className="text-xs text-slate-500">{info.description}</p>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {info.param && (
                      <Field label={info.param_label ?? info.param}>
                        <input type="number" min={0} max={100} step="any" className={inputClass} value={d.pct}
                          onChange={(e) => updateDraft(d.key, { pct: e.target.value })} />
                      </Field>
                    )}
                    <Field label="Start time (hours)">
                      <input type="number" min={0} step="any" className={inputClass} value={d.start}
                        onChange={(e) => updateDraft(d.key, { start: e.target.value })} />
                    </Field>
                    {info.duration !== 'forbidden' && (
                      <Field label={`Duration (hours${info.duration === 'optional' ? ', optional' : ''})`}>
                        <input type="number" min={0} step="any" className={inputClass} value={d.duration}
                          placeholder={info.duration === 'optional' ? 'whole run' : ''}
                          onChange={(e) => updateDraft(d.key, { duration: e.target.value })} />
                      </Field>
                    )}
                  </div>
                </div>
              )
            })}
          </section>
        </fieldset>

        <aside className="space-y-3">
          {report && <ScenarioValidationPanel report={report} onSelect={focusIssue} />}
          <section className="rounded-xl border border-white/10 bg-card p-3 text-xs text-slate-400">
            <h2 className="mb-1 text-sm font-medium text-slate-200">How events work</h2>
            <ul className="list-disc space-y-1 pl-4">
              <li>Times are in hours. No duration means the effect lasts the whole run.</li>
              <li>Several events with the same start time are simultaneous disruptions.</li>
              <li>This page defines what changes. The effects on other nodes are calculated by the simulation engine (Phase 4).</li>
              <li>The baseline environment is never modified by a scenario.</li>
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}