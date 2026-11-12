import {
  Activity,
  Boxes,
  Database,
  KeyRound,
  LayoutGrid,
  ScrollText,
  UsersRound,
} from 'lucide-react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { LIFECYCLE_STATUSES } from '@/features/products/constants'
import { formatDateTime } from '@/lib/utils'
import { useDashboardSummary, useReadiness } from './api'

function greeting(timeZone) {
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hour12: false, timeZone }).format(
      new Date(),
    ),
  )
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function Metric({ label, value, to }) {
  const content = (
    <>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </>
  )
  return to ? (
    <Link to={to} className="rounded-md p-1 hover:bg-muted/50">
      {content}
    </Link>
  ) : (
    <div className="p-1">{content}</div>
  )
}

function ProductsCard({ products }) {
  const statuses = LIFECYCLE_STATUSES.filter((s) => products.by_status[s.value])
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Boxes className="size-4 text-accent" aria-hidden="true" /> Products
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Metric label="In registry" value={products.total} to="/app/products" />
          <Metric label="Awaiting confirmation" value={products.unconfirmed} />
        </div>
        {statuses.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {statuses.map((s) => (
              <Badge key={s.value} variant={s.variant}>
                {s.label}: {products.by_status[s.value]}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No products registered yet.</p>
        )}
      </CardContent>
    </Card>
  )
}

function PeopleCard({ people, accounts }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UsersRound className="size-4 text-accent" aria-hidden="true" /> People
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-2">
        {people && <Metric label="Active people" value={people.active} to="/app/team" />}
        {people && (
          <Metric label="Departments" value={people.departments} to="/app/team/departments" />
        )}
        {accounts && (
          <Metric
            label="Awaiting first sign-in"
            value={accounts.awaiting_first_sign_in}
            to="/app/settings/users"
          />
        )}
        {accounts && <Metric label="Disabled accounts" value={accounts.disabled} />}
      </CardContent>
    </Card>
  )
}

function ActivityCard({ events, timeZone }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScrollText className="size-4 text-accent" aria-hidden="true" /> Recent activity
        </CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
        ) : (
          <ul className="space-y-2">
            {events.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate font-mono text-xs">{e.action}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDateTime(e.created_at, timeZone)}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Link
          to="/app/settings/audit-log"
          className="mt-3 inline-block text-xs text-accent hover:underline"
        >
          View audit log
        </Link>
      </CardContent>
    </Card>
  )
}

function SystemStatusCard({ timeZone }) {
  const { data, isPending, isError, error, refetch } = useReadiness()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="size-4 text-accent" aria-hidden="true" /> Platform status
        </CardTitle>
        <CardDescription>Live check of the Orbit API and its database.</CardDescription>
      </CardHeader>
      <CardContent>
        {isPending && <Skeleton className="h-16" />}
        {isError && <ErrorState title="Status unavailable" error={error} onRetry={refetch} />}
        {data && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Database className="size-4 text-muted-foreground" aria-hidden="true" /> Database
              </span>
              <Badge variant={data.checks?.database === 'ok' ? 'success' : 'destructive'}>
                {data.checks?.database === 'ok' ? 'Operational' : 'Unavailable'}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Checked {formatDateTime(data.checkedAt, timeZone)}
              {data.environment ? ` · ${data.environment} environment` : ''}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AccessCard({ me }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-accent" aria-hidden="true" /> Your access
        </CardTitle>
        <CardDescription>Roles assigned to your account and where they apply.</CardDescription>
      </CardHeader>
      <CardContent>
        {me.roles.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No roles assigned yet. Ask a Super Admin to grant the access you need.
          </p>
        ) : (
          <ul className="space-y-2">
            {me.roles.map((role) => (
              <li key={role.assignment_id} className="flex items-center justify-between text-sm">
                <span>{role.role_name}</span>
                <Badge variant="accent">{role.scope_type}</Badge>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          {me.permissions.length} permission{me.permissions.length === 1 ? '' : 's'} in effect
        </p>
      </CardContent>
    </Card>
  )
}

function CompanySummary({ timeZone }) {
  const { data, isPending, isError, error, refetch } = useDashboardSummary()
  if (isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    )
  }
  if (isError)
    return <ErrorState title="Couldn't load the summary" error={error} onRetry={refetch} />

  const hasAny = data.products || data.people || data.accounts || data.recent_activity
  return (
    <section aria-label="Company summary" className="space-y-2">
      {hasAny ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.products && <ProductsCard products={data.products} />}
          {(data.people || data.accounts) && (
            <PeopleCard people={data.people} accounts={data.accounts} />
          )}
          {data.recent_activity && (
            <ActivityCard events={data.recent_activity} timeZone={timeZone} />
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Your roles don't include company summaries yet.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Source: {data.source} · generated {formatDateTime(data.generated_at, timeZone)}
      </p>
    </section>
  )
}

export function OverviewPage() {
  const { data: me } = useMe()
  const timeZone = me.company.timezone
  const firstName = me.user.full_name.split(' ')[0]

  return (
    <>
      <PageHeader
        title={`${greeting(timeZone)}, ${firstName}`}
        description={`${me.company.name} command centre`}
      />
      <div className="space-y-4">
        <CompanySummary timeZone={timeZone} />
        <div className="grid gap-4 md:grid-cols-2">
          <AccessCard me={me} />
          <SystemStatusCard timeZone={timeZone} />
        </div>
        <Card>
          <CardContent className="pt-5">
            <EmptyState
              icon={LayoutGrid}
              title="Sales, revenue and traffic are not connected yet"
              description="These appear once the CRM, finance and analytics modules and integrations are delivered. Orbit never shows sample figures as live company metrics."
            />
          </CardContent>
        </Card>
      </div>
    </>
  )
}
