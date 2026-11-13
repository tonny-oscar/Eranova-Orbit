import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState, Skeleton } from '@/components/ui/states'
import { usePermissions } from '@/features/auth/hooks'
import { formatDateTime, formatNumber } from '@/lib/utils'
import { Freshness } from './AnalyticsPage'
import { connectionHealth, useProductOperations } from './api'

export function ProductOperationsCard({ productId, timeZone }) {
  const { has } = usePermissions()
  const { data, isPending, isError, error, refetch } = useProductOperations(productId)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Live operations</CardTitle>
        <CardDescription>Data from this product's connected systems.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {isPending && <Skeleton className="h-24" />}
        {isError && <ErrorState title="Couldn't load operations" error={error} onRetry={refetch} />}
        {data?.integrations.length === 0 && (
          <p className="text-muted-foreground">
            Nothing connected.{' '}
            {has('integration.manage') && (
              <Link to="/app/integrations" className="text-accent hover:underline">
                Connect a system
              </Link>
            )}
          </p>
        )}
        {data?.integrations.length > 0 && (
          <>
            <ul className="space-y-1.5">
              {data.integrations.map((c) => {
                const health = connectionHealth(c)
                return (
                  <li key={c.id} className="flex items-center justify-between gap-2">
                    <Link to={`/app/integrations/${c.id}`} className="hover:text-accent">
                      {c.name}
                    </Link>
                    <Badge variant={health.variant}>{health.label}</Badge>
                  </li>
                )
              })}
            </ul>
            {data.uptime && (
              <div>
                <p className="font-medium">Uptime</p>
                <p className="text-muted-foreground">
                  {data.uptime.data.up ? 'Up' : 'Down'}
                  {data.uptime.data.latency_ms != null
                    ? ` · ${data.uptime.data.latency_ms} ms`
                    : ''}
                  {` · checked ${formatDateTime(data.uptime.observed_at, timeZone)}`}
                </p>
              </div>
            )}
            {data.deployments.length > 0 && (
              <div>
                <p className="font-medium">Latest deployments</p>
                <ul className="mt-1 space-y-1">
                  {data.deployments.slice(0, 3).map((d) => (
                    <li
                      key={d.external_id}
                      className="flex items-center gap-2 text-muted-foreground"
                    >
                      <Badge>{d.data.state ?? 'unknown'}</Badge>
                      <span>{d.data.target}</span>
                      {d.data.url && (
                        <a
                          href={d.data.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="Open deployment"
                        >
                          <ExternalLink className="size-3" aria-hidden="true" />
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.pull_requests.length > 0 && (
              <div>
                <p className="font-medium">Open pull requests</p>
                <ul className="mt-1 space-y-1">
                  {data.pull_requests.slice(0, 5).map((pr) => (
                    <li key={pr.external_id}>
                      <a
                        href={pr.data.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent hover:underline"
                      >
                        #{pr.data.number} {pr.data.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.product_metrics?.data.metrics && (
              <div>
                <p className="font-medium">Reported metrics</p>
                <dl className="mt-1 grid grid-cols-2 gap-2">
                  {Object.entries(data.product_metrics.data.metrics).map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs capitalize text-muted-foreground">
                        {k.replaceAll('_', ' ')}
                      </dt>
                      <dd className="font-semibold">{formatNumber(v)}</dd>
                    </div>
                  ))}
                </dl>
                <Freshness freshness={data.freshness.product_api} timeZone={timeZone} />
              </div>
            )}
            {data.traffic && (
              <div>
                <p className="font-medium">Traffic · last 28 days</p>
                <p className="text-muted-foreground">
                  {formatNumber(data.traffic.totals.activeUsers)} users ·{' '}
                  {formatNumber(data.traffic.totals.sessions)} sessions
                </p>
                <Freshness freshness={data.freshness.ga4} timeZone={timeZone} />
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
