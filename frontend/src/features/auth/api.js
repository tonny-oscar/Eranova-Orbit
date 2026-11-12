import { ApiError, apiRequest, setCsrfToken } from '@/lib/api/client'

export async function fetchMe({ signal } = {}) {
  try {
    const me = await apiRequest('/api/v1/auth/me', { signal })
    setCsrfToken(me.csrf_token)
    return me
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      setCsrfToken(null)
      return null
    }
    throw error
  }
}

export async function login(credentials) {
  const me = await apiRequest('/api/v1/auth/login', { method: 'POST', body: credentials })
  setCsrfToken(me.csrf_token)
  return me
}

export async function logout() {
  try {
    await apiRequest('/api/v1/auth/logout', { method: 'POST' })
  } finally {
    setCsrfToken(null)
  }
}

export function changePassword(payload) {
  return apiRequest('/api/v1/auth/change-password', { method: 'POST', body: payload })
}
