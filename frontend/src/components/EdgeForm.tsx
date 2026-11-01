import { useState, type FormEvent } from 'react'
import { RELATIONSHIPS, type NexusEdge, type Relationship } from '../types'
import Field from './Field'
import { btnDanger, btnPrimary, inputClass } from './formStyles'

type Props = {
  edge: NexusEdge
  sourceName: string
  destName: string
  onSave: (patch: Partial<NexusEdge>) => Promise<void>
  onDelete: () => void
}

export default function EdgeForm({ edge, sourceName, destName, onSave, onDelete }: Props) {
  const [type, setType] = useState<string>(edge.relationship_type)
  const [strength, setStrength] = useState(String(edge.strength))
  const [capacity, setCapacity] = useState(edge.capacity?.toString() ?? '')
  const [description, setDescription] = useState(edge.description)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    await onSave({
      relationship_type: type as Relationship,
      strength: Number(strength),
      capacity: capacity === '' ? null : Number(capacity),
      description,
    })
    setBusy(false)
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <h2 className="font-medium">Connection #{edge.id}</h2>
      <p className="text-xs text-slate-400">
        <span className="text-slate-200">{sourceName}</span> supplies{' '}
        <span className="text-slate-200">{destName}</span>
      </p>
      <Field label="Relationship type">
        <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
          {RELATIONSHIPS.map((r) => <option key={r}>{r}</option>)}
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Dependency strength 0-1">
          <input type="number" min={0} max={1} step="0.05" className={inputClass}
            value={strength} onChange={(e) => setStrength(e.target.value)} />
        </Field>
        <Field label="Capacity (optional)">
          <input type="number" min={0} step="any" className={inputClass}
            value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        </Field>
      </div>
      <Field label="Description">
        <textarea rows={2} className={inputClass} value={description}
          onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <div className="flex gap-2">
        <button className={btnPrimary} disabled={busy}>Save changes</button>
        <button type="button" className={btnDanger} onClick={onDelete}>Delete</button>
      </div>
    </form>
  )
}