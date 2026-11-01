import { describe, expect, it } from 'vitest'
import type { EventTypeInfo } from '../types'
import { toDrafts, toPayload, type Draft } from './draft'

const types: Record<string, EventTypeInfo> = {
  failure: { type: 'failure', label: 'Failure', description: '', param: null, param_label: null, duration: 'optional', targets: null },
  capacity_reduction: { type: 'capacity_reduction', label: 'Capacity reduction', description: '', param: 'reduction_pct', param_label: 'Reduction (%)', duration: 'optional', targets: null },
  maintenance: { type: 'maintenance', label: 'Maintenance', description: '', param: null, param_label: null, duration: 'required', targets: null },
  recovery: { type: 'recovery', label: 'Recovery', description: '', param: null, param_label: null, duration: 'forbidden', targets: null },
}

const draft = (over: Partial<Draft> = {}): Draft => ({
  key: 'k', event_type: 'failure', target: '1', pct: '', start: '0', duration: '', ...over,
})

describe('toPayload', () => {
  it('builds a simple failure', () => {
    expect(toPayload([draft()], types)).toEqual([
      { event_type: 'failure', target_node_id: 1, params: {}, start_time: 0, duration: null },
    ])
  })
  it('requires a target', () => {
    expect(() => toPayload([draft({ target: '' })], types)).toThrow(/target/)
  })
  it('parses the percentage parameter and requires it', () => {
    const ok = toPayload([draft({ event_type: 'capacity_reduction', pct: '50' })], types)
    expect(ok[0].params).toEqual({ reduction_pct: 50 })
    expect(() => toPayload([draft({ event_type: 'capacity_reduction' })], types)).toThrow(/Reduction/)
  })
  it('ignores duration text for events that cannot have one', () => {
    expect(toPayload([draft({ event_type: 'recovery', duration: '9' })], types)[0].duration).toBeNull()
  })
  it('requires a duration for maintenance and rejects non-numbers', () => {
    expect(() => toPayload([draft({ event_type: 'maintenance' })], types)).toThrow(/duration is required/)
    expect(() => toPayload([draft({ duration: 'abc' })], types)).toThrow(/duration must be a number/)
  })
})

describe('toDrafts', () => {
  it('turns saved events into form rows', () => {
    const rows = toDrafts(
      [{ id: 5, event_type: 'capacity_reduction', target_node_id: 3, params: { reduction_pct: 50 }, start_time: 2, duration: null }],
      types,
    )
    expect(rows[0]).toMatchObject({ id: 5, target: '3', pct: '50', start: '2', duration: '' })
  })
})