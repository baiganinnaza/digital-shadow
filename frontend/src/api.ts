const BASE = '/api'

export interface Signal {
  id: number
  object_id: number
  object_key: string
  type: string
  score: number
  category: string
  reasons: { rule: string; weight: number }[]
  created_at: string
  status: string
}

export interface ObjectDetail {
  id: number
  key: string
  type: string
  attrs: Record<string, unknown>
  signals: { id: number; score: number; category: string; reasons: unknown[]; status: string }[]
  entities: { type: string; value: string; confidence: number }[]
  provenance: { source: string; source_url: string | null; collected_at: string }[]
}

export interface GraphData {
  nodes: { id: string; key: string; type: string; risk: number }[]
  edges: { source: string; target: string; type: string; reason: string }[]
}

export interface CaseItem {
  id: number
  title: string
  object_id: number
  note: string | null
  created_at: string
}

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

export const api = {
  signals: (sort = 'risk_desc', limit = 50) =>
    req<Signal[]>(`/signals?sort=${sort}&limit=${limit}`),

  object: (id: number) => req<ObjectDetail>(`/objects/${id}`),

  graph: (objectId: number, depth = 2) =>
    req<GraphData>(`/graph/${objectId}?depth=${depth}`),

  createCase: (title: string, objectId: number, note?: string) =>
    req<{ id: number }>('/cases', {
      method: 'POST',
      body: JSON.stringify({ title, object_id: objectId, note }),
    }),

  cases: () => req<CaseItem[]>('/cases'),

  feedback: (signalId: number, verdict: 'true_positive' | 'false_positive') =>
    req<{ ok: boolean }>('/feedback', {
      method: 'POST',
      body: JSON.stringify({ signal_id: signalId, verdict }),
    }),

  dismiss: (signalId: number) =>
    req<{ ok: boolean }>(`/signals/${signalId}/dismiss`, { method: 'POST' }),
}
