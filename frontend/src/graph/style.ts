import type { Category, State } from '../types'

export const CATEGORY_COLORS: Record<Category, string> = {
  building: '#60A5FA', road: '#94A3B8', electricity: '#FACC15', water: '#38BDF8',
  drainage: '#2DD4BF', transport: '#8B5CF6', communication: '#F472B6', generic: '#A3A3A3',
}

export const STATE_COLORS: Record<State, string> = {
  operational: '#22C55E', degraded: '#F59E0B', failed: '#EF4444', maintenance: '#8B5CF6',
}

export const MARK_COLORS = {
  selected: '#FFFFFF', upstream: '#8B5CF6', downstream: '#22D3EE', issue: '#F59E0B',
} as const