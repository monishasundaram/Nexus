import { useMemo, useState } from 'react'
import { inputClass } from '../components/formStyles'
import { STATE_COLORS } from '../graph/style'
import { CATEGORIES, type Category, type NodeResult } from '../types'
import { deltaPts, filterNodes, pct, type ImpactFilter, type NodeSort } from './format'

interface Props {
  rows: NodeResult[]
  selected: number | null
  onSelect: (id: number) => void
}

const IMPACT_LABEL: Record<NodeResult['impact'], string> = { direct: 'Direct', indirect: 'Indirect', none: '—' }

export default function NodeTable({ rows, selected, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [impact, setImpact] = useState<ImpactFilter>('affected')
  const [category, setCategory] = useState<'all' | Category>('all')
  const [sort, setSort] = useState<NodeSort>('delta')
  const shown = useMemo(() => filterNodes(rows, { query, impact, category }, sort), [rows, query, impact, category, sort])

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-48">
          <input className={inputClass} placeholder="Search nodes" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <select className={`${inputClass} w-44`} value={impact} aria-label="Impact filter"
          onChange={(e) => setImpact(e.target.value as ImpactFilter)}>
          <option value="affected">Affected nodes</option>
          <option value="direct">Directly affected</option>
          <option value="indirect">Indirectly affected</option>
          <option value="none">Not affected</option>
          <option value="all">All nodes</option>
        </select>
        <select className={`${inputClass} w-40`} value={category} aria-label="Category filter"
          onChange={(e) => setCategory(e.target.value as 'all' | Category)}>
          <option value="all">All categories</option>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className={`${inputClass} w-44`} value={sort} aria-label="Sort"
          onChange={(e) => setSort(e.target.value as NodeSort)}>
          <option value="delta">Biggest loss first</option>
          <option value="importance">Most important first</option>
          <option value="name">Name</option>
        </select>
        <span className="text-xs text-slate-500">{shown.length} of {rows.length} nodes</span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full min-w-160 text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-2">Node</th><th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Service level</th><th className="px-3 py-2">Change</th>
              <th className="px-3 py-2">State</th><th className="px-3 py-2">Impact</th>
              <th className="px-3 py-2 text-right">Weight</th>
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-slate-400">No nodes match these filters.</td></tr>
            )}
            {shown.map((r) => (
              <tr key={r.node_id} onClick={() => onSelect(r.node_id)}
                className={`cursor-pointer border-t border-white/5 hover:bg-white/5 ${r.node_id === selected ? 'bg-accent/10' : ''}`}>
                <td className="px-3 py-1.5 font-medium">{r.name}</td>
                <td className="px-3 py-1.5 capitalize text-slate-400">{r.category}</td>
                <td className="px-3 py-1.5">{pct(r.baseline_level)} → {pct(r.level)}</td>
                <td className={`px-3 py-1.5 ${r.delta < 0 ? 'text-danger' : r.delta > 0 ? 'text-ok' : 'text-slate-500'}`}>{deltaPts(r.delta)}</td>
                <td className="px-3 py-1.5">
                  <span className="inline-flex items-center gap-1.5 capitalize">
                    <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLORS[r.state] }} />{r.state}
                  </span>
                </td>
                <td className="px-3 py-1.5">{r.absorbed ? 'Absorbed' : IMPACT_LABEL[r.impact]}</td>
                <td className="px-3 py-1.5 text-right text-slate-400">{r.importance}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}