import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, mockApi, renderRoute } from '../../../tests/utils'

const PRODUCT = {
  name: 'ShulePoa',
  slug: 'shulepoa',
  category: 'Education',
  tagline: 'School management',
  description: 'Manage fees and records.',
  lifecycle_status: 'live',
  logo_url: null,
  website_url: 'https://shulepoa.example',
  docs_url: null,
  status_page_url: null,
  support_email: null,
  features: [{ title: 'Fee tracking', description: 'Record payments.' }],
  pricing: [{ name: 'Starter', amount: '1500.00', currency: 'KES', interval: 'monthly' }],
}
const SITE = {
  company_name: 'Eranova',
  published_pages: [],
  categories: ['Education'],
  privacy_notice_version: 'v1',
}
const notFound = () =>
  jsonResponse(404, { error: { code: 'not_found', message: 'Page not found.' } })

describe('public marketplace', () => {
  it('lists published products in the catalogue', async () => {
    mockApi({
      'GET /api/v1/public/site': () => jsonResponse(200, SITE),
      'GET /api/v1/public/products': () => jsonResponse(200, [PRODUCT]),
    })
    renderRoute('/products')

    expect(await screen.findByText('ShulePoa')).toBeInTheDocument()
    expect(screen.getByText('School management')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Education' })).toBeInTheDocument()
  })

  it('shows a product page with features, pricing and product-specific calls to action', async () => {
    mockApi({ 'GET /api/v1/public/products/shulepoa': () => jsonResponse(200, PRODUCT) })
    renderRoute('/products/shulepoa')

    expect(await screen.findByRole('heading', { name: 'ShulePoa' })).toBeInTheDocument()
    expect(screen.getByText('Fee tracking')).toBeInTheDocument()
    expect(screen.getByText(/KES 1,500/)).toBeInTheDocument()
    const demoLinks = screen.getAllByRole('link', { name: 'Request a demo' })
    expect(demoLinks.map((link) => link.getAttribute('href'))).toContain('/demo?product=shulepoa')
  })

  it('shows not-found for unpublished products', async () => {
    mockApi({ 'GET /api/v1/public/products/secret': notFound })
    renderRoute('/products/secret')
    expect(await screen.findByRole('heading', { name: 'Product not found' })).toBeInTheDocument()
  })

  it('shows an honest placeholder for unpublished content pages', async () => {
    mockApi({ 'GET /api/v1/public/pages/careers': notFound })
    renderRoute('/careers')
    expect(await screen.findByText('This page is being prepared.')).toBeInTheDocument()
  })

  it('renders published content as plain text', async () => {
    mockApi({
      'GET /api/v1/public/pages/about': () =>
        jsonResponse(200, {
          slug: 'about',
          title: 'About Eranova',
          summary: 'Who we are',
          sections: [{ heading: 'Mission', body: '<script>alert(1)</script>' }],
          seo_description: '',
          published_at: '2026-11-13T08:00:00Z',
        }),
    })
    renderRoute('/about')
    expect(await screen.findByRole('heading', { name: 'About Eranova' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Mission' })).toBeInTheDocument()
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument()
    expect(document.querySelector('script[data-test]')).toBeNull()
  })

  it('requires consent and sends a complete enquiry with attribution', async () => {
    sessionStorage.setItem(
      'orbit.attribution',
      JSON.stringify({ utm_source: 'google', landing_page: '/' }),
    )
    const calls = mockApi({
      'GET /api/v1/public/products': () => jsonResponse(200, [PRODUCT]),
      'GET /api/v1/public/pages/contact': notFound,
      'POST /api/v1/public/enquiries': () =>
        jsonResponse(202, {
          status: 'received',
          message: 'Thank you. Our team will get back to you.',
        }),
    })
    renderRoute('/contact?product=shulepoa')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Full name'), 'Wanjiku Mwangi')
    await user.type(screen.getByLabelText('Email'), 'wanjiku@school.example')
    await user.type(screen.getByLabelText('How can we help?'), 'We want a quote for our school.')
    await user.click(screen.getByRole('button', { name: 'Send message' }))
    expect(
      await screen.findByText('Please accept the privacy notice to continue.'),
    ).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)

    await user.click(screen.getByRole('checkbox', { name: /privacy notice/ }))
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText(/we received your message/)).toBeInTheDocument()
    const body = JSON.parse(calls.find((c) => c.method === 'POST').init.body)
    expect(body).toMatchObject({
      type: 'contact',
      full_name: 'Wanjiku Mwangi',
      product_slug: 'shulepoa',
      consent_privacy: true,
      consent_marketing: false,
      website: '',
      attribution: { utm_source: 'google', landing_page: '/' },
    })
    expect(typeof body.elapsed_ms).toBe('number')
    sessionStorage.clear()
  })

  it('shows rate-limit errors from the API', async () => {
    mockApi({
      'GET /api/v1/public/products': () => jsonResponse(200, []),
      'POST /api/v1/public/enquiries': () =>
        jsonResponse(429, {
          error: { code: 'rate_limited', message: 'Too many enquiries. Please try again later.' },
        }),
    })
    renderRoute('/demo')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Full name'), 'Visitor')
    await user.type(screen.getByLabelText('Email'), 'v@example.com')
    await user.click(screen.getByRole('checkbox', { name: /privacy notice/ }))
    await user.click(screen.getByRole('button', { name: 'Request demo' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Too many enquiries'))
  })
})
