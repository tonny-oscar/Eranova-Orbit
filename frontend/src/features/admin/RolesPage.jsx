import { Lock, ShieldCheck } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useRoles } from './api'

function RolesTable() {
  const { data: roles, isPending, isError, error, refetch } = useRoles()

  if (isPending) return <LoadingState label="Loading roles…" />
  if (isError) return <ErrorState title="Couldn't load roles" error={error} onRetry={refetch} />
  if (roles.length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="No roles defined"
        description="Run bootstrap to create the starter roles."
      />
    )
  }

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Company roles</caption>
          <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Role
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Description
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Permissions
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Assigned
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {roles.map((role) => (
              <tr key={role.id} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{role.name}</span>
                    {role.is_locked && (
                      <Badge variant="warning">
                        <Lock className="mr-1 size-3" aria-hidden="true" /> Locked
                      </Badge>
                    )}
                    {role.is_system && !role.is_locked && <Badge>Starter</Badge>}
                  </div>
                </td>
                <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                  {role.description}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{role.permissions.length}</td>
                <td className="px-4 py-3 text-right tabular-nums">{role.assignment_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function RolesPage() {
  return (
    <>
      <PageHeader
        title="Roles"
        description="Starter roles are fully customisable except the locked Super Admin role. Role editing arrives with user management."
      />
      <RequirePermission permission="role.read">
        <RolesTable />
      </RequirePermission>
    </>
  )
}
