const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

// `npm run dev:demo` only. Both values are build-time constants, so production
// bundles drop the demo code entirely and always talk to the real API.
export const DEMO_MODE = import.meta.env.DEV && import.meta.env.MODE === 'demo'

// Held in memory only; restored from /auth/me after a reload. The session
// cookie itself is HttpOnly and never readable from JavaScript.
let csrfToken = null

export function setCsrfToken(token) {
  csrfToken = token ?? null
}

export class ApiError extends Error {
  constructor({ status, code, message, details = [], correlationId = null }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.correlationId = correlationId
  }
}

async function demoApiRequest(path, method, body, query) {
  const { demoRequest } = await import('@/demo/demoApi')
  const cleanQuery = Object.fromEntries(
    Object.entries(query ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  )
  try {
    return await demoRequest(method, path, { query: cleanQuery, body })
  } catch (error) {
    throw new ApiError({
      status: error.status ?? 500,
      code: error.code ?? 'demo_error',
      message: error.message,
      details: error.details ?? [],
    })
  }
}

export async function apiRequest(path, { method = 'GET', body, query, signal } = {}) {
  if (DEMO_MODE) return demoApiRequest(path, method, body, query)

  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (!SAFE_METHODS.has(method) && csrfToken) headers['X-CSRF-Token'] = csrfToken

  let url = `${API_BASE_URL}${path}`
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }

  let response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: 'include',
      signal,
    })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new ApiError({
      status: 0,
      code: 'network_error',
      message: 'Unable to reach the Orbit API. Check your connection and try again.',
    })
  }

  if (response.status === 204) return null

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = data?.error
    throw new ApiError({
      status: response.status,
      code: error?.code ?? 'http_error',
      message: error?.message ?? `Request failed with status ${response.status}.`,
      details: error?.details ?? [],
      correlationId: error?.correlation_id ?? response.headers.get('X-Correlation-ID'),
    })
  }
  return data
}
