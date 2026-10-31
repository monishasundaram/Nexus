export async function api<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json()
}

export interface Health { status: string; database: string; model_version: string }
export interface DashboardData {
  environments: number
  scenarios: number
  completed_simulations: number
  recent_simulations: { id: number; scenario_id: number; status: string; started_at: string }[]
  category_distribution: { category: string; count: number }[]
  most_affected_nodes: { name: string; count: number }[]
}