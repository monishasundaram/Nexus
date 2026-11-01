export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: string[]; msg: string }) => {
        const where = (d.loc ?? []).slice(1).join('.')
        const msg = d.msg.replace(/^Value error, /, '')
        return where ? `${where}: ${msg}` : msg
      })
      .join('; ')
  }
  return fallback
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail: unknown
    try {
      detail = (await res.json()).detail
    } catch {
      /* no JSON body */
    }
    throw new ApiError(detailToMessage(detail, `Request failed (${res.status})`), res.status)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = <T>(path: string) => request<T>('GET', path)
export const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body)
export const patch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
export const del = (path: string) => request<void>('DELETE', path)

// The server stores UTC but sends timestamps without a "Z"
export function formatDate(iso: string): string {
  const utc = /(Z|[+-]\d\d:\d\d)$/.test(iso) ? iso : `${iso}Z`
  return new Date(utc).toLocaleString()
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