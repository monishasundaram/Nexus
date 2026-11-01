import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Background, Controls, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow } from '@xyflow/react'
import { api } from '../api/client'
import { inputClass } from '../components/formStyles'
import { toFlowEdge, toFlowNode, type InfraData } from '../graph/convert'
import { nodeTypes } from '../graph/nodeTypes'
import { CATEGORY_COLORS, MARK_COLORS } from '../graph/style'
import { reach } from '../graph/traverse'
import {
  CATEGORIES, STATES, type Category, type EnvironmentDetail, type EnvironmentSummary, type NexusNode, type State,
} from '../types'

export default function Explorer() {
  return (
    <ReactFlowProvider>
      <Inner />
    </ReactFlowProvider>
  )
}

function Inner() {
  const rf = useReactFlow()
  const [envs, setEnvs] = useState<EnvironmentSummary[] | null>(null)
  const [envId, setEnvId] = useState<number | null>(null)
  const [env, setEnv] = useState<EnvironmentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<'all' | Category>('all')
  const [stateFilter, setStateFilter] = useState<'all' | State>('all')
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    api<EnvironmentSummary[]>('/environments')
      .then((list) => { setEnvs(list); if (list.length) setEnvId(list[0].id) })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (envId === null) return
    api<EnvironmentDetail>(`/environments/${envId}`).then(setEnv).catch((e: Error) => setError(e.message))
  }, [envId])

  const links = useMemo(
    () => (env?.edges ?? []).map((e) => ({ source: String(e.source_id), target: String(e.destination_id) })),
    [env],
  )
  const byId = useMemo(
    () => new Map((env?.nodes ?? []).map((n): [string, NexusNode] => [String(n.id), n])),
    [env],
  )
  const up = useMemo(() => (selected ? reach(selected, links, 'up') : new Set<string>()), [selected, links])
  const down = useMemo(() => (selected ? reach(selected, links, 'down') : new Set<string>()), [selected, links])
  const ranking = useMemo(
    () => (env?.nodes ?? [])
      .map((n) => ({ node: n, downstream: reach(String(n.id), links, 'down').size }))
      .sort((a, b) => b.downstream - a.downstream)
      .slice(0, 6),
    [env, links],
  )

  const term = search.trim().toLowerCase()

  const flowNodes = useMemo(
    () => (env?.nodes ?? []).map((n) => {
      const id = String(n.id)
      const mark: InfraData['mark'] =
        id === selected ? 'selected' : up.has(id) ? 'upstream' : down.has(id) ? 'downstream' : undefined
      const matches =
        (!term || n.name.toLowerCase().includes(term)) &&
        (category === 'all' || n.category === category) &&
        (stateFilter === 'all' || n.state === stateFilter)
      return toFlowNode(n, { mark, dim: !matches || (selected !== null && !mark) })
    }),
    [env, selected, up, down, term, category, stateFilter],
  )

  const flowEdges = useMemo(
    () => (env?.edges ?? []).map((e) => {
      const s = String(e.source_id)
      const t = String(e.destination_id)
      let color: string | undefined
      if (selected) {
        if ((s === selected || down.has(s)) && down.has(t)) color = MARK_COLORS.downstream
        else if ((t === selected || up.has(t)) && up.has(s)) color = MARK_COLORS.upstream
      }
      return toFlowEdge(e, color, selected !== null && !color)
    }),
    [env, selected, up, down],
  )

  function pick(id: string) {
    setSelected(id)
    rf.fitView({ nodes: [{ id }], duration: 400, padding: 1.5, maxZoom: 1 })
  }

  if (error) return <div className="rounded-xl bg-danger/10 border border-danger/40 p-4 text-danger">{error}</div>
  if (!envs) return <div className="text-slate-400">Loading…</div>
  if (envs.length === 0)
    return (
      <div className="rounded-xl bg-card border border-dashed border-white/20 p-8 text-center">
        <p className="font-medium">Nothing to explore yet</p>
        <p className="mt-1 text-sm text-slate-400">
          Create an environment or load the demo in <Link to="/environments" className="text-accent underline">Environments</Link>.
        </p>
      </div>
    )

  const sel = selected ? byId.get(selected) : undefined
  const suppliers = sel ? (env?.edges ?? []).filter((e) => e.destination_id === sel.id) : []
  const dependents = sel ? (env?.edges ?? []).filter((e) => e.source_id === sel.id) : []
  const nm = (id: number) => byId.get(String(id))?.name ?? `#${id}`

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">Dependency Explorer</h1>
      <div className="flex flex-wrap items-center gap-2">
        <select className={`${inputClass} w-52`} value={envId ?? ''} aria-label="Environment"
          onChange={(e) => { setEnv(null); setSelected(null); setEnvId(Number(e.target.value)) }}>
          {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <div className="w-48">
          <input className={inputClass} placeholder="Search nodes" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className={`${inputClass} w-40`} value={category} aria-label="Category filter"
          onChange={(e) => setCategory(e.target.value as 'all' | Category)}>
          <option value="all">All categories</option>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className={`${inputClass} w-40`} value={stateFilter} aria-label="State filter"
          onChange={(e) => setStateFilter(e.target.value as 'all' | State)}>
          <option value="all">All states</option>
          {STATES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <span className="flex items-center gap-3 text-xs text-slate-400">
          <Legend color={MARK_COLORS.selected} label="selected" />
          <Legend color={MARK_COLORS.upstream} label="upstream (suppliers)" />
          <Legend color={MARK_COLORS.downstream} label="downstream (dependents)" />
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_22rem]">
        <div className="overflow-hidden rounded-xl border border-white/10" style={{ height: '70vh', minHeight: 420 }}>
          {env ? (
            <ReactFlow key={env.id} nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes}
              nodesDraggable={false} nodesConnectable={false} colorMode="dark" minZoom={0.1} fitView
              onNodeClick={(_, n) => setSelected(n.id)} onPaneClick={() => setSelected(null)}>
              <Background gap={24} color="#243049" />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable maskColor="rgba(11,16,32,0.7)" style={{ background: '#111827' }}
                nodeColor={(n) => CATEGORY_COLORS[(n.data as InfraData).node.category]} />
            </ReactFlow>
          ) : <div className="p-6 text-slate-400">Loading graph…</div>}
        </div>

        <aside className="space-y-3">
          {sel ? (
            <section className="space-y-3 rounded-xl border border-white/10 bg-card p-3 text-sm">
              <div>
                <h2 className="font-medium">{sel.name}</h2>
                <p className="text-xs capitalize text-slate-400">{sel.category} · {sel.state} · importance {sel.importance}</p>
              </div>
              <p className="text-xs text-slate-400">
                {up.size} nodes upstream (all) · {down.size} nodes downstream (all)
              </p>
              <LinkList title="Direct suppliers" items={suppliers.map((e) => ({ id: e.source_id, name: nm(e.source_id), note: `${e.relationship_type} ${e.strength}` }))} onPick={(id) => pick(String(id))} />
              <LinkList title="Direct dependents" items={dependents.map((e) => ({ id: e.destination_id, name: nm(e.destination_id), note: `${e.relationship_type} ${e.strength}` }))} onPick={(id) => pick(String(id))} />
              <p className="text-xs text-slate-500">Simulated effect explanations arrive with the engine in Phases 4-5.</p>
            </section>
          ) : (
            <section className="rounded-xl border border-white/10 bg-card p-3 text-sm">
              <h2 className="mb-1 font-medium">Most connected nodes</h2>
              <p className="mb-2 text-xs text-slate-500">
                Ranked by how many nodes depend on them, directly or indirectly. This is a structural count, not a simulation result.
              </p>
              <ul className="space-y-1">
                {ranking.map(({ node, downstream }) => (
                  <li key={node.id}>
                    <button className="flex w-full justify-between rounded-md px-2 py-1 text-left hover:bg-white/5"
                      onClick={() => pick(String(node.id))}>
                      <span>{node.name}</span><span className="text-slate-400">{downstream}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  )
}

function LinkList({ title, items, onPick }: {
  title: string
  items: { id: number; name: string; note: string }[]
  onPick: (id: number) => void
}) {
  return (
    <div>
      <h3 className="mb-1 text-xs uppercase tracking-wide text-slate-400">{title}</h3>
      {items.length === 0 ? <p className="text-xs text-slate-500">None</p> : (
        <ul className="space-y-0.5">
          {items.map((i) => (
            <li key={`${i.id}-${i.note}`}>
              <button className="flex w-full justify-between rounded-md px-2 py-1 text-left hover:bg-white/5" onClick={() => onPick(i.id)}>
                <span>{i.name}</span><span className="text-xs text-slate-500">{i.note}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}