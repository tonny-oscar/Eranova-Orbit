import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'
import { createQueryClient } from '@/app/queryClient'
import { routes } from '@/app/routes'

export const ME = {
  user: {
    id: '11111111-1111-1111-1111-111111111111',
    email: 'ada@eranova.co.ke',
    full_name: 'Ada Lovelace',
    status: 'active',
    last_login_at: '2026-11-12T08:00:00Z',
  },
  company: { id: 'c', name: 'Eranova Technologies', slug: 'eranova', timezone: 'Africa/Nairobi' },
  permissions: ['product.read'],
  roles: [
    {
      assignment_id: 'a1',
      role_id: 'r1',
      role_slug: 'developer',
      role_name: 'Developer',
      scope_type: 'company',
      scope_id: null,
    },
  ],
  csrf_token: 'csrf-test-token',
  session_expires_at: '2026-11-12T20:00:00Z',
}

export function jsonResponse(status, body) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Route fetch calls by "METHOD path" to handler functions returning Responses. */
export function mockApi(handlers) {
  const calls = []
  const fetchMock = vi.fn(async (url, init = {}) => {
    const method = init.method ?? 'GET'
    const path = new URL(url, 'http://localhost').pathname
    calls.push({ method, path, init })
    const handler = handlers[`${method} ${path}`]
    if (!handler) return jsonResponse(404, { error: { code: 'not_found', message: 'Not found' } })
    return handler(init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

export function renderRoute(path) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false, staleTime: 0 } })
  const result = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...result, router, queryClient }
}
