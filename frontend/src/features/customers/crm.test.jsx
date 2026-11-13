import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const CRM = {
  ...ME,
  permissions: [
    'lead.read',
    'lead.update',
    'lead.create',
    'customer.read',
    'customer.create',
    'customer.update',
    'lead.export',
  ],
}
const STAGES = [
  { id: 's1', key: 'new', name: 'New', position: 0, is_won: false, is_lost: false },
  { id: 's2', key: 'converted', name: 'Converted', position: 1, is_won: true, is_lost: false },
]
const LEAD = {
  id: 'l1',
  full_name: 'Amina Otieno',
  organization: 'Lakeview Hotel',
  email: 'amina@hotel.example',
  phone: null,
  product: null,
  source: 'manual',
  status: 'new',
  priority: 'medium',
  owner: null,
  next_follow_up: null,
  last_enquiry_at: null,
  created_at: '2026-11-13T08:00:00Z',
}
const DETAIL = {
  ...LEAD,
  notes: '',
  expected_value: null,
  currency: null,
  marketing_consent: false,
  enquiries: [],
  activities: [],
  converted_customer: null,
  converted_at: null,
  can_update: true,
  can_convert: true,
}
const page = (items) => jsonResponse(200, { items, total: items.length, limit: 25, offset: 0 })

describe('CRM', () => {
  it('shows the pipeline board grouped by stage', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, CRM),
      'GET /api/v1/crm/stages': () => jsonResponse(200, STAGES),
      'GET /api/v1/products': () => page([]),
      'GET /api/v1/leads': () => page([LEAD]),
    })
    renderRoute('/app/leads')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /pipeline board/i }))
    const column = await screen.findByRole('region', { name: 'New' })
    expect(column).toHaveTextContent('Amina Otieno')
    expect(screen.getByRole('link', { name: /export csv/i })).toHaveAttribute(
      'href',
      '/api/v1/leads/export.csv',
    )
  })

  it('logs an activity and converts the lead', async () => {
    let converted = false
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, CRM),
      'GET /api/v1/crm/stages': () => jsonResponse(200, STAGES),
      'GET /api/v1/leads/l1': () =>
        jsonResponse(
          200,
          converted
            ? {
                ...DETAIL,
                status: 'converted',
                can_convert: false,
                converted_customer: { id: 'c1', name: 'Lakeview Hotel' },
              }
            : DETAIL,
        ),
      'POST /api/v1/leads/l1/activities': () =>
        jsonResponse(201, {
          ...DETAIL,
          activities: [
            {
              id: 'a1',
              type: 'call',
              subject: 'Intro call',
              body: '',
              occurred_at: '2026-11-13T09:00:00Z',
              created_by: null,
            },
          ],
        }),
      'POST /api/v1/leads/l1/convert': () => {
        converted = true
        return jsonResponse(200, {
          ...DETAIL,
          status: 'converted',
          can_convert: false,
          converted_customer: { id: 'c1', name: 'Lakeview Hotel' },
        })
      },
    })
    renderRoute('/app/leads/l1')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Summary'), 'Intro call')
    await user.click(screen.getByRole('button', { name: 'Log activity' }))
    expect(await screen.findByText('Intro call')).toBeInTheDocument()

    expect(screen.getByLabelText('Customer name')).toHaveValue('Lakeview Hotel')
    await user.click(screen.getByRole('button', { name: 'Convert' }))
    expect(
      await screen.findByRole('link', { name: /Customer: Lakeview Hotel/ }),
    ).toBeInTheDocument()
    await waitFor(() => expect(calls.some((c) => c.path.endsWith('/convert'))).toBe(true))
  })

  it('lists customers with their products', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, CRM),
      'GET /api/v1/products': () => page([]),
      'GET /api/v1/customers': () =>
        page([
          {
            id: 'c1',
            name: 'Hill School',
            industry: 'Education',
            status: 'active',
            email: null,
            phone: null,
            account_manager: null,
            products: [{ id: 'p1', name: 'ShulePoa' }],
            next_renewal: '2027-01-31',
            created_at: '',
          },
        ]),
    })
    renderRoute('/app/customers')
    expect(await screen.findByRole('link', { name: 'Hill School' })).toBeInTheDocument()
    expect(screen.getByText('ShulePoa')).toBeInTheDocument()
    expect(screen.getByText('2027-01-31')).toBeInTheDocument()
  })
})
