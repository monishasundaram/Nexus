import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import EnvironmentEditor from './pages/EnvironmentEditor'
import Environments from './pages/Environments'
import Explorer from './pages/Explorer'
import Placeholder from './pages/Placeholder'
import Results from './pages/Results'
import ScenarioEditor from './pages/ScenarioEditor'
import Scenarios from './pages/Scenarios'
import SimulationResult from './pages/SimulationResult'

const pages: [string, string, number][] = [
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
        <Route path="scenarios" element={<Scenarios />} />
        <Route path="scenarios/:scenarioId" element={<ScenarioEditor />} />
        <Route path="results" element={<Results />} />
        <Route path="results/:simId" element={<SimulationResult />} />
        {pages.map(([path, title, phase]) => (
          <Route key={path} path={path} element={<Placeholder title={title} phase={phase} />} />
        ))}
      </Route>
    </Routes>
  )
}