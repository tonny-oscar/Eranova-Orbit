import { BarChart3 } from 'lucide-react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime, formatNumber } from '@/lib/utils'
import { useAnalyticsOverview } from './api'

const TRAFFIC = [
  ['activeUsers', 'Active users'],
  ['sessions', 'Sessions'],
  ['screenPageViews', 'Page views'],
  ['conversions', 'Conversions'],
]

export function Freshness({ freshness, timeZone }) {
  if (!freshness) return null
  return (
    <p className="text-xs text-muted-foreground">
      Source: {freshness.source}
      {freshness.last_success_at
        ? ` · updated ${formatDateTime(freshness.last_success_at, timeZone)}`
        : ' · never synced'}
      {freshness.stale && (
        <Badge variant="warning" className="ml-2">
          Stale
        </Badge>
      )}
    </p>
  )
}

function ProductAnalytics({ row, timeZone }) {
  const hasAny = row.traffic_freshness || row.product_metrics_freshness
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Link to={`/app/products/${row.product.id}`} className="hover:text-accent">
            {row.product.name}
          </Link>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasAny && (
          <p className="text-sm text-muted-foreground">
            No analytics source connected. Connect Google Analytics or the product's Orbit API under
            Integrations.
          </p>
        )}
        {row.traffic_freshness && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Website traffic · last 28 days</p>
            {row.traffic ? (
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {TRAFFIC.map(([key, label]) => (
                  <div key={key}>
                    <dt className="text-xs text-muted-foreground">{label}</dt>
                    <dd className="text-lg font-semibold">{formatNumber(row.traffic[key])}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">No traffic data received yet.</p>
            )}
            <Freshness freshness={row.traffic_freshness} timeZone={timeZone} />
          </div>
        )}
        {row.product_metrics_freshness && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Reported by the product</p>
            {row.product_metrics ? (
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Object.entries(row.product_metrics).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs capitalize text-muted-foreground">
                      {key.replaceAll('_', ' ')}
                    </dt>
                    <dd className="text-lg font-semibold">{formatNumber(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">No metrics received yet.</p>
            )}
            <Freshness freshness={row.product_metrics_freshness} timeZone={timeZone} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AnalyticsBoard() {
  const { data: me } = useMe()
  const { data, isPending, isError, error, refetch } = useAnalyticsOverview()
  if (isPending) return <LoadingState label="Loading analytics…" />
  if (isError) return <ErrorState title="Couldn't load analytics" error={error} onRetry={refetch} />
  if (data.length === 0)
    return (
      <EmptyState
        icon={BarChart3}
        title="No products yet"
        description="Register a product first."
      />
    )
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {data.map((row) => (
        <ProductAnalytics key={row.product.id} row={row} timeZone={me.company.timezone} />
      ))}
    </div>
  )
}

export function AnalyticsPage() {
  return (
    <>
      <PageHeader
        title="Analytics"
        description="Marketing and usage numbers from connected sources. Figures show only what each source reported."
      />
      <RequirePermission permission="product.read">
        <AnalyticsBoard />
      </RequirePermission>
    </>
  )
}
