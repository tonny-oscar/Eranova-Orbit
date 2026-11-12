import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const HR = { ...ME, permissions: ['employee.read', 'employee.update'] }
const DEPARTMENTS = [
  { id: 'd1', name: 'Engineering', description: '', head: null, member_count: 1, created_at: '' },
]
const EMPLOYEE = {
  user: { id: 'u2', full_name: 'Dev Person', email: 'dev@eranova.co.ke' },
  status: 'active',
  department: null,
  job_title: null,
  manager: null,
  employment_type: null,
  start_date: null,
  has_profile: false,
  can_update: true,
}
const page = (items) => jsonResponse(200, { items, total: items.length, limit: 25, offset: 0 })

describe('team', () => {
  it('lists people and flags missing profiles', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, HR),
      'GET /api/v1/departments': () => jsonResponse(200, DEPARTMENTS),
      'GET /api/v1/employees': () => page([EMPLOYEE]),
    })
    renderRoute('/app/team')

    expect(await screen.findByRole('link', { name: 'Dev Person' })).toBeInTheDocument()
    expect(screen.getByText('Profile not set up')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Engineering' })).toBeInTheDocument()
  })

  it('saves a work profile with nulls for empty fields', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, HR),
      'GET /api/v1/departments': () => jsonResponse(200, DEPARTMENTS),
      'GET /api/v1/employees': () => page([EMPLOYEE]),
      'GET /api/v1/employees/u2': () => jsonResponse(200, EMPLOYEE),
      'PUT /api/v1/employees/u2': () =>
        jsonResponse(200, { ...EMPLOYEE, has_profile: true, job_title: 'Developer' }),
    })
    renderRoute('/app/team/u2')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Job title'), 'Developer')
    await user.selectOptions(screen.getByLabelText('Primary department'), 'd1')
    await user.click(screen.getByRole('button', { name: 'Save profile' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PUT').init.body)).toEqual({
      department_id: 'd1',
      job_title: 'Developer',
      manager_user_id: null,
      employment_type: 'full_time',
      start_date: null,
    })
  })

  it('shows a read-only profile without update access', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, { ...ME, permissions: ['employee.read'] }),
      'GET /api/v1/employees/u2': () =>
        jsonResponse(200, { ...EMPLOYEE, can_update: false, job_title: 'Developer' }),
    })
    renderRoute('/app/team/u2')

    expect(await screen.findByText('Developer')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save profile' })).not.toBeInTheDocument()
  })

  it('only offers department creation to managers of the structure', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, HR),
      'GET /api/v1/departments': () => jsonResponse(200, DEPARTMENTS),
    })
    renderRoute('/app/team/departments')

    expect(await screen.findByRole('heading', { name: 'Engineering' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /new department/i })).not.toBeInTheDocument()
  })
})
