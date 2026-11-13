import { beforeEach, describe, expect, it } from 'vitest'
import { demoRequest, resetDemoState } from './demoApi'

describe('demo preview API', () => {
  beforeEach(() => resetDemoState())

  it('serves every module with sample data', async () => {
    for (const path of [
      '/api/v1/crm/stages',
      '/api/v1/customers',
      '/api/v1/projects',
      '/api/v1/tasks',
      '/api/v1/me/work',
      '/api/v1/notifications',
      '/api/v1/integrations',
      '/api/v1/monitoring/overview',
      '/api/v1/marketing/campaigns',
      '/api/v1/support/tickets',
      '/api/v1/documents',
      '/api/v1/reports',
      '/api/v1/reports/executive',
      '/api/v1/nova/status',
    ]) {
      await expect(demoRequest('GET', path)).resolves.toBeTruthy()
    }
    const leads = await demoRequest('GET', '/api/v1/leads')
    expect(leads.total).toBeGreaterThan(1)
  })

  it('lets NOVA learn about you and forget on request', async () => {
    const { id } = await demoRequest('POST', '/api/v1/nova/conversations')
    const said = (content) =>
      demoRequest('POST', `/api/v1/nova/conversations/${id}/messages`, { body: { content } })

    const learned = await said('I prefer short answers')
    expect(learned.message.content).toMatch(/Noted for next time/)
    await said('remember that I manage ShulePoa')
    const memories = await demoRequest('GET', '/api/v1/nova/memories')
    expect(memories.map((m) => m.source).sort()).toEqual(['learned', 'told'])

    await expect(said('remember my password is abc')).resolves.toMatchObject({
      executions: [{ status: 'failed' }],
    })
    const recall = await said('what do you know about me?')
    expect(recall.message.content).toContain('I manage ShulePoa')

    await demoRequest('PUT', '/api/v1/nova/profile', {
      body: {
        preferred_name: 'Tonny',
        response_style: 'concise',
        language: 'en',
        learning_enabled: false,
      },
    })
    const off = await said('I like tea')
    expect(off.message.content).toMatch(/Learning is switched off/)

    await said('forget ShulePoa')
    expect(await demoRequest('GET', '/api/v1/nova/memories')).toHaveLength(1)
  })
})
