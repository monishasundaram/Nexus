import type { ReactNode } from 'react'

export default function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-xs text-slate-400">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  )
}