import { NavLink, Outlet } from 'react-router-dom'

const links = [
  ['/', 'Dashboard'], ['/environments', 'Environments'], ['/explorer', 'Dependency Explorer'],
  ['/scenarios', 'Scenarios'], ['/results', 'Results'], ['/compare', 'Compare'],
  ['/interventions', 'Interventions'], ['/sensitivity', 'Sensitivity'], ['/reports', 'Reports'],
]

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="bg-surface border-b md:border-b-0 md:border-r border-white/10 md:w-60 shrink-0">
        <div className="p-4">
          <div className="text-xl font-bold text-accent tracking-wide">NEXUS</div>
          <div className="text-xs text-slate-400">Change One Thing. Discover Everything That Follows.</div>
        </div>
        <nav className="flex md:flex-col gap-1 px-2 pb-3 overflow-x-auto">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive ? 'bg-accent/15 text-accent' : 'text-slate-300 hover:bg-white/5'}`}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-4 md:p-8"><Outlet /></main>
    </div>
  )
}