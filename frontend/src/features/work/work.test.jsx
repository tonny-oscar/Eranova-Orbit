import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jsonResponse, ME, mockApi, renderRoute } from '../../../tests/utils'

const DEV = { ...ME, permissions: ['task.read', 'task.update', 'project.read'] }
const TASK = {
  id: 't1',
  title: 'Build fee module',
  status: 'in_progress',
  priority: 'high',
  project: { id: 'p1', name: 'ShulePoa v2' },
  assignee: { id: ME.user.id, name: 'Ada' },
  due_date: '2026-11-01',
  parent_task_id: null,
  is_overdue: true,
  updated_at: '2026-11-13T08:00:00Z',
  description: 'Fees',
  milestone_id: null,
  reporter: { id: 'u9', name: 'Lead' },
  start_date: null,
  estimate_hours: null,
  completed_at: null,
  subtasks: [],
  depends_on: [],
  comments: [],
  reviews: [],
  events: [],
  links: [],
  allowed_transitions: ['submitted'],
  can_update: true,
  can_review: false,
}

describe('tasks and my work', () => {
  it('submits a task for review with a note', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, DEV),
      'GET /api/v1/tasks/t1': () => jsonResponse(200, TASK),
      'GET /api/v1/tasks': () => jsonResponse(200, { items: [], total: 0, limit: 100, offset: 0 }),
      'POST /api/v1/tasks/t1/transition': () =>
        jsonResponse(200, { ...TASK, status: 'submitted', allowed_transitions: [] }),
    })
    renderRoute('/app/tasks/t1')
    const user = userEvent.setup()

    expect(await screen.findByText('Overdue')).toBeInTheDocument()
    await user.type(screen.getByLabelText(/note for the reviewer/i), 'Ready')
    await user.click(screen.getByRole('button', { name: 'Submit for review' }))
    await waitFor(() => expect(calls.some((c) => c.path.endsWith('/transition'))).toBe(true))
    expect(JSON.parse(calls.find((c) => c.path.endsWith('/transition')).init.body)).toEqual({
      to: 'submitted',
      note: 'Ready',
    })
    expect(await screen.findByText('Submitted for review')).toBeInTheDocument()
  })

  it('shows reviewers approve and request-revision controls', async () => {
    mockApi({
      'GET /api/v1/auth/me': () =>
        jsonResponse(200, { ...DEV, permissions: [...DEV.permissions, 'task.approve'] }),
      'GET /api/v1/tasks/t1': () =>
        jsonResponse(200, {
          ...TASK,
          status: 'submitted',
          allowed_transitions: ['under_review'],
          can_review: true,
        }),
      'GET /api/v1/tasks': () => jsonResponse(200, { items: [], total: 0, limit: 100, offset: 0 }),
    })
    renderRoute('/app/tasks/t1')
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Request revision' })).toBeDisabled()
  })

  it('shows my work with transparent attendance notice and check-in', async () => {
    const calls = mockApi({
      'GET /api/v1/auth/me': () => jsonResponse(200, DEV),
      'GET /api/v1/me/work': () =>
        jsonResponse(200, {
          open_tasks: [
            {
              id: 't1',
              title: 'Build fee module',
              status: 'assigned',
              priority: 'high',
              project: { id: 'p1', name: 'ShulePoa v2' },
              due_date: null,
              is_overdue: false,
            },
          ],
          awaiting_my_review: [],
          leave_requests: [],
          leave_to_approve: [],
          attendance_today: null,
          unread_notifications: 0,
        }),
      'POST /api/v1/attendance/check-in': () => jsonResponse(201, {}),
    })
    renderRoute('/app/me')
    const user = userEvent.setup()

    expect(await screen.findByRole('link', { name: 'Build fee module' })).toBeInTheDocument()
    expect(screen.getByText(/does not track location/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Check in' }))
    await waitFor(() =>
      expect(calls.some((c) => c.path === '/api/v1/attendance/check-in')).toBe(true),
    )
  })
})
