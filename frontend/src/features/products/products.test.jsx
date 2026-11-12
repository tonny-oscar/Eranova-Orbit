import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'
import { slugify } from './constants'

const ADMIN = {
  ...ME,
  permissions: ['product.read', 'product.create', 'product.update', 'product.manage', 'user.read'],
}

const PRODUCT = {
  id: 'p1',
  name: 'ShulePoa',
  slug: 'shulepoa',
  category: 'Education',
  tagline: null,
  lifecycle_status: 'draft',
  details_confirmed: false,
  website_url: null,
  logo_url: null,
  owner: null,
  updated_at: '2026-11-12T08:00:00Z',
}

const DETAIL = {
  ...PRODUCT,
  description: '',
  repository_url: null,
  deployment_ref: null,
  docs_url: null,
  status_page_url: null,
  support_email: null,
  analytics_source: null,
  analytics_property_id: null,
  launch_date: null,
  pricing: [],
  created_at: '2026-11-12T08:00:00Z',
  can_update: true,
  can_manage: true,
}

const page = (items) => jsonResponse(200, { items, total: items.length, limit: 25, offset: 0 })

describe('product registry', () => {
  it('lists products with status and confirmation badges', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/products': () => page([PRODUCT]),
    })
    renderRoute('/app/products')

    const row = (await screen.findByRole('link', { name: 'ShulePoa' })).closest('tr')
    expect(within(row).getByText('Draft')).toBeInTheDocument()
    expect(within(row).getByText('Awaiting confirmation')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /register product/i })).toBeInTheDocument()
  })

  it('hides registration from users without product.create', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, { ...ME, permissions: ['product.read'] }),
      'GET /api/v1/products': () => page([]),
    })
    renderRoute('/app/products')

    expect(await screen.findByText('No products registered yet')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /register product/i })).not.toBeInTheDocument()
  })

  it('registers a product with a generated slug and normalised payload', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/users': () => page([]),
      'POST /api/v1/products': () => jsonResponse(201, { ...DETAIL, id: 'new1', name: 'Menu Poa' }),
      'GET /api/v1/products/new1': () =>
        jsonResponse(200, { ...DETAIL, id: 'new1', name: 'Menu Poa' }),
      'GET /api/v1/products/new1/status-history': () => jsonResponse(200, []),
      'GET /api/v1/products/new1/members': () => jsonResponse(200, []),
    })
    const { router } = renderRoute('/app/products/new')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Name'), 'Menu Poa')
    expect(screen.getByLabelText('Slug')).toHaveValue('menu-poa')
    await user.type(screen.getByLabelText('Public website'), 'not a url')
    await user.click(screen.getByRole('button', { name: 'Register product' }))
    expect(await screen.findByText('Enter a full http(s) URL.')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Public website'))
    await user.type(screen.getByLabelText('Public website'), 'https://menupoa.example')
    await user.click(screen.getByRole('button', { name: 'Register product' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/app/products/new1'))
    const body = JSON.parse(
      calls.find((c) => c.path === '/api/v1/products' && c.method === 'POST').init.body,
    )
    expect(body).toMatchObject({
      name: 'Menu Poa',
      slug: 'menu-poa',
      lifecycle_status: 'draft',
      website_url: 'https://menupoa.example',
      category: null,
      owner_user_id: null,
      pricing: [],
      details_confirmed: false,
    })
  })

  it('shows server conflicts on the matching field', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/users': () => page([]),
      'POST /api/v1/products': () =>
        jsonResponse(409, {
          error: {
            code: 'product_slug_taken',
            message: 'Another product already uses this slug.',
            details: [{ field: 'slug', message: 'This slug is already in use.' }],
          },
        }),
    })
    renderRoute('/app/products/new')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Name'), 'ShulePoa')
    await user.click(screen.getByRole('button', { name: 'Register product' }))

    expect(await screen.findByText('This slug is already in use.')).toBeInTheDocument()
  })

  it('hides edit and lifecycle controls when the user cannot update', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, { ...ME, permissions: ['product.read'] }),
      'GET /api/v1/products/p1': () =>
        jsonResponse(200, { ...DETAIL, can_update: false, can_manage: false }),
      'GET /api/v1/products/p1/status-history': () => jsonResponse(200, []),
      'GET /api/v1/products/p1/members': () => jsonResponse(200, []),
    })
    renderRoute('/app/products/p1')

    expect(await screen.findByRole('heading', { name: 'ShulePoa' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Update status' })).not.toBeInTheDocument()
  })

  it('changes lifecycle status', async () => {
    let status = 'draft'
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/users': () => page([]),
      'GET /api/v1/products/p1': () => jsonResponse(200, { ...DETAIL, lifecycle_status: status }),
      'POST /api/v1/products/p1/status': () => {
        status = 'live'
        return jsonResponse(200, { ...DETAIL, lifecycle_status: 'live' })
      },
      'GET /api/v1/products/p1/status-history': () => jsonResponse(200, []),
      'GET /api/v1/products/p1/members': () => jsonResponse(200, []),
    })
    renderRoute('/app/products/p1')
    const user = userEvent.setup()

    await user.selectOptions(await screen.findByLabelText('New status'), 'live')
    await user.type(screen.getByLabelText('Reason (optional)'), 'Launched')
    await user.click(screen.getByRole('button', { name: 'Update status' }))

    await waitFor(() =>
      expect(calls.some((c) => c.path === '/api/v1/products/p1/status')).toBe(true),
    )
    const body = JSON.parse(calls.find((c) => c.path === '/api/v1/products/p1/status').init.body)
    expect(body).toEqual({ status: 'live', reason: 'Launched' })
    expect(await screen.findAllByText('Live')).not.toHaveLength(0)
  })
})

describe('slugify', () => {
  it.each([
    ['Menu Poa', 'menu-poa'],
    ['  OTP--Guard! ', 'otp-guard'],
    ['Shule Poa 2.0', 'shule-poa-20'],
  ])('%s -> %s', (input, expected) => {
    expect(slugify(input)).toBe(expected)
  })
})
