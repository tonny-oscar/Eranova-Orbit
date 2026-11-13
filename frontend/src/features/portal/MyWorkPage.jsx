import { Clock } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { TaskStatusBadge } from '@/features/work/TaskList'
import { formatDateTime } from '@/lib/utils'
import { useAttendance, useMyWork, usePortalActions } from './api'

const LEAVE_VARIANT = {
  pending: 'warning',
  approved: 'success',
  rejected: 'destructive',
  cancelled: 'default',
}

function TaskList({ tasks, empty }) {
  if (tasks.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <ul className="divide-y">
      {tasks.map((t) => (
        <li key={t.id} className="flex items-center justify-between gap-3 py-2 text-sm">
          <div>
            <Link to={`/app/tasks/${t.id}`} className="font-medium hover:text-accent">
              {t.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {t.project.name}
              {t.due_date ? ` · due ${t.due_date}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {t.is_overdue && <Badge variant="destructive">Overdue</Badge>}
            <TaskStatusBadge status={t.status} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function AttendanceCard({ today, tz }) {
  const actions = usePortalActions()
  const error = actions.checkIn.error ?? actions.checkOut.error
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="size-4 text-accent" aria-hidden="true" /> Attendance
        </CardTitle>
        <CardDescription>
          Recorded only when you check in or out yourself. Orbit does not track location, devices or
          activity.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {error && <Alert variant="error" title={error.message} />}
        {today ? (
          <p>
            Checked in {formatDateTime(today.check_in_at, tz)}
            {today.check_out_at ? ` · out ${formatDateTime(today.check_out_at, tz)}` : ''}
          </p>
        ) : (
          <p className="text-muted-foreground">You have not checked in today.</p>
        )}
        <div className="flex gap-2">
          {!today && (
            <Button
              size="sm"
              loading={actions.checkIn.isPending}
              onClick={() => actions.checkIn.mutate(null)}
            >
              Check in
            </Button>
          )}
          {today && !today.check_out_at && (
            <Button
              size="sm"
              variant="outline"
              loading={actions.checkOut.isPending}
              onClick={() => actions.checkOut.mutate()}
            >
              Check out
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function LeaveCard({ requests, toApprove }) {
  const actions = usePortalActions()
  const [values, setValues] = useState({ type: 'annual', start_date: '', end_date: '', reason: '' })
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))
  const error = actions.requestLeave.error ?? actions.decideLeave.error ?? actions.cancelLeave.error
  return (
    <Card>
      <CardHeader>
        <CardTitle>Leave</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <Alert variant="error" title={error.message} />}
        <form
          className="grid gap-2 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            actions.requestLeave.mutate(
              { ...values, reason: values.reason.trim() },
              {
                onSuccess: () =>
                  setValues({ type: 'annual', start_date: '', end_date: '', reason: '' }),
              },
            )
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="leave-type">Type</Label>
            <Select id="leave-type" value={values.type} onChange={set('type')}>
              {['annual', 'sick', 'parental', 'unpaid', 'other'].map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="leave-reason">Reason (optional)</Label>
            <Input id="leave-reason" value={values.reason} onChange={set('reason')} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="leave-start">From</Label>
            <Input
              id="leave-start"
              type="date"
              value={values.start_date}
              onChange={set('start_date')}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="leave-end">To</Label>
            <Input id="leave-end" type="date" value={values.end_date} onChange={set('end_date')} />
          </div>
          <Button
            type="submit"
            size="sm"
            className="sm:col-span-2 sm:w-fit"
            disabled={!values.start_date || !values.end_date}
            loading={actions.requestLeave.isPending}
          >
            Request leave
          </Button>
        </form>
        {requests.length > 0 && (
          <ul className="divide-y text-sm">
            {requests.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2 py-2">
                <span>
                  {r.type} · {r.start_date} to {r.end_date} ({r.days} day{r.days === 1 ? '' : 's'})
                </span>
                <span className="flex items-center gap-2">
                  <Badge variant={LEAVE_VARIANT[r.status]}>{r.status}</Badge>
                  {r.status === 'pending' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => actions.cancelLeave.mutate(r.id)}
                    >
                      Cancel
                    </Button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        {toApprove.length > 0 && (
          <div className="space-y-2 border-t pt-3">
            <p className="text-sm font-medium">Waiting for your decision</p>
            {toApprove.map((r) => (
              <div
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-2 text-sm"
              >
                <span>
                  {r.person.name}: {r.type}, {r.start_date} to {r.end_date}
                  {r.reason ? ` · ${r.reason}` : ''}
                </span>
                <span className="flex gap-2">
                  <Button
                    size="sm"
                    variant="accent"
                    onClick={() => actions.decideLeave.mutate({ id: r.id, decision: 'approved' })}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => actions.decideLeave.mutate({ id: r.id, decision: 'rejected' })}
                  >
                    Reject
                  </Button>
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function TeamAttendance({ tz }) {
  const { data, isPending } = useAttendance(true)
  if (isPending) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Team attendance (last 14 days)</CardTitle>
      </CardHeader>
      <CardContent>
        {data?.length === 0 ? (
          <p className="text-sm text-muted-foreground">No check-ins recorded.</p>
        ) : (
          <ul className="divide-y text-sm">
            {data.map((a) => (
              <li key={a.id} className="flex justify-between gap-2 py-1.5">
                <span>{a.person.name}</span>
                <span className="text-muted-foreground">
                  {a.work_date} · {formatDateTime(a.check_in_at, tz)}
                  {a.check_out_at ? ` – ${formatDateTime(a.check_out_at, tz)}` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function MyWorkPage() {
  const { data: me } = useMe()
  const { has } = usePermissions()
  const { data, isPending, isError, error, refetch } = useMyWork()
  const tz = me.company.timezone

  if (isPending) return <LoadingState label="Loading your work…" />
  if (isError) return <ErrorState title="Couldn't load your work" error={error} onRetry={refetch} />

  return (
    <>
      <PageHeader
        title="My work"
        description="Your tasks, reviews, leave and attendance in one place."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>My open tasks ({data.open_tasks.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <TaskList tasks={data.open_tasks} empty="No open tasks. Nice." />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Waiting for my review ({data.awaiting_my_review.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <TaskList tasks={data.awaiting_my_review} empty="Nothing waiting for your review." />
          </CardContent>
        </Card>
        <AttendanceCard today={data.attendance_today} tz={tz} />
        <LeaveCard requests={data.leave_requests} toApprove={data.leave_to_approve} />
        {has('employee.read') && <TeamAttendance tz={tz} />}
      </div>
    </>
  )
}
