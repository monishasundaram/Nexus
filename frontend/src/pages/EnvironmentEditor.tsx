import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Background, Controls, MiniMap, ReactFlow, ReactFlowProvider,
  useEdgesState, useNodesState, useReactFlow, type Connection,
} from '@xyflow/react'
import { api, del, patch, post } from '../api/client'
import EdgeForm from '../components/EdgeForm'
import NodeForm from '../components/NodeForm'
import ValidationPanel from '../components/ValidationPanel'
import { btn, btnPrimary, inputClass } from '../components/formStyles'
import { toFlowEdge, toFlowNode, type InfraData, type InfraFlowNode, type NexusFlowEdge } from '../graph/convert'
import { nodeTypes } from '../graph/nodeTypes'
import { CATEGORY_COLORS } from '../graph/style'
import {
  CATEGORIES, type Category, type EnvironmentDetail, type EnvironmentSummary,
  type NexusEdge, type NexusNode, type ValidationIssue, type ValidationReport,
} from '../types'

type Status = { kind: 'idle' | 'saving' | 'saved' | 'error'; text?: string }

export default function EnvironmentEditor() {
  return (
    <ReactFlowProvider>
      <Editor />
    </ReactFlowProvider>
  )
}

function Editor() {
  const { envId } = useParams()
  const id = Number(envId)
  const rf = useReactFlow<InfraFlowNode, NexusFlowEdge>()

  const [env, setEnv] = useState<EnvironmentSummary | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<InfraFlowNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<NexusFlowEdge>([])
  const [selected, setSelected] = useState<{ kind: 'node' | 'edge'; id: string } | null>(null)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [loadError, setLoadError] = useState<string | null>(null)
  const [report, setReport] = useState<ValidationReport | null>(null)
  const [issueIds, setIssueIds] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [addCategory, setAddCategory] = useState<Category>('building')

  useEffect(() => {
    let cancelled = false
    api<EnvironmentDetail>(`/environments/${id}`)
      .then((d) => {
        if (cancelled) return
        setEnv(d)
        setNodes(d.nodes.map((n) => toFlowNode(n)))
        setEdges(d.edges.map((e) => toFlowEdge(e)))
      })
      .catch((e: Error) => {
        if (!cancelled) setLoadError(e.message)
      })
    return () => { cancelled = true }
  }, [id, setNodes, setEdges])

  async function save<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setStatus({ kind: 'saving' })
    try {
      const result = await fn()
      setStatus({ kind: 'saved' })
      return result
    } catch (e) {
      setStatus({ kind: 'error', text: (e as Error).message })
      return undefined
    }
  }

  // ---- actions ----
  async function addNode() {
    const names = new Set(nodes.map((n) => n.data.node.name.toLowerCase()))
    let i = nodes.filter((n) => n.data.node.category === addCategory).length + 1
    while (names.has(`new ${addCategory} ${i}`)) i++
    const pos = rf.screenToFlowPosition({ x: window.innerWidth / 2 - 100, y: window.innerHeight / 2 })
    const created = await save(() =>
      post<NexusNode>(`/environments/${id}/nodes`, {
        name: `New ${addCategory} ${i}`, category: addCategory,
        pos_x: Math.round(pos.x), pos_y: Math.round(pos.y),
      }))
    if (created) {
      setNodes((ns) => [...ns, toFlowNode(created)])
      setSelected({ kind: 'node', id: String(created.id) })
      setReport(null)
    }
  }

  async function onConnect(c: Connection) {
    if (!c.source || !c.target) return
    const created = await save(() =>
      post<NexusEdge>(`/environments/${id}/edges`, {
        source_id: Number(c.source), destination_id: Number(c.target),
      }))
    if (created) {
      setEdges((es) => [...es, toFlowEdge(created)])
      setSelected({ kind: 'edge', id: String(created.id) })
      setReport(null)
    }
  }

  async function saveNode(nodeId: string, changes: Partial<NexusNode>) {
    const updated = await save(() => patch<NexusNode>(`/nodes/${nodeId}`, changes))
    if (updated) {
      setNodes((ns) => ns.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, node: updated } } : n)))
      setReport(null)
    }
  }

  async function saveEdge(edgeId: string, changes: Partial<NexusEdge>) {
    const updated = await save(() => patch<NexusEdge>(`/edges/${edgeId}`, changes))
    if (updated) {
      setEdges((es) => es.map((e) => (e.id === edgeId ? toFlowEdge(updated) : e)))
      setReport(null)
    }
  }

  async function deleteNode(nodeId: string) {
    if (!window.confirm('Delete this node and all of its connections?')) return
    const ok = await save(async () => { await del(`/nodes/${nodeId}`); return true })
    if (ok) {
      setNodes((ns) => ns.filter((n) => n.id !== nodeId))
      setEdges((es) => es.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelected(null)
      setReport(null)
    }
  }

  async function deleteEdge(edgeId: string) {
    if (!window.confirm('Delete this connection?')) return
    const ok = await save(async () => { await del(`/edges/${edgeId}`); return true })
    if (ok) {
      setEdges((es) => es.filter((e) => e.id !== edgeId))
      setSelected(null)
      setReport(null)
    }
  }

  async function renameEnv(name: string) {
    if (!env || !name.trim() || name === env.name) return
    const updated = await save(() => patch<EnvironmentSummary>(`/environments/${id}`, { name }))
    if (updated) setEnv(updated)
  }

  async function runValidate() {
    const r = await save(() => post<ValidationReport>(`/environments/${id}/validate`))
    if (r) setReport(r)
  }

  function selectIssue(issue: ValidationIssue) {
    const ids = new Set(issue.node_ids.map(String))
    setIssueIds(ids)
    if (ids.size) rf.fitView({ nodes: [...ids].map((i) => ({ id: i })), duration: 400, padding: 0.8, maxZoom: 1.2 })
  }

  const term = search.trim().toLowerCase()
  function focusSearch() {
    const hits = nodes.filter((n) => n.data.node.name.toLowerCase().includes(term))
    if (term && hits.length) rf.fitView({ nodes: hits, duration: 400, padding: 0.6, maxZoom: 1.2 })
  }

  const shown = useMemo(
    () => nodes.map((n): InfraFlowNode => ({
      ...n,
      data: {
        ...n.data,
        dim: term ? !n.data.node.name.toLowerCase().includes(term) : false,
        mark: issueIds.has(n.id) ? 'issue' : undefined,
      },
    })),
    [nodes, term, issueIds],
  )

  const selNode = selected?.kind === 'node' ? nodes.find((n) => n.id === selected.id)?.data.node : undefined
  const selEdge = selected?.kind === 'edge' ? edges.find((e) => e.id === selected.id)?.data?.edge : undefined
  const nameOf = (nid: number) => nodes.find((n) => n.id === String(nid))?.data.node.name ?? `#${nid}`

  if (loadError)
    return (
      <div className="rounded-xl bg-danger/10 border border-danger/40 p-4 text-danger">
        {loadError} <Link to="/environments" className="underline">Back to environments</Link>
      </div>
    )
  if (!env) return <div className="text-slate-400">Loading…</div>

  const badge =
    status.kind === 'error' ? 'bg-danger/15 text-danger'
    : status.kind === 'saving' ? 'bg-warn/15 text-warn'
    : 'bg-ok/15 text-ok'

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/environments" className="text-sm text-slate-400 hover:text-accent">← Environments</Link>
        <div className="w-64">
          <input key={env.id} defaultValue={env.name} aria-label="Environment name" className={inputClass}
            maxLength={120} onBlur={(e) => renameEnv(e.target.value)} />
        </div>
        {env.is_demo && <span className="rounded-full bg-plasma/20 px-2 py-0.5 text-xs text-plasma">Synthetic demo data</span>}
        <span className={`ml-auto rounded-full px-3 py-1 text-xs ${badge}`}>
          {status.kind === 'saving' ? 'Saving…'
            : status.kind === 'error' ? `Error: ${status.text}`
            : status.kind === 'saved' ? 'All changes saved' : 'Up to date'}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select className={`${inputClass} w-40`} value={addCategory}
          onChange={(e) => setAddCategory(e.target.value as Category)} aria-label="Node category">
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <button className={btnPrimary} onClick={addNode}>+ Add node</button>
        <div className="w-56">
          <input className={inputClass} placeholder="Search nodes (Enter to zoom)" value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && focusSearch()} />
        </div>
        <button className={btn} onClick={runValidate}>Validate graph</button>
        <span className="text-xs text-slate-500">Drag from a node's right handle to another node's left handle: source supplies destination.</span>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_22rem]">
        <div className="overflow-hidden rounded-xl border border-white/10" style={{ height: '70vh', minHeight: 420 }}>
          <ReactFlow
            nodes={shown}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={(_, node) => {
              save(() => patch(`/nodes/${node.id}`, {
                pos_x: Math.round(node.position.x), pos_y: Math.round(node.position.y),
              }))
            }}
            onNodeClick={(_, n) => { setSelected({ kind: 'node', id: n.id }); setIssueIds(new Set()) }}
            onEdgeClick={(_, e) => setSelected({ kind: 'edge', id: e.id })}
            onPaneClick={() => { setSelected(null); setIssueIds(new Set()) }}
            deleteKeyCode={null}
            colorMode="dark"
            minZoom={0.1}
            fitView
          >
            <Background gap={24} color="#243049" />
            <Controls />
            <MiniMap pannable zoomable maskColor="rgba(11,16,32,0.7)" style={{ background: '#111827' }}
              nodeColor={(n) => CATEGORY_COLORS[(n.data as InfraData).node.category]} />
          </ReactFlow>
        </div>

        <aside className="space-y-3">
          <section className="rounded-xl bg-card border border-white/10 p-3">
            {selNode ? (
              <NodeForm key={selNode.id} node={selNode}
                onSave={(c) => saveNode(String(selNode.id), c)}
                onDelete={() => deleteNode(String(selNode.id))} />
            ) : selEdge ? (
              <EdgeForm key={selEdge.id} edge={selEdge}
                sourceName={nameOf(selEdge.source_id)} destName={nameOf(selEdge.destination_id)}
                onSave={(c) => saveEdge(String(selEdge.id), c)}
                onDelete={() => deleteEdge(String(selEdge.id))} />
            ) : (
              <p className="text-sm text-slate-400">
                Click a node or a connection to edit it. Changes are saved to the database as you make them.
              </p>
            )}
          </section>
          {report && <ValidationPanel report={report} onSelect={selectIssue} />}
        </aside>
      </div>
    </div>
  )
}