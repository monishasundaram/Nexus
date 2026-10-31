import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Placeholder from './pages/Placeholder'

const pages: [string, string, number][] = [
  ['environments', 'Environment Builder', 2], ['explorer', 'Dependency Explorer', 2],
  ['scenarios', 'Scenario Builder', 3], ['results', 'Simulation Results', 5],
  ['compare', 'Scenario Comparison', 6], ['interventions', 'Intervention Planner', 6],
  ['sensitivity', 'Sensitivity Analysis', 7], ['reports', 'Reports', 8],
]

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        {pages.map(([path, title, phase]) => (
          <Route key={path} path={path} element={<Placeholder title={title} phase={phase} />} />
        ))}
      </Route>
    </Routes>
  )
}