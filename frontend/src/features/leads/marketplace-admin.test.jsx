import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const STAFF = {
  ...ME,
  permissions: ['lead.read', 'lead.update', 'content.read', 'content.update', 'product.read'],
}

const LEAD = {
  id: 'l1',
  full_name: 'Wanjiku Mwangi',
  organization: 'Hill School',
  email: 'wanjiku@school.example',
  phone: null,
  product: { id: 'p1', name: 'ShulePoa' },
  source: 'website_demo',
  status: 'new',
  priority: 'medium',
  owner: null,
  next_follow_up: null,
  last_enquiry_at: '2026-11-13T08:00:00Z',
  created_at: '2026-11-13T08:00:00Z',
}

const page = (items) => jsonResponse(200, { items, total: items.length, limit: 25, offset: 0 })

describe('leads', () => {
  it('lists leads from website enquiries', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/products': () => page([]),
      'GET /api/v1/leads': () => page([LEAD]),
    })
    renderRoute('/app/leads')

    expect(await screen.findByRole('link', { name: 'Wanjiku Mwangi' })).toBeInTheDocument()
    expect(screen.getByText('Website demo request')).toBeInTheDocument()
  })

  it('shows enquiry history with consent and updates the lead', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/leads/l1': () =>
        jsonResponse(200, {
          ...LEAD,
          notes: '',
          expected_value: null,
          currency: null,
          marketing_consent: false,
          can_update: true,
          enquiries: [
            {
              id: 'q1',
              type: 'demo',
              message: 'Show us fee tracking',
              preferred_date: null,
              consent_privacy: true,
              consent_marketing: false,
              privacy_notice_version: '2026-11-draft',
              utm_source: 'google',
              utm_medium: 'cpc',
              utm_campaign: null,
              referrer: null,
              landing_page: '/products/shulepoa',
              created_at: '2026-11-13T08:00:00Z',
            },
          ],
        }),
      'PATCH /api/v1/leads/l1': () =>
        jsonResponse(200, {
          ...LEAD,
          status: 'contacted',
          notes: '',
          enquiries: [],
          can_update: true,
          marketing_consent: false,
        }),
    })
    renderRoute('/app/leads/l1')
    const user = userEvent.setup()

    expect(await screen.findByText('Show us fee tracking')).toBeInTheDocument()
    expect(screen.getByText(/privacy notice 2026-11-draft/)).toBeInTheDocument()
    expect(screen.getByText(/source google\/cpc/)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Status'), 'contacted')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PATCH').init.body)).toMatchObject({
      status: 'contacted',
      owner_user_id: null,
    })
  })
})

describe('website content', () => {
  const ADMIN_PAGE = {
    slug: 'about',
    label: 'About',
    draft: { title: 'About', summary: '', sections: [], seo_description: '' },
    published: null,
    published_at: null,
    has_unpublished_changes: false,
    updated_at: null,
    can_edit: true,
    can_publish: false,
  }

  it('saves drafts and explains that publishing needs approval', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/content/pages/about': () => jsonResponse(200, ADMIN_PAGE),
      'PUT /api/v1/content/pages/about': () =>
        jsonResponse(200, { ...ADMIN_PAGE, has_unpublished_changes: true, updated_at: 'x' }),
    })
    renderRoute('/app/website/about')
    const user = userEvent.setup()

    expect(await screen.findByText(/Publishing requires approval rights/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /add section/i }))
    await user.type(screen.getByLabelText('Heading'), 'Mission')
    await user.type(screen.getByLabelText('Text'), 'Build useful software.')
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PUT').init.body)).toEqual({
      title: 'About',
      summary: '',
      seo_description: '',
      sections: [{ heading: 'Mission', body: 'Build useful software.' }],
    })
  })
})
