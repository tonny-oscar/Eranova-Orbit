import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const ADMIN = {
  ...ME,
  permissions: [
    'user.read',
    'user.create',
    'user.update',
    'user.manage',
    'role.read',
    'role.create',
    'role.update',
    'role.manage',
    'document.read',
  ],
}

const USER = {
  id: 'u2',
  email: 'dev@eranova.co.ke',
  full_name: 'Dev Person',
  status: 'active',
  last_login_at: null,
  must_change_password: false,
}

const page = (items) => jsonResponse(200, { items, total: items.length, limit: 25, offset: 0 })

describe('user administration', () => {
  it('creates a user and shows the temporary password once', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/users': () => page([{ ...USER, role_names: ['Developer'] }]),
      'POST /api/v1/users': () =>
        jsonResponse(201, {
          user: { ...USER, id: 'u3', email: 'new@eranova.co.ke', must_change_password: true },
          temporary_password: 'Tmp0rary-Pass123',
        }),
    })
    renderRoute('/app/settings/users')
    const user = userEvent.setup()

    expect(await screen.findByText('Developer')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /add user/i }))
    await user.type(screen.getByLabelText('Full name'), 'New Hire')
    await user.type(screen.getByLabelText('Work email'), 'new@eranova.co.ke')
    await user.click(screen.getByRole('button', { name: 'Create user' }))

    expect(await screen.findByText('Tmp0rary-Pass123')).toBeInTheDocument()
    expect(screen.getByText(/shown only once/)).toBeInTheDocument()
    const body = JSON.parse(calls.find((c) => c.method === 'POST').init.body)
    expect(body).toEqual({ full_name: 'New Hire', email: 'new@eranova.co.ke' })
  })

  it('requires confirmation before disabling an account', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/users/u2': () =>
        jsonResponse(200, { ...USER, roles: [], can_update: true, can_manage: true }),
      'GET /api/v1/roles': () => jsonResponse(200, []),
      'PATCH /api/v1/users/u2': () =>
        jsonResponse(200, {
          ...USER,
          status: 'disabled',
          roles: [],
          can_update: true,
          can_manage: true,
        }),
    })
    renderRoute('/app/settings/users/u2')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Disable account' }))
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Confirm disable' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PATCH').init.body)).toEqual({
      status: 'disabled',
    })
  })

  it('does not offer role changes on your own account', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      [`GET /api/v1/users/${ME.user.id}`]: () =>
        jsonResponse(200, {
          ...ME.user,
          roles: [
            {
              id: 'a1',
              role_id: 'r1',
              role_slug: 'developer',
              role_name: 'Developer',
              scope_type: 'company',
              scope_id: null,
              granted_by_user_id: null,
              created_at: '2026-11-12T08:00:00Z',
            },
          ],
          can_update: true,
          can_manage: false,
        }),
    })
    renderRoute(`/app/settings/users/${ME.user.id}`)

    expect(await screen.findByText('Developer')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remove developer/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Assign role' })).not.toBeInTheDocument()
    expect(screen.getByText(/must be changed by another administrator/)).toBeInTheDocument()
  })
})

describe('role editor', () => {
  const CATALOGUE = [
    {
      key: 'document.read',
      resource: 'document',
      action: 'read',
      description: 'View documents',
      is_sensitive: false,
    },
    {
      key: 'invoice.approve',
      resource: 'invoice',
      action: 'approve',
      description: 'Approve invoices',
      is_sensitive: true,
    },
  ]

  it('only lets you grant permissions you hold', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/authz/permissions': () => jsonResponse(200, CATALOGUE),
      'POST /api/v1/roles': () =>
        jsonResponse(201, {
          id: 'r9',
          name: 'Docs',
          slug: 'docs',
          description: '',
          is_system: false,
          is_locked: false,
          permissions: ['document.read'],
          assignment_count: 0,
        }),
      'GET /api/v1/roles/r9': () =>
        jsonResponse(200, {
          id: 'r9',
          name: 'Docs',
          slug: 'docs',
          description: '',
          is_system: false,
          is_locked: false,
          permissions: ['document.read'],
          assignment_count: 0,
        }),
    })
    const { router } = renderRoute('/app/settings/roles/new')
    const user = userEvent.setup()

    const approve = await screen.findByRole('checkbox', { name: 'Approve invoices' })
    expect(approve).toBeDisabled()
    await user.type(screen.getByLabelText('Name'), 'Docs')
    await user.click(screen.getByRole('checkbox', { name: 'View documents' }))
    await user.click(screen.getByRole('button', { name: 'Create role' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/app/settings/roles/r9'))
    const body = JSON.parse(calls.find((c) => c.method === 'POST').init.body)
    expect(body).toEqual({ name: 'Docs', description: '', permissions: ['document.read'] })
  })

  it('shows locked roles read-only', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, ADMIN),
      'GET /api/v1/authz/permissions': () => jsonResponse(200, CATALOGUE),
      'GET /api/v1/roles/r1': () =>
        jsonResponse(200, {
          id: 'r1',
          name: 'Super Admin',
          slug: 'super_admin',
          description: '',
          is_system: true,
          is_locked: true,
          permissions: ['document.read', 'invoice.approve'],
          assignment_count: 1,
        }),
    })
    renderRoute('/app/settings/roles/r1')

    expect(await screen.findByText('This role is locked')).toBeInTheDocument()
    const table = screen.getByRole('table')
    for (const box of within(table).getAllByRole('checkbox')) expect(box).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument()
  })
})

describe('forced password change', () => {
  it('blocks the app until a temporary password is replaced', async () => {
    mockApi({
      'GET /api/v1/auth/me': () =>
        jsonResponse(200, { ...ME, user: { ...ME.user, must_change_password: true } }),
    })
    renderRoute('/app')

    expect(await screen.findByRole('heading', { name: 'Set your password' })).toBeInTheDocument()
    expect(screen.getByLabelText('Temporary password')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
  })
})
