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