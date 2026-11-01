import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import EnvironmentEditor from './pages/EnvironmentEditor'
import Environments from './pages/Environments'
import Explorer from './pages/Explorer'
import Placeholder from './pages/Placeholder'

const pages: [string, string, number][] = [
  ['scenarios', 'Scenario Builder', 3], ['results', 'Simulation Results', 5],
  ['compare', 'Scenario Comparison', 6], ['interventions', 'Intervention Planner', 6],
  ['sensitivity', 'Sensitivity Analysis', 7], ['reports', 'Reports', 8],
]

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="environments" element={<Environments />} />
        <Route path="environments/:envId" element={<EnvironmentEditor />} />
        <Route path="explorer" element={<Explorer />} />
        {pages.map(([path, title, phase]) => (
          <Route key={path} path={path} element={<Placeholder title={title} phase={phase} />} />
        ))}
      </Route>
    </Routes>
  )
}