import type { EventType, EventTypeInfo, ScenarioEvent } from '../types'

export interface Draft {
  key: string
  id?: number
  event_type: EventType
  target: string
  pct: string
  start: string
  duration: string
}

export interface EventPayload {
  event_type: EventType
  target_node_id: number
  params: Record<string, number>
  start_time: number
  duration: number | null
}

let seq = 0
export const nextKey = () => `d${++seq}`

export function newDraft(): Draft {
  return { key: nextKey(), event_type: 'failure', target: '', pct: '', start: '0', duration: '' }
}

export function toDrafts(events: ScenarioEvent[], types: Record<string, EventTypeInfo>): Draft[] {
  return events.map((e) => {
    const p = types[e.event_type]?.param
    return {
      key: nextKey(),
      id: e.id,
      event_type: e.event_type,
      target: e.target_node_id === null ? '' : String(e.target_node_id),
      pct: p && e.params[p] !== undefined ? String(e.params[p]) : '',
      start: String(e.start_time),
      duration: e.duration === null ? '' : String(e.duration),
    }
  })
}

/** Converts form rows to API payloads. Throws an Error with a readable message if a row is incomplete. */
export function toPayload(drafts: Draft[], types: Record<string, EventTypeInfo>): EventPayload[] {
  return drafts.map((d, i) => {
    const where = `Event ${i + 1}`
    const info = types[d.event_type]
    if (!info) throw new Error(`${where}: unknown event type.`)
    if (!d.target) throw new Error(`${where}: choose a target node.`)
    const num = (text: string, label: string) => {
      const v = Number(text)
      if (text.trim() === '' || !Number.isFinite(v)) throw new Error(`${where}: ${label} must be a number.`)
      return v
    }
    const params: Record<string, number> = {}
    if (info.param) params[info.param] = num(d.pct, info.param_label ?? info.param)
    const start = d.start.trim() === '' ? 0 : num(d.start, 'start time')
    let duration: number | null = null
    if (info.duration !== 'forbidden' && d.duration.trim() !== '') duration = num(d.duration, 'duration')
    if (info.duration === 'required' && duration === null) throw new Error(`${where}: a duration is required.`)
    return { event_type: d.event_type, target_node_id: Number(d.target), params, start_time: start, duration }
  })
}