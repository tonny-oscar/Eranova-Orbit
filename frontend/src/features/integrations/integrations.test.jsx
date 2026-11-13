import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const OPS = {
  ...ME,
  permissions: ['integration.read', 'integration.manage', 'integration.update', 'product.read'],
}
const PROVIDERS = [
  {
    provider: 'product_api',
    label: 'Eranova product API',
    description: 'Connects a live product.',
    capabilities: ['health_check'],
    config_fields: [
      { name: 'base_url', label: 'Product API base URL', required: true, help: '', kind: 'url' },
    ],
    secret_required: true,
    secret_help: 'Set INTEGRATION_* on the server.',
    supports_webhooks: true,
  },
]
const CONNECTION = {
  id: 'c1',
  provider: 'product_api',
  provider_label: 'Eranova product API',
  name: 'CRM production',
  product: { id: 'p1', name: 'Eranova CRM' },
  config: { base_url: 'https://crm.example.com' },
  secret_ref: 'INTEGRATION_CRM_KEY',
  webhook_secret_ref: null,
  capabilities: ['health_check'],
  status: 'active',
  sync_interval_minutes: 60,
  last_sync_at: '2026-11-13T08:00:00Z',
  last_success_at: null,
  last_error: 'The service rejected the credentials (HTTP 401).',
  is_stale: true,
  webhook_url: 'http://localhost/api/v1/webhooks/product_api/c1',
  can_manage: true,
}

describe('Integrations', () => {
  it('shows failing connections honestly', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, OPS),
      'GET /api/v1/integrations/providers': () => jsonResponse(200, PROVIDERS),
      'GET /api/v1/integrations': () => jsonResponse(200, [CONNECTION]),
    })
    renderRoute('/app/integrations')
    expect(await screen.findByText('CRM production')).toBeInTheDocument()
    expect(screen.getByText('Failing')).toBeInTheDocument()
    expect(screen.getByText('No successful sync yet')).toBeInTheDocument()
  })

  it('creates a connection with a secret reference, not a secret', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, OPS),
      'GET /api/v1/integrations/providers': () => jsonResponse(200, PROVIDERS),
      'GET /api/v1/integrations': () => jsonResponse(200, []),
      'GET /api/v1/products': () =>
        jsonResponse(200, { items: [], total: 0, limit: 100, offset: 0 }),
      'POST /api/v1/integrations': () => jsonResponse(201, CONNECTION),
      'GET /api/v1/integrations/c1': () => jsonResponse(200, CONNECTION),
      'GET /api/v1/integrations/c1/runs': () => jsonResponse(200, []),
    })
    renderRoute('/app/integrations')
    await userEvent.click(await screen.findByRole('button', { name: /connect a system/i }))
    await userEvent.type(screen.getByLabelText('Connection name'), 'CRM production')
    await userEvent.type(screen.getByLabelText('Product API base URL'), 'https://crm.example.com')
    await userEvent.type(screen.getByLabelText('Credential variable'), 'integration_crm_key')
    await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = JSON.parse(calls.find((c) => c.method === 'POST').init.body)
    expect(body).toMatchObject({
      provider: 'product_api',
      secret_ref: 'INTEGRATION_CRM_KEY',
      config: { base_url: 'https://crm.example.com' },
    })
    expect(await screen.findByRole('heading', { name: 'CRM production' })).toBeInTheDocument()
  })

  it('reports a failed connection test', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, OPS),
      'GET /api/v1/integrations/providers': () => jsonResponse(200, PROVIDERS),
      'GET /api/v1/integrations/c1': () => jsonResponse(200, CONNECTION),
      'GET /api/v1/integrations/c1/runs': () => jsonResponse(200, []),
      'POST /api/v1/integrations/c1/test': () =>
        jsonResponse(200, {
          ok: false,
          message: 'Server variable INTEGRATION_CRM_KEY is not set.',
          details: {},
        }),
    })
    renderRoute('/app/integrations/c1')
    await userEvent.click(await screen.findByRole('button', { name: /test connection/i }))
    expect(await screen.findByText('Connection failed')).toBeInTheDocument()
    expect(screen.getByText(/INTEGRATION_CRM_KEY is not set/)).toBeInTheDocument()
  })

  it('shows uptime and certificate state on the monitoring board', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, OPS),
      'GET /api/v1/monitoring/overview': () =>
        jsonResponse(200, {
          integrations: [
            {
              ...CONNECTION,
              provider: 'http_monitor',
              last_error: null,
              last_success_at: '2026-11-13T08:00:00Z',
              stale: false,
            },
          ],
          monitors: [
            {
              id: 'c1',
              name: 'CRM uptime',
              product: null,
              url: 'https://crm.example.com',
              latest: {
                data: { up: false, status: 503, latency_ms: 120, certificate_expires_at: null },
              },
              uptime_percent: 97.9,
              checks: 48,
            },
          ],
          deployments: [],
        }),
    })
    renderRoute('/app/monitoring')
    expect(await screen.findByText('Down (503)')).toBeInTheDocument()
    expect(screen.getByText('97.9% of 48 checks')).toBeInTheDocument()
  })

  it('labels analytics with their source and never invents numbers', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, OPS),
      'GET /api/v1/analytics/overview': () =>
        jsonResponse(200, [
          {
            product: { id: 'p1', name: 'ShulePoa' },
            traffic: null,
            traffic_freshness: null,
            product_metrics: { active_schools: 12 },
            product_metrics_freshness: {
              source: 'ShulePoa API',
              last_success_at: '2026-11-13T08:00:00Z',
              stale: false,
            },
          },
          {
            product: { id: 'p2', name: 'Idea' },
            traffic: null,
            traffic_freshness: null,
            product_metrics: null,
            product_metrics_freshness: null,
          },
        ]),
    })
    renderRoute('/app/analytics')
    expect(await screen.findByText('active schools')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText(/Source: ShulePoa API/)).toBeInTheDocument()
    expect(screen.getByText(/No analytics source connected/)).toBeInTheDocument()
  })
})
