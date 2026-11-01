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