import { BarChart3, CalendarClock, Inbox } from 'lucide-react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { useMyRuns, useReportCatalogue, useScheduleActions, useSchedules } from './api'

function Schedules({ timeZone }) {
  const { data } = useSchedules()
  const { update, remove } = useScheduleActions()
  if (!data?.length) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="size-4" aria-hidden="true" /> Scheduled reports
        </CardTitle>
        <CardDescription>
          Delivered in Orbit at 06:00 company time. Each recipient gets the report with their own
          access.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {(update.isError || remove.isError) && (
          <Alert variant="error" title={(update.error ?? remove.error).message} />
        )}
        <ul className="divide-y text-sm">
          {data.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
              <div>
                <p className="font-medium">
                  {s.name} {!s.active && <Badge variant="warning">Paused</Badge>}
                </p>
                <p className="text-xs text-muted-foreground">
                  {s.report_title} · {s.frequency} · last {s.range_days} days · to{' '}
                  {s.recipients.map((r) => r.name).join(', ')} · next{' '}
                  {formatDateTime(s.next_run_at, timeZone)}
                </p>
              </div>
              {s.can_manage && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => update.mutate({ id: s.id, active: !s.active })}
                  >
                    {s.active ? 'Pause' : 'Resume'}
                  </Button>
                  <ConfirmButton
                    confirmLabel="Confirm delete"
                    onConfirm={() => remove.mutate(s.id)}
                  >
                    Delete
                  </ConfirmButton>
                </div>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function Reports() {
  const { data: me } = useMe()
  const catalogue = useReportCatalogue()
  const runs = useMyRuns()
  if (catalogue.isPending) return <LoadingState label="Loading reports…" />
  if (catalogue.isError)
    return (
      <ErrorState
        title="Couldn't load reports"
        error={catalogue.error}
        onRetry={catalogue.refetch}
      />
    )
  return (
    <div className="space-y-6">
      {catalogue.data.length === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No reports available"
          description="Your role has no report data."
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {catalogue.data.map((r) => (
            <Link key={r.key} to={`/app/reports/${r.key}`}>
              <Card className="h-full transition-colors hover:border-accent/60">
                <CardContent className="space-y-1 pt-5">
                  <p className="font-medium">{r.title}</p>
                  <p className="text-xs text-muted-foreground">{r.description}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
      <Schedules timeZone={me.company.timezone} />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Inbox className="size-4" aria-hidden="true" /> Delivered to you
          </CardTitle>
        </CardHeader>
        <CardContent>
          {runs.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No scheduled reports delivered yet.</p>
          )}
          <ul className="divide-y text-sm">
            {(runs.data ?? []).map((run) => (
              <li key={run.id} className="py-2">
                <Link to={`/app/reports/runs/${run.id}`} className="hover:text-accent">
                  {run.title}
                </Link>
                <span className="ml-2 text-xs text-muted-foreground">
                  generated {formatDateTime(run.generated_at, me.company.timezone)}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

export function ReportsPage() {
  return (
    <>
      <PageHeader
        title="Reports"
        description="Generated from live Orbit data you are allowed to see, with export and scheduling."
      />
      <RequirePermission permission="report.read">
        <Reports />
      </RequirePermission>
    </>
  )
}
