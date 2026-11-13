import { beforeEach, describe, expect, it } from 'vitest'
import { demoRequest, resetDemoState } from './demoApi'

beforeEach(() => resetDemoState())

describe('demo preview API', () => {
  it('signs you in as a demo Super Admin with every permission', async () => {
    const me = await demoRequest('GET', '/api/v1/auth/me')
    expect(me.user.email).toBe('admin@demo.local')
    expect(me.permissions).toContain('role.manage')
    expect(me.company.name).toMatch(/demo/)
  })

  it('logs out and back in with any credentials', async () => {
    await demoRequest('POST', '/api/v1/auth/logout')
    await expect(demoRequest('GET', '/api/v1/auth/me')).rejects.toMatchObject({ status: 401 })
    await demoRequest('POST', '/api/v1/auth/login', { body: { email: 'x', password: 'y' } })
    expect((await demoRequest('GET', '/api/v1/auth/me')).user.id).toBe('u-admin')
  })

  it('serves launch products as unconfirmed drafts without invented details', async () => {
    const page = await demoRequest('GET', '/api/v1/products')
    expect(page.total).toBe(5)
    expect(page.items.every((p) => p.lifecycle_status === 'draft' && !p.details_confirmed)).toBe(
      true,
    )
    expect(page.items.every((p) => p.description === '' && p.pricing.length === 0)).toBe(true)
  })

  it('keeps changes in memory and records them in the audit list', async () => {
    await demoRequest('POST', '/api/v1/products/p-shulepoa/status', {
      body: { status: 'live', reason: 'Demo' },
    })
    const product = await demoRequest('GET', '/api/v1/products/p-shulepoa')
    expect(product.lifecycle_status).toBe('live')
    const audit = await demoRequest('GET', '/api/v1/audit-logs')
    expect(audit.items[0].action).toBe('product.status.change')
  })

  it('labels the summary source as sample data', async () => {
    const summary = await demoRequest('GET', '/api/v1/dashboard/summary')
    expect(summary.source).toMatch(/sample data, not live/)
  })

  it('returns 404 for unknown routes', async () => {
    await expect(demoRequest('GET', '/api/v1/nope')).rejects.toMatchObject({ status: 404 })
  })
})
