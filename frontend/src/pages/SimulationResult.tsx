import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, del, formatDate, post } from '../api/client'
import ResultGraph from '../components/ResultGraph'
import { btn, btnDanger, btnPrimary } from '../components/formStyles'
import CapacityTab from '../results/CapacityTab'
import NodePanel, { type SupplierInput } from '../results/NodePanel'
import NodeTable from '../results/NodeTable'
import NotesTab from '../results/NotesTab'
import SummaryCards from '../results/SummaryCards'
import TimelineTab from '../results/TimelineTab'
import { hours } from '../results/format'
import { STATE_COLORS } from '../graph/style'
import type { SimulationDetail, Snapshot } from '../types'

type Tab = 'nodes' | 'timeline' | 'capacity' | 'notes'
const TABS: [Tab, string][] = [['nodes', 'Nodes'], ['timeline', 'Timeline'], ['capacity', 'Capacity & demand'], ['notes', 'Assumptions & warnings']]

export default function SimulationResult() {
  const { simId } = useParams()
  return <Loader key={simId} id={Number(simId)} />
}

function Loader({ id }: { id: number }) {
  const [sim, setSim] = useState<SimulationDetail | null>(null)
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([api<SimulationDetail>(`/simulations/${id}`), api<Snapshot>(`/simulations/${id}/snapshot`)])
      .then(([s, sn]) => { if (!cancelled) { setSim(s); setSnap(sn) } })
      .catch((e: Error) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [id])

  if (error)
    return (
      <div className="rounded-xl border border-danger/40 bg-danger/10 p-4 text-danger">
        {error} <Link to="/results" className="underline">Back to results</Link>
      </div>
    )
  if (!sim || !snap) return <div className="text-slate-400">Loading…</div>
  return <View sim={sim} snap={snap} />
}

function View({ sim, snap }: { sim: SimulationDetail; snap: Snapshot }) {
  const nav = useNavigate()
  const result = sim.result
  const [selected, setSelected] = useState<number | null>(null)
  const [nonce, setNonce] = useState(0)
  const [tab, setTab] = useState<Tab>('nodes')
  const [focusAffected, setFocusAffected] = useState(true)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const traces = useMemo(() => new Map((result?.traces ?? []).map((t) => [t.node_id, t])), [result])
  const nodes = useMemo(() => new Map((result?.node_results ?? []).map((n) => [n.node_id, n])), [result])
  const capacity = useMemo(() => new Map((result?.capacity ?? []).map((c) => [c.node_id, c])), [result])

  const suppliers = useMemo<SupplierInput[]>(() => {
    if (selected === null) return []
    return snap.edges
      .filter((e) => e.destination_id === selected && nodes.has(e.source_id))
      .map((edge) => {
        const s = nodes.get(edge.source_id)!
        return { edge, name: s.name, baseline: s.baseline_level, level: s.level }
      })
  }, [selected, snap, nodes])

  function pickFromTable(id: number) {
    setSelected(id)
    setNonce((n) => n + 1)
  }

  async function guarded(fn: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  const runAgain = () => guarded(async () => {
    const next = await post<SimulationDetail>(`/scenarios/${sim.scenario_id}/simulate`)
    nav(`/results/${next.id}`)
  })
  const remove = () => guarded(async () => {
    await del(`/simulations/${sim.id}`)
    nav('/results')
  })

  const sel = selected !== null ? nodes.get(selected) : undefined
  const selEvents = result?.events ?? []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/results" className="text-sm text-slate-400 hover:text-accent">← Results</Link>
        <h1 className="text-xl font-semibold">{sim.scenario_name || `Scenario #${sim.scenario_id}`}</h1>
        <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs">v{sim.scenario_version}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${sim.status === 'completed' ? 'bg-ok/15 text-ok' : 'bg-danger/15 text-danger'}`}>{sim.status}</span>
        {snap.environment.is_demo && <span className="rounded-full bg-plasma/20 px-2 py-0.5 text-xs text-plasma">Synthetic demo data</span>}
        <span className="ml-auto text-xs text-slate-500">
          Simulation #{sim.id} · {sim.environment_name} · {formatDate(sim.started_at)} · model v{sim.model_version}
        </span>
      </div>

      <p className="rounded-xl border border-white/10 bg-card px-3 py-2 text-xs text-slate-400">
        These are outputs of a transparent educational model, calculated from the graph and events frozen in this simulation.
        They are not predictions of real-world behaviour. See the Assumptions tab.
      </p>

      {error && <div className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{error}</div>}

      <div className="flex flex-wrap gap-2">
        <button className={btnPrimary} disabled={busy} onClick={runAgain}>Run again</button>
        <Link to={`/scenarios/${sim.scenario_id}`} className={btn}>Open scenario</Link>
        {confirmDelete ? (
          <>
            <button className={btnDanger} disabled={busy} onClick={remove}>Confirm delete</button>
            <button className={btn} onClick={() => setConfirmDelete(false)}>Cancel</button>
          </>
        ) : (
          <button className={btnDanger} onClick={() => setConfirmDelete(true)}>Delete this simulation</button>
        )}
      </div>

      {!result ? (
        <div className="rounded-xl border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
          This simulation has no results{sim.error_summary ? `: ${sim.error_summary}` : '.'}
        </div>
      ) : (
        <>
          <SummaryCards result={result} />

          <section className="rounded-xl border border-white/10 bg-card p-3">
            <h2 className="mb-1 text-sm font-medium">Initial events ({result.events.length})</h2>
            <ul className="grid gap-x-6 gap-y-1 text-sm text-slate-300 md:grid-cols-2">
              {result.events.map((e) => (
                <li key={e.id}>
                  {e.label}{e.duration !== null ? `, lasts ${hours(e.duration)}` : ', until the end of the run'}
                </li>
              ))}
            </ul>
          </section>

          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
            <span>Showing the steady state at t={hours(result.evaluated_at)} (peak impact).</span>
            <label className="flex items-center gap-1.5">
              <input type="checkbox" checked={focusAffected} onChange={(e) => setFocusAffected(e.target.checked)} />
              Dim unaffected nodes
            </label>
            {(['operational', 'degraded', 'failed', 'maintenance'] as const).map((s) => (
              <span key={s} className="flex items-center gap-1 capitalize">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATE_COLORS[s] }} />{s}
              </span>
            ))}
            <span>White border = direct · cyan/violet = selected node and its trace · red edges carry a loss</span>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_22rem]">
            <div className="overflow-hidden rounded-xl border border-white/10" style={{ height: '65vh', minHeight: 420 }}>
              <ResultGraph snapshot={snap} results={result.node_results} trace={selected !== null ? traces.get(selected) : undefined}
                selected={selected} focusAffected={focusAffected} focusNonce={nonce} onSelect={setSelected} />
            </div>
            <aside>
              {sel ? (
                <NodePanel node={sel} trace={traces.get(sel.node_id)} events={selEvents} suppliers={suppliers}
                  capacity={capacity.get(sel.node_id)} onSelect={pickFromTable} />
              ) : (
                <section className="rounded-xl border border-white/10 bg-card p-3 text-sm text-slate-400">
                  Click a node in the graph or the table to see why it was affected, its supplier inputs and its dependency path.
                </section>
              )}
            </aside>
          </div>

          <div>
            <div className="mb-3 flex flex-wrap gap-1 border-b border-white/10">
              {TABS.map(([key, label]) => (
                <button key={key} onClick={() => setTab(key)}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === key ? 'border-accent text-accent' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
                  {label}{key === 'notes' && result.warnings.length > 0 ? ` (${result.warnings.length})` : ''}
                </button>
              ))}
            </div>
            {tab === 'nodes' && <NodeTable rows={result.node_results} selected={selected} onSelect={pickFromTable} />}
            {tab === 'timeline' && <TimelineTab timeline={result.timeline} events={result.events} peakTime={result.metrics.peak_time} />}
            {tab === 'capacity' && <CapacityTab rows={result.capacity} />}
            {tab === 'notes' && <NotesTab result={result} modelVersion={sim.model_version} />}
          </div>
        </>
      )}
    </div>
  )
}