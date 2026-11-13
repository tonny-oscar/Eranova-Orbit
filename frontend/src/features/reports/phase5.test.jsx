import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const STAFF = {
  ...ME,
  permissions: [
    'campaign.read',
    'campaign.create',
    'campaign.update',
    'ticket.read',
    'ticket.update',
    'document.read',
    'document.create',
    'report.read',
    'lead.read',
  ],
}
const page = (items) => jsonResponse(200, { items, total: items.length, limit: 100, offset: 0 })

const CONTENT = {
  id: 'k1',
  title: 'Launch post',
  kind: 'social_caption',
  channel: 'facebook',
  body: 'Hello schools',
  status: 'approved',
  campaign: null,
  product: { id: 'p1', name: 'ShulePoa' },
  author: { id: 'u2', name: 'Mary' },
  approved_by: { id: 'u3', name: 'Ada' },
  approved_at: '2026-11-13T08:00:00Z',
  review_note: null,
  scheduled_for: null,
  published_at: null,
  published_url: null,
  publish_method: null,
  published_by: null,
  failure_reason: null,
  created_at: '2026-11-12T08:00:00Z',
  updated_at: '2026-11-13T08:00:00Z',
  allowed_actions: ['schedule', 'record_published', 'record_failed', 'reopen'],
  can_edit: false,
}

const TICKET = {
  id: 't1',
  number: 1001,
  reference: 'T-1001',
  subject: 'Cannot log in',
  status: 'open',
  priority: 'high',
  category: 'bug',
  channel: 'email',
  product: null,
  customer: null,
  requester_name: 'Head teacher',
  requester_email: 'head@school.example',
  assignee: null,
  first_response_at: null,
  resolved_at: null,
  closed_at: null,
  created_at: '2026-11-13T08:00:00Z',
  updated_at: '2026-11-13T08:00:00Z',
  description: 'Error 500 on login',
  resolution: null,
  messages: [],
  events: [
    {
      id: 'e1',
      kind: 'created',
      from_value: null,
      to_value: 'new',
      actor: null,
      created_at: '2026-11-13T08:00:00Z',
    },
  ],
  allowed_statuses: ['assigned', 'in_progress', 'waiting_customer', 'resolved', 'closed'],
  can_update: true,
}

describe('Phase 5 screens', () => {
  it('records a publication only with a link to the live post', async () => {
    let current = CONTENT
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/marketing/content/k1': () => jsonResponse(200, current),
      'POST /api/v1/marketing/content/k1/actions': () => {
        current = {
          ...CONTENT,
          status: 'published',
          publish_method: 'manual',
          published_by: { id: 'u1', name: 'Ada Lovelace' },
          published_at: '2026-11-13T09:00:00Z',
          published_url: 'https://facebook.com/p/1',
          allowed_actions: [],
        }
        return jsonResponse(200, current)
      },
    })
    renderRoute('/app/marketing/content/k1')
    expect(await screen.findByText(/Locked after approval/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Record publication' }))
    const submit = screen.getAllByRole('button', { name: 'Record publication' }).at(-1)
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Link to the live post'), 'https://facebook.com/p/1')
    await userEvent.click(submit)
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'POST').init.body)).toEqual({
      action: 'record_published',
      published_url: 'https://facebook.com/p/1',
    })
    expect(await screen.findByText('Manually confirmed by Ada Lovelace')).toBeInTheDocument()
  })

  it('requires a resolution before resolving a ticket', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/support/tickets/t1': () => jsonResponse(200, TICKET),
      'POST /api/v1/support/tickets/t1/transition': () =>
        jsonResponse(200, {
          ...TICKET,
          status: 'resolved',
          resolution: 'Reset sessions',
          allowed_statuses: ['closed', 'open'],
        }),
    })
    renderRoute('/app/support/t1')
    expect(await screen.findByText('Error 500 on login')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Move to'), 'resolved')
    const update = screen.getByRole('button', { name: 'Update status' })
    expect(update).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Resolution'), 'Reset sessions')
    await userEvent.click(update)
    await waitFor(() => expect(calls.some((c) => c.path.endsWith('/transition'))).toBe(true))
    expect(JSON.parse(calls.find((c) => c.path.endsWith('/transition')).init.body)).toEqual({
      status: 'resolved',
      resolution: 'Reset sessions',
    })
  })

  it('uploads documents as multipart form data', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/documents': () => page([]),
      'POST /api/v1/documents': () =>
        jsonResponse(400, {
          error: { code: 'file_type', message: 'This file type is not accepted.' },
        }),
    })
    renderRoute('/app/documents')
    await userEvent.click(await screen.findByRole('button', { name: /upload document/i }))
    const file = new File(['%PDF-1.7'], 'Leave policy.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByLabelText(/File/), file)
    expect(screen.getByLabelText('Title')).toHaveValue('Leave policy')
    await userEvent.click(screen.getByRole('button', { name: /^upload$/i }))
    expect(await screen.findByText('This file type is not accepted.')).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST')
    expect(post.init.body).toBeInstanceOf(FormData)
    expect(post.init.headers['Content-Type']).toBeUndefined()
    expect(post.init.body.get('title')).toBe('Leave policy')
  })

  it('renders report sections with their period and empty states', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, STAFF),
      'GET /api/v1/reports/sales': () =>
        jsonResponse(200, {
          key: 'sales',
          title: 'Sales',
          period: { start: '2026-10-15', end: '2026-11-13' },
          generated_at: '2026-11-13T09:00:00Z',
          sections: [
            {
              title: 'Sales',
              metrics: [
                { label: 'New leads', value: 3, unit: null },
                { label: 'Conversion rate', value: null, unit: '%' },
              ],
              columns: [],
              rows: [],
              note: null,
            },
            {
              title: 'Overdue follow-ups',
              metrics: [],
              columns: ['Lead', 'Owner'],
              rows: [],
              note: null,
            },
          ],
        }),
    })
    renderRoute('/app/reports/sales')
    expect(await screen.findByText('New leads')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText('No records in this period.')).toBeInTheDocument()
    expect(screen.getByText(/Period 2026-10-15 to 2026-11-13/)).toBeInTheDocument()
  })
})
