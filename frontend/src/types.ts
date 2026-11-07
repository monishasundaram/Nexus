export const CATEGORIES = ['building', 'road', 'electricity', 'water', 'drainage',
  'transport', 'communication', 'generic'] as const
export const STATES = ['operational', 'degraded', 'failed', 'maintenance'] as const
export const RELATIONSHIPS = ['required', 'partial', 'backup'] as const

export type Category = (typeof CATEGORIES)[number]
export type State = (typeof STATES)[number]
export type Relationship = (typeof RELATIONSHIPS)[number]

export interface NexusNode {
  id: number
  environment_id: number
  name: string
  category: Category
  description: string
  pos_x: number
  pos_y: number
  state: State
  capacity: number
  demand: number
  importance: number
  latitude: number | null
  longitude: number | null
  meta: Record<string, unknown>
}

export interface NexusEdge {
  id: number
  environment_id: number
  source_id: number
  destination_id: number
  relationship_type: Relationship
  strength: number
  capacity: number | null
  description: string
  meta: Record<string, unknown>
}

export interface EnvironmentSummary {
  id: number
  project_id: number
  name: string
  description: string
  model_version: string
  is_demo: boolean
  created_at: string
  updated_at: string
  node_count: number
  edge_count: number
}

export interface EnvironmentDetail extends EnvironmentSummary {
  nodes: NexusNode[]
  edges: NexusEdge[]
}

export interface ValidationIssue {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
  node_ids: number[]
  edge_ids: number[]
}

export interface ValidationReport {
  valid: boolean
  error_count: number
  warning_count: number
  issues: ValidationIssue[]
  stats: { node_count: number; edge_count: number; categories: Record<string, number>; has_cycles: boolean }
}

export type EventType =
  | 'failure' | 'capacity_reduction' | 'road_closure'
  | 'resource_shortage' | 'maintenance' | 'recovery'

export interface EventTypeInfo {
  type: EventType
  label: string
  description: string
  param: string | null
  param_label: string | null
  duration: 'optional' | 'required' | 'forbidden'
  targets: Category[] | null
}

export interface ScenarioEvent {
  id: number
  event_type: EventType
  target_node_id: number | null
  params: Record<string, number>
  start_time: number
  duration: number | null
}

export interface Scenario {
  id: number
  environment_id: number
  parent_id: number | null
  name: string
  version: number
  description: string
  status: 'draft' | 'final'
  is_archived: boolean
  assumptions: string[]
  created_at: string
  updated_at: string
  events: ScenarioEvent[]
  simulation_count: number
  environment_name: string
}

export interface ScenarioIssue {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
  node_ids: number[]
  event_ids: number[]
}

export interface ScenarioValidationReport {
  valid: boolean
  error_count: number
  warning_count: number
  issues: ScenarioIssue[]
  stats: Record<string, unknown>
}


// ---------- simulations ----------
export interface SimMetrics {
  total_nodes: number
  affected_nodes: number
  direct_nodes: number
  indirect_nodes: number
  failed_nodes: number
  degraded_nodes: number
  improved_nodes: number
  impact_score: number
  peak_time: number
  final_time: number
  final_score: number
  recovered_at: number | null
  impact_hours: number
  affected_categories: Record<string, number>
  score_by_category: Record<string, number>
}

export interface NodeResult {
  node_id: number
  name: string
  category: Category
  importance: number
  baseline_level: number
  level: number
  delta: number
  baseline_state: State
  state: State
  impact: 'direct' | 'indirect' | 'none'
  trend: 'worse' | 'better' | 'same'
  absorbed: boolean
  event_ids: number[]
  availability: number
  output: number
  capacity: number
}

export interface Trace {
  node_id: number
  node_name: string
  impact: 'direct' | 'indirect'
  baseline_level: number
  level: number
  event_ids: number[]
  path: number[]
  path_names: string[]
  edge_ids: number[]
  explanation: string
}

export interface CapacityRow {
  node_id: number
  name: string
  category: string
  unit: string
  nominal_capacity: number
  baseline_output: number
  scenario_output: number
  demand: number
  baseline_unserved: number
  scenario_unserved: number
  baseline_level: number
  scenario_level: number
}

export interface TimelineStep {
  time: number
  impact_score: number
  affected_nodes: number
  failed_nodes: number
  degraded_nodes: number
  active_event_ids: number[]
  starting: number[]
  ending: number[]
}

export interface SimEvent {
  id: number
  type: string
  label: string
  target_node_id: number | null
  params: Record<string, number>
  start_time: number
  duration: number | null
}

export interface SimWarning {
  source: string
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
}

export interface SimResult {
  metrics: SimMetrics
  node_results: NodeResult[]
  traces: Trace[]
  warnings: SimWarning[]
  assumptions: string[]
  limitations: string[]
  capacity: CapacityRow[]
  unserved: Record<string, { baseline: number; scenario: number }>
  timeline: TimelineStep[]
  events: SimEvent[]
  solver: { max_sweeps: number; converged: boolean; steps: number }
  evaluated_at: number
  formula: string
}

export interface SimulationHead {
  id: number
  scenario_id: number
  scenario_name: string
  scenario_version: number
  environment_id: number | null
  environment_name: string
  model_version: string
  status: string
  started_at: string
  completed_at: string | null
  error_summary: string | null
  node_count: number
  edge_count: number
}

export interface SimulationDetail extends SimulationHead {
  result: SimResult | null
}

export interface SimulationRow extends SimulationHead {
  metrics: {
    impact_score: number
    affected_nodes: number
    failed_nodes: number
    degraded_nodes: number
  } | null
}

export interface SnapNode {
  id: number
  name: string
  category: Category
  state: State
  capacity: number
  demand: number
  importance: number
  meta: Record<string, unknown>
  pos_x?: number
  pos_y?: number
}

export interface SnapEdge {
  id: number
  source_id: number
  destination_id: number
  relationship_type: Relationship
  strength: number
  capacity: number | null
}

export interface Snapshot {
  environment: { id: number; name: string; model_version: string; is_demo?: boolean }
  scenario: { id: number; name: string; version: number; description: string; assumptions: string[] }
  nodes: SnapNode[]
  edges: SnapEdge[]
  events: {
    id: number
    event_type: string
    target_node_id: number | null
    params: Record<string, number>
    start_time: number
    duration: number | null
  }[]
}