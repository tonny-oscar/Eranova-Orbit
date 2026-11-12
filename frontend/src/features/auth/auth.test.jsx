import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'
import { safeNextPath } from './redirects'

const unauthenticated = () =>
  jsonResponse(401, { error: { code: 'not_authenticated', message: 'Sign in to continue.' } })

const READY = () =>
  jsonResponse(200, { status: 'ready', environment: 'test', checks: { database: 'ok' } })

describe('authentication flow', () => {
  it('redirects unauthenticated visitors from the app to sign-in, keeping the target', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated })
    const { router } = renderRoute('/app/settings/profile')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe(
      `?next=${encodeURIComponent('/app/settings/profile')}`,
    )
  })

  it('validates the form before calling the API', async () => {
    const calls = mockApi({ 'GET /api/v1/auth/me': unauthenticated })
    renderRoute('/login')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(calls.some((c) => c.path === '/api/v1/auth/login')).toBe(false)
  })

  it('shows the server message when credentials are rejected', async () => {
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'POST /api/v1/auth/login': () =>
        jsonResponse(401, {
          error: { code: 'invalid_credentials', message: 'Invalid email or password.' },
        }),
    })
    renderRoute('/login')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Email'), 'ada@eranova.co.ke')
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
  })

  it('signs in, lands on the requested page and sends credentials with the request', async () => {
    let signedIn = false
    const calls = mockApi({
      'GET /api/v1/auth/me': () => (signedIn ? jsonResponse(200, ME) : unauthenticated()),
      'POST /api/v1/auth/login': () => {
        signedIn = true
        return jsonResponse(200, ME)
      },
      'GET /ready': READY,
    })
    const { router } = renderRoute('/login?next=%2Fapp')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Email'), 'ada@eranova.co.ke')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: /Ada$/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app')
    const loginCall = calls.find((c) => c.path === '/api/v1/auth/login')
    expect(loginCall.init.credentials).toBe('include')
    expect(JSON.parse(loginCall.init.body)).toEqual({
      email: 'ada@eranova.co.ke',
      password: 'correct-horse-battery',
    })
  })

  it('signs out with the CSRF token and returns to sign-in', async () => {
    let signedIn = true
    const calls = mockApi({
      'GET /api/v1/auth/me': () => (signedIn ? jsonResponse(200, ME) : unauthenticated()),
      'POST /api/v1/auth/logout': () => {
        signedIn = false
        return new Response(null, { status: 204 })
      },
      'GET /ready': READY,
    })
    const { router } = renderRoute('/app')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /sign out/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    const logoutCall = calls.find((c) => c.path === '/api/v1/auth/logout')
    expect(logoutCall.init.headers['X-CSRF-Token']).toBe('csrf-test-token')
  })
})

describe('safeNextPath', () => {
  it.each([
    [null, '/app'],
    ['/app/settings/profile', '/app/settings/profile'],
    ['https://evil.example', '/app'],
    ['//evil.example', '/app'],
    ['/login', '/app'],
  ])('maps %s to %s', (input, expected) => {
    expect(safeNextPath(input)).toBe(expected)
  })
})
