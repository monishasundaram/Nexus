import type { ValidationIssue, ValidationReport } from '../types'

const LEVEL_STYLE: Record<ValidationIssue['level'], string> = {
  error: 'border-danger/50 bg-danger/10 text-red-200',
  warning: 'border-warn/50 bg-warn/10 text-amber-200',
  info: 'border-white/15 bg-white/5 text-slate-300',
}

export default function ValidationPanel({
  report, onSelect,
}: { report: ValidationReport; onSelect: (issue: ValidationIssue) => void }) {
  return (
    <section className="rounded-xl bg-card border border-white/10 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="font-medium">Validation</h2>
        <span className={`rounded-full px-2 py-0.5 text-xs ${report.valid ? 'bg-ok/15 text-ok' : 'bg-danger/15 text-danger'}`}>
          {report.valid ? 'Valid' : 'Invalid'} · {report.error_count} errors · {report.warning_count} warnings
        </span>
      </div>
      {report.issues.length === 0 && (
        <p className="text-sm text-slate-400">No issues found in {report.stats.node_count} nodes and {report.stats.edge_count} connections.</p>
      )}
      <ul className="space-y-1.5 max-h-72 overflow-y-auto">
        {report.issues.map((i, idx) => (
          <li key={idx}>
            <button onClick={() => onSelect(i)}
              className={`w-full rounded-md border px-2 py-1.5 text-left text-xs ${LEVEL_STYLE[i.level]}`}>
              <span className="font-medium uppercase">{i.level}</span> · {i.message}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}