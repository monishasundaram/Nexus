import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SimEvent, TimelineStep } from '../types'
import { hours, score } from './format'

export default function TimelineTab({ timeline, events, peakTime }: {
  timeline: TimelineStep[]
  events: SimEvent[]
  peakTime: number
}) {
  const label = (id: number) => events.find((e) => e.id === id)?.label ?? `event ${id}`
  const data = timeline.map((s) => ({ time: s.time, score: s.impact_score }))
  return (
    <div className="space-y-3">
      {timeline.length === 1 ? (
        <p className="rounded-xl border border-white/10 bg-card p-3 text-sm text-slate-300">
          All events start at t=0 and never end, so the scenario has a single steady state. Add start times,
          durations or a recovery event to see service change over time.
        </p>
      ) : (
        <div className="rounded-xl border border-white/10 bg-card p-3">
          <h3 className="mb-2 text-sm font-medium">Impact score over time (steady state at each event change)</h3>
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer>
              <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="#243049" strokeDasharray="3 3" />
                <XAxis dataKey="time" type="number" domain={['dataMin', 'dataMax']} stroke="#94A3B8"
                  tickFormatter={(v: number) => `${v} h`} />
                <YAxis domain={[0, 1]} stroke="#94A3B8" />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #243049' }}
                  formatter={(v) => [score(Number(v)), 'Impact score']} labelFormatter={(t) => `t = ${t} h`} />
                <Line type="stepAfter" dataKey="score" stroke="#22D3EE" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full min-w-[600px] text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-2">Time</th><th className="px-3 py-2">Score</th><th className="px-3 py-2">Affected</th>
              <th className="px-3 py-2">Failed / degraded</th><th className="px-3 py-2">What changes</th>
            </tr>
          </thead>
          <tbody>
            {timeline.map((s) => (
              <tr key={s.time} className="border-t border-white/5 align-top">
                <td className="px-3 py-1.5">{hours(s.time)}{s.time === peakTime && <span className="ml-2 rounded bg-warn/15 px-1.5 text-xs text-warn">peak</span>}</td>
                <td className="px-3 py-1.5">{score(s.impact_score)}</td>
                <td className="px-3 py-1.5">{s.affected_nodes}</td>
                <td className="px-3 py-1.5">{s.failed_nodes} / {s.degraded_nodes}</td>
                <td className="px-3 py-1.5 text-xs text-slate-300">
                  {s.starting.map((id) => <div key={`s${id}`}>starts: {label(id)}</div>)}
                  {s.ending.map((id) => <div key={`e${id}`}>ends: {label(id)}</div>)}
                  {s.starting.length === 0 && s.ending.length === 0 && <span className="text-slate-500">initial state</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}