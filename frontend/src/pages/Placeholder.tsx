export default function Placeholder({ title, phase }: { title: string; phase: number }) {
  return (
    <div className="rounded-xl bg-card border border-dashed border-white/20 p-8">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-sm text-slate-400 mt-1">Coming in Phase {phase}.</p>
    </div>
  )
}