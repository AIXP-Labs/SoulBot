// Centralized API helper for SoulBot backend (FastAPI + Uvicorn)

const API_BASE = ''  // Same origin — proxied in dev, same server in production

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const hasBody = options?.method && options.method !== 'GET'
  const headers: Record<string, string> = hasBody
    ? { 'Content-Type': 'application/json' }
    : {}
  const resp = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`API error ${resp.status}: ${text}`)
  }
  return resp.json()
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function apiDelete(path: string): Promise<{ status: string }> {
  return api(path, { method: 'DELETE' })
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export function sseUrl(path: string): string {
  return `${API_BASE}${path}`
}
