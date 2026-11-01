import { useState, type ChangeEvent, type FormEvent } from 'react'
import { CATEGORIES, STATES, type Category, type NexusNode, type State } from '../types'
import Field from './Field'
import { btnDanger, btnPrimary, inputClass } from './formStyles'

type Props = {
  node: NexusNode
  onSave: (patch: Partial<NexusNode>) => Promise<void>
  onDelete: () => void
}
type Form = Record<
  'name' | 'category' | 'state' | 'description' | 'capacity' | 'demand' | 'importance' | 'latitude' | 'longitude' | 'meta',
  string
>

export default function NodeForm({ node, onSave, onDelete }: Props) {
  const [f, setF] = useState<Form>({
    name: node.name, category: node.category, state: node.state, description: node.description,
    capacity: String(node.capacity), demand: String(node.demand), importance: String(node.importance),
    latitude: node.latitude?.toString() ?? '', longitude: node.longitude?.toString() ?? '',
    meta: JSON.stringify(node.meta, null, 2),
  })
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const bind = (k: keyof Form) => ({
    value: f[k],
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setF((p) => ({ ...p, [k]: e.target.value })),
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    let meta: Record<string, unknown>
    try {
      meta = JSON.parse(f.meta || '{}')
      if (typeof meta !== 'object' || meta === null || Array.isArray(meta)) throw new Error()
    } catch {
      setErr('Metadata must be a valid JSON object, e.g. {"unit": "kW"}')
      return
    }
    setBusy(true)
    await onSave({
      name: f.name,
      category: f.category as Category,
      state: f.state as State,
      description: f.description,
      capacity: Number(f.capacity),
      demand: Number(f.demand),
      importance: Number(f.importance),
      latitude: f.latitude === '' ? null : Number(f.latitude),
      longitude: f.longitude === '' ? null : Number(f.longitude),
      meta,
    })
    setBusy(false)
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <h2 className="font-medium">Node #{node.id}</h2>
      <Field label="Name"><input className={inputClass} {...bind('name')} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Category">
          <select className={inputClass} {...bind('category')}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="State">
          <select className={inputClass} {...bind('state')}>
            {STATES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Description">
        <textarea rows={2} className={inputClass} {...bind('description')} />
      </Field>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Capacity"><input type="number" min={0} step="any" className={inputClass} {...bind('capacity')} /></Field>
        <Field label="Demand"><input type="number" min={0} step="any" className={inputClass} {...bind('demand')} /></Field>
        <Field label="Importance 0-1"><input type="number" min={0} max={1} step="0.05" className={inputClass} {...bind('importance')} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Latitude (optional)"><input type="number" step="any" className={inputClass} {...bind('latitude')} /></Field>
        <Field label="Longitude (optional)"><input type="number" step="any" className={inputClass} {...bind('longitude')} /></Field>
      </div>
      <Field label="Metadata (JSON)">
        <textarea rows={4} className={`${inputClass} font-mono text-xs`} {...bind('meta')} />
      </Field>
      {err && <p className="text-xs text-danger">{err}</p>}
      <div className="flex gap-2">
        <button className={btnPrimary} disabled={busy}>Save changes</button>
        <button type="button" className={btnDanger} onClick={onDelete}>Delete node</button>
      </div>
    </form>
  )
}