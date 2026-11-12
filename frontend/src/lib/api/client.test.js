import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse } from '../../../tests/utils'
import { ApiError, apiRequest, setCsrfToken } from './client'

afterEach(() => setCsrfToken(null))

describe('apiRequest', () => {
  it('sends the CSRF token only on state-changing requests', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('tok')

    await apiRequest('/api/v1/x')
    await apiRequest('/api/v1/x', { method: 'POST', body: {} })

    expect(fetchMock.mock.calls[0][1].headers['X-CSRF-Token']).toBeUndefined()
    expect(fetchMock.mock.calls[1][1].headers['X-CSRF-Token']).toBe('tok')
  })

  it('parses the API error envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(403, {
          error: { code: 'permission_denied', message: 'Nope', details: [], correlation_id: 'cid' },
        }),
      ),
    )
    const error = await apiRequest('/api/v1/x').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 403,
      code: 'permission_denied',
      message: 'Nope',
      correlationId: 'cid',
    })
  })

  it('reports network failures without leaking internals', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))),
    )
    const error = await apiRequest('/api/v1/x').catch((e) => e)
    expect(error.code).toBe('network_error')
    expect(error.status).toBe(0)
  })

  it('builds query strings and skips empty values', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}))
    vi.stubGlobal('fetch', fetchMock)
    await apiRequest('/api/v1/audit-logs', { query: { limit: 25, offset: 0, action: '' } })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/audit-logs?limit=25&offset=0')
  })

  it('returns null for 204 responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 204 })),
    )
    expect(await apiRequest('/api/v1/x', { method: 'POST' })).toBeNull()
  })
})
