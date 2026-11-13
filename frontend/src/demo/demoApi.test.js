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
    const launch = page.items.filter((p) => p.id !== 'p-sample')
    expect(launch).toHaveLength(5)
    expect(launch.every((p) => p.lifecycle_status === 'draft' && !p.details_confirmed)).toBe(true)
    expect(launch.every((p) => p.description === '' && p.pricing.length === 0)).toBe(true)
  })

  it('only exposes the clearly labelled sample product publicly', async () => {
    const products = await demoRequest('GET', '/api/v1/public/products')
    expect(products.map((p) => p.name)).toEqual(['Sample App (demo)'])
    expect(products[0]).not.toHaveProperty('owner')
  })

  it('turns a public enquiry into a lead', async () => {
    await demoRequest('POST', '/api/v1/public/enquiries', {
      body: {
        type: 'contact',
        full_name: 'Visitor',
        email: 'Visitor@Example.com',
        message: 'Hello there team',
        consent_privacy: true,
        consent_marketing: false,
        product_slug: 'sample-app',
        attribution: { utm_source: 'test' },
      },
    })
    const leads = await demoRequest('GET', '/api/v1/leads', { query: { q: 'visitor' } })
    expect(leads.items[0].email).toBe('visitor@example.com')
    expect(leads.items[0].product.name).toBe('Sample App (demo)')
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
