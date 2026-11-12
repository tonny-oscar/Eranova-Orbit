import { Activity, Database, KeyRound, LayoutGrid } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { useReadiness } from './api'

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
      <div className="grid gap-4 md:grid-cols-2">
        <AccessCard me={me} />
        <SystemStatusCard timeZone={timeZone} />
      </div>
      <Card className="mt-4">
        <CardContent className="pt-5">
          <EmptyState
            icon={LayoutGrid}
            title="No business data connected yet"
            description="Product, customer, project and traffic summaries appear here as each module and integration is delivered. Orbit never shows sample figures as live company metrics."
          />
        </CardContent>
      </Card>
    </>
  )
}
