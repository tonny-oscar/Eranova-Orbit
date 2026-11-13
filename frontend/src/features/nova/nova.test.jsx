import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const STATUS = {
  mode: 'basic',
  provider: null,
  model: null,
  capabilities: {},
  tools: [],
  retention_days: 180,
  shares_contact_details: false,
  can_view_company_usage: false,
}
const USAGE = {
  window_days: 30,
  scope: 'you',
  replies: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  cost_usd: null,
  avg_latency_ms: 0,
  provider_errors: 0,
  tool_outcomes: {},
  by_user: [],
  daily_token_limit: 200000,
}
const APPROVAL = {
  id: 'ap1',
  tool: 'create_task',
  summary: "Create task 'Call the printer' in Launch",
  arguments: { project: 'Launch', title: 'Call the printer' },
  policy: 'self_confirm',
  reason: 'Spoken requests are confirmed on screen before anything changes.',
  status: 'pending',
  requester: { id: 'u1', name: 'Ada Lovelace' },
  decided_by: null,
  decided_at: null,
  decision_note: null,
  result_summary: null,
  created_at: '2026-11-13T09:00:00Z',
  expires_at: '2026-11-14T09:00:00Z',
  can_decide: true,
}

function novaApi(overrides = {}) {
  const state = { messages: [], executions: [] }
  const calls = mockApi({
    'GET /api/v1/auth/me': () => jsonResponse(200, ME),
    'GET /api/v1/nova/status': () => jsonResponse(200, STATUS),
    'GET /api/v1/nova/usage': () => jsonResponse(200, USAGE),
    'GET /api/v1/nova/conversations': () => jsonResponse(200, []),
    'GET /api/v1/nova/approvals': () => jsonResponse(200, []),
    'POST /api/v1/nova/conversations': () =>
      jsonResponse(201, {
        id: 'c1',
        title: 'New conversation',
        updated_at: '2026-11-13T09:00:00Z',
      }),
    'GET /api/v1/nova/conversations/c1': () =>
      jsonResponse(200, {
        conversation: { id: 'c1', title: 'My work', updated_at: '2026-11-13T09:00:00Z' },
        ...state,
      }),
    'POST /api/v1/nova/conversations/c1/messages': (init) => {
      const body = JSON.parse(init.body)
      const reply = {
        id: 'm2',
        role: 'assistant',
        content: '2 open task(s), 1 overdue.',
        via: 'text',
        links: [{ label: 'Write release notes', href: '/app/tasks/t1' }],
        status: 'ok',
        provider: 'basic',
        model: null,
        created_at: '2026-11-13T09:00:02Z',
      }
      const execution = {
        id: 'e1',
        tool: 'my_work',
        authority: 'read',
        status: 'succeeded',
        summary: '2 open task(s)',
        error: null,
        approval_id: null,
        created_at: '2026-11-13T09:00:01Z',
      }
      state.messages = [
        {
          ...reply,
          id: 'm1',
          role: 'user',
          content: body.content,
          via: body.via,
          links: [],
          created_at: '2026-11-13T09:00:00Z',
        },
        reply,
      ]
      state.executions = [execution]
      return jsonResponse(200, { message: reply, executions: [execution], approvals: [] })
    },
    ...overrides,
  })
  return calls
}

describe('NOVA', () => {
  it('starts a conversation, shows what NOVA did and links to records', async () => {
    const calls = novaApi()
    renderRoute('/app/nova')
    expect(await screen.findByText(/Basic mode · look-ups only/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'What should I work on today?' }))
    await waitFor(() =>
      expect(calls.some((c) => c.path === '/api/v1/nova/conversations/c1/messages')).toBe(true),
    )
    const sent = calls.find((c) => c.path.endsWith('/messages'))
    expect(JSON.parse(sent.init.body)).toEqual({
      content: 'What should I work on today?',
      via: 'text',
    })
    expect(await screen.findByText('2 open task(s), 1 overdue.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Write release notes/ })).toHaveAttribute(
      'href',
      '/app/tasks/t1',
    )
    expect(screen.getByText('my_work')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('lets the requester confirm a prepared action with its exact parameters', async () => {
    const calls = novaApi({
      'GET /api/v1/nova/approvals': () => jsonResponse(200, [APPROVAL]),
      'POST /api/v1/nova/approvals/ap1/decision': () =>
        jsonResponse(200, {
          ...APPROVAL,
          status: 'executed',
          can_decide: false,
          result_summary: "Created task 'Call the printer' in Launch.",
        }),
    })
    renderRoute('/app/nova/approvals')
    expect(await screen.findByText(APPROVAL.summary)).toBeInTheDocument()
    expect(screen.getByText(/"title": "Call the printer"/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(calls.some((c) => c.path.endsWith('/decision'))).toBe(true))
    expect(JSON.parse(calls.find((c) => c.path.endsWith('/decision')).init.body)).toEqual({
      approve: true,
      note: null,
    })
    expect(
      await screen.findByText("Created task 'Call the printer' in Launch."),
    ).toBeInTheDocument()
  })
})
