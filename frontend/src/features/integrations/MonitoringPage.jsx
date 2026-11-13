import { Activity } from 'lucide-react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { PROVIDER_LABELS, connectionHealth, useMonitoringOverview } from './api'

const DAY_MS = 86_400_000

function certificateBadge(expiresAt, now) {
  if (!expiresAt) return null
  const days = Math.floor((new Date(expiresAt).getTime() - now) / DAY_MS)
  if (days < 0) return <Badge variant="destructive">Certificate expired</Badge>
  if (days < 14) return <Badge variant="warning">Certificate expires in {days}d</Badge>
  return <Badge>Certificate valid {days}d</Badge>
}

function deploymentVariant(state) {
  if (!state) return 'default'
  const s = state.toLowerCase()
  if (['ready', 'succeeded'].includes(s)) return 'success'
  if (['error', 'failed', 'canceled'].includes(s)) return 'destructive'
  return 'accent'
}

function MonitoringBoard() {
  const { data: me } = useMe()
  const tz = me.company.timezone
  const { data, isPending, isError, error, refetch, dataUpdatedAt } = useMonitoringOverview()
  if (isPending) return <LoadingState label="Loading monitoring…" />
  if (isError)
    return <ErrorState title="Couldn't load monitoring" error={error} onRetry={refetch} />
  if (data.integrations.length === 0)
    return (
      <EmptyState
        icon={Activity}
        title="No monitoring sources"
        description="Add an uptime monitor or Vercel connection under Integrations to see live status here."
      />
    )

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Uptime</CardTitle>
          <CardDescription>Percent of the latest checks (up to 48) that succeeded.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.monitors.length === 0 ? (
            <p className="text-sm text-muted-foreground">No uptime monitors configured.</p>
          ) : (
            <ul className="divide-y">
              {data.monitors.map((m) => {
                const latest = m.latest?.data
                return (
                  <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div>
                      <Link
                        to={`/app/integrations/${m.id}`}
                        className="font-medium hover:text-accent"
                      >
                        {m.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {m.product?.name ?? 'Company-wide'} · {m.url}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      {!latest ? (
                        <Badge variant="warning">No checks yet</Badge>
                      ) : latest.up ? (
                        <Badge variant="success">Up</Badge>
                      ) : (
                        <Badge variant="destructive">
                          Down{latest.status ? ` (${latest.status})` : ''}
                        </Badge>
                      )}
                      {latest?.latency_ms != null && (
                        <span className="text-muted-foreground">{latest.latency_ms} ms</span>
                      )}
                      {m.uptime_percent != null && (
                        <span className="text-muted-foreground">
                          {m.uptime_percent}% of {m.checks} checks
                        </span>
                      )}
                      {certificateBadge(latest?.certificate_expires_at, dataUpdatedAt)}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Deployments</CardTitle>
        </CardHeader>
        <CardContent>
          {data.deployments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No deployment sources configured.</p>
          ) : (
            <ul className="divide-y">
              {data.deployments.map((d) => (
                <li
                  key={d.name}
                  className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"
                >
                  <div>
                    <p className="font-medium">{d.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {d.product?.name ?? 'Company-wide'}
                      {d.latest?.data.branch ? ` · ${d.latest.data.branch}` : ''}
                    </p>
                  </div>
                  {d.latest ? (
                    <div className="flex items-center gap-2">
                      <Badge variant={deploymentVariant(d.latest.data.state)}>
                        {d.latest.data.state ?? 'unknown'}
                      </Badge>
                      <span className="text-muted-foreground">{d.latest.data.target}</span>
                    </div>
                  ) : (
                    <Badge variant="warning">No data yet</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integration health</CardTitle>
          <CardDescription>Whether each data source is delivering fresh data.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {data.integrations.map((c) => {
              const health = connectionHealth(c)
              return (
                <li
                  key={c.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm"
                >
                  <div>
                    <Link
                      to={`/app/integrations/${c.id}`}
                      className="font-medium hover:text-accent"
                    >
                      {c.name}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {PROVIDER_LABELS[c.provider] ?? c.provider} ·{' '}
                      {c.last_success_at ? formatDateTime(c.last_success_at, tz) : 'never synced'}
                    </p>
                  </div>
                  <Badge variant={health.variant}>{health.label}</Badge>
                </li>
              )
            })}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

export function MonitoringPage() {
  return (
    <>
      <PageHeader
        title="Monitoring"
        description="Technical health of your live systems: uptime, certificates and deployments."
      />
      <RequirePermission permission="integration.read">
        <MonitoringBoard />
      </RequirePermission>
    </>
  )
}
