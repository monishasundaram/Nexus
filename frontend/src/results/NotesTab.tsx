import type { SimResult } from '../types'

const TONE = { error: 'border-danger/50 bg-danger/10 text-red-200', warning: 'border-warn/50 bg-warn/10 text-amber-200',
  info: 'border-white/15 bg-white/5 text-slate-300' } as const

export default function NotesTab({ result, modelVersion }: { result: SimResult; modelVersion: string }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="space-y-2">
        <h3 className="font-medium">Validation warnings ({result.warnings.length})</h3>
        {result.warnings.length === 0 && <p className="text-sm text-slate-400">The graph and scenario raised no warnings.</p>}
        <ul className="space-y-1.5">
          {result.warnings.map((w, i) => (
            <li key={i} className={`rounded-md border px-2 py-1.5 text-xs ${TONE[w.level]}`}>
              <span className="font-medium uppercase">{w.level}</span> · <span className="text-slate-400">{w.source}</span> · {w.message}
            </li>
          ))}
        </ul>
        <div className="rounded-md border border-white/10 bg-card p-2 text-xs text-slate-400">
          Solver: {result.solver.steps} time step(s), up to {result.solver.max_sweeps} sweep(s),{' '}
          {result.solver.converged ? 'converged' : <b className="text-warn">did not converge</b>}. Model v{modelVersion}.
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="mb-1 font-medium">Impact score formula</h3>
          <p className="rounded-md bg-surface p-2 font-mono text-xs text-slate-300">{result.formula}</p>
        </div>
        <div>
          <h3 className="mb-1 font-medium">Model and scenario assumptions</h3>
          <ul className="list-disc space-y-1 pl-5 text-xs text-slate-300">
            {result.assumptions.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 font-medium">Limitations</h3>
          <ul className="list-disc space-y-1 pl-5 text-xs text-slate-300">
            {result.limitations.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      </section>
    </div>
  )
}