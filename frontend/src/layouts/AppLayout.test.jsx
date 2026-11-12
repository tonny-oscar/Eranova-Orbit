import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../tests/utils'

const READY = () => jsonResponse(200, { status: 'ready', checks: { database: 'ok' } })

describe('command centre shell', () => {
  it('hides administration links the user has no permission for', async () => {
    mockApi({ 'GET /api/v1/auth/me': () => jsonResponse(200, ME), 'GET /ready': READY })
    renderRoute('/app')

    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Overview' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Settings' })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: 'Audit log' })).not.toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument()
  })

  it('shows administration links when permitted', async () => {
    const admin = { ...ME, permissions: ['role.read', 'audit_log.read'] }
    mockApi({ 'GET /api/v1/auth/me': () => jsonResponse(200, admin), 'GET /ready': READY })
    renderRoute('/app')

    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Audit log' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Roles' })).toBeInTheDocument()
  })

  it('shows an honest empty state instead of placeholder metrics', async () => {
    mockApi({ 'GET /api/v1/auth/me': () => jsonResponse(200, ME), 'GET /ready': READY })
    renderRoute('/app')

    expect(await screen.findByText('No business data connected yet')).toBeInTheDocument()
    expect(await screen.findByText('Operational')).toBeInTheDocument()
  })

  it('blocks a page the user lacks permission for even via direct URL', async () => {
    mockApi({ 'GET /api/v1/auth/me': () => jsonResponse(200, ME), 'GET /ready': READY })
    renderRoute('/app/settings/audit-log')

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument()
  })

  it('renders audit events for permitted users', async () => {
    const auditor = { ...ME, permissions: ['audit_log.read'] }
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, auditor),
      'GET /api/v1/audit-logs': () =>
        jsonResponse(200, {
          items: [
            {
              id: 'e1',
              created_at: '2026-11-12T08:00:00Z',
              actor_type: 'user',
              actor_user_id: '11111111-1111',
              action: 'auth.login.succeeded',
              resource_type: 'session',
              resource_id: 'abcdef123456',
              outcome: 'success',
              ip_address: '127.0.0.1',
              correlation_id: 'c1',
              details: {},
            },
          ],
          total: 1,
          limit: 25,
          offset: 0,
        }),
    })
    renderRoute('/app/settings/audit-log')

    expect(await screen.findByText('auth.login.succeeded')).toBeInTheDocument()
    expect(screen.getByText('1–1 of 1')).toBeInTheDocument()
  })

  it('shows an error state with a reference when the API fails', async () => {
    const auditor = { ...ME, permissions: ['audit_log.read'] }
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, auditor),
      'GET /api/v1/audit-logs': () =>
        jsonResponse(500, {
          error: {
            code: 'internal_error',
            message: 'An unexpected error occurred.',
            correlation_id: 'ref-123',
          },
        }),
    })
    renderRoute('/app/settings/audit-log')

    expect(await screen.findByText("Couldn't load audit events")).toBeInTheDocument()
    expect(screen.getByText('Reference: ref-123')).toBeInTheDocument()
  })
})
