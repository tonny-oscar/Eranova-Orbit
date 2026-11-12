import { ArrowLeft, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Select } from '@/components/ui/form-controls'
import { Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import {
  useAssignRole,
  useProductOptions,
  useResetUserPassword,
  useRevokeRole,
  useRoles,
  useUpdateUser,
  useUser,
} from './api'
import { TemporaryPasswordNotice } from './TemporaryPasswordNotice'
import { USER_STATUS_VARIANT } from './constants'

const SCOPE_LABELS = {
  company: 'Whole company',
  own: 'Own records only',
  product: 'One product',
}

function AccountCard({ user }) {
  const update = useUpdateUser(user.id)
  const reset = useResetUserPassword(user.id)
  const disabled = user.status === 'disabled'
  const error = update.error ?? reset.error

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <Alert variant="error" title={error.message} />}
        {reset.data && (
          <TemporaryPasswordNotice
            email={user.email}
            password={reset.data.temporary_password}
            onDismiss={() => reset.reset()}
          />
        )}
        {user.can_manage ? (
          <div className="flex flex-wrap gap-2">
            <ConfirmButton
              confirmLabel={disabled ? 'Confirm enable' : 'Confirm disable'}
              confirmVariant={disabled ? 'default' : 'destructive'}
              loading={update.isPending}
              onConfirm={() => update.mutate({ status: disabled ? 'active' : 'disabled' })}
            >
              {disabled ? 'Enable account' : 'Disable account'}
            </ConfirmButton>
            {!disabled && (
              <ConfirmButton
                confirmLabel="Confirm reset"
                loading={reset.isPending}
                onConfirm={() => reset.mutate()}
              >
                Reset password
              </ConfirmButton>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            You can view this account but not change its status or password.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Disabling signs the person out everywhere immediately. Resetting issues a new temporary
          password.
        </p>
      </CardContent>
    </Card>
  )
}

function AssignRoleForm({ user }) {
  const roles = useRoles()
  const products = useProductOptions()
  const assign = useAssignRole(user.id)
  const [roleId, setRoleId] = useState('')
  const [scopeType, setScopeType] = useState('company')
  const [scopeId, setScopeId] = useState('')
  const needsTarget = scopeType === 'product'

  return (
    <form
      className="space-y-3 border-t pt-4"
      onSubmit={(event) => {
        event.preventDefault()
        assign.mutate(
          { role_id: roleId, scope_type: scopeType, scope_id: needsTarget ? scopeId : null },
          {
            onSuccess: () => {
              setRoleId('')
              setScopeId('')
            },
          },
        )
      }}
    >
      {assign.isError && <Alert variant="error" title={assign.error.message} />}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="assign-role">Role</Label>
          <Select id="assign-role" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">Select a role…</option>
            {(roles.data ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="assign-scope">Applies to</Label>
          <Select
            id="assign-scope"
            value={scopeType}
            onChange={(e) => {
              setScopeType(e.target.value)
              setScopeId('')
            }}
          >
            {Object.entries(SCOPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        {needsTarget && (
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="assign-product">Product</Label>
            <Select
              id="assign-product"
              value={scopeId}
              onChange={(e) => setScopeId(e.target.value)}
            >
              <option value="">Select a product…</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>
      <Button
        type="submit"
        variant="outline"
        disabled={!roleId || (needsTarget && !scopeId)}
        loading={assign.isPending}
      >
        Assign role
      </Button>
    </form>
  )
}

function RolesCard({ user, isSelf }) {
  const { has } = usePermissions()
  const products = useProductOptions()
  const revoke = useRevokeRole(user.id)
  const canManageRoles = has('role.manage') && !isSelf
  const productName = (id) => products.data?.find((p) => p.id === id)?.name ?? 'a product'

  return (
    <Card>
      <CardHeader>
        <CardTitle>Roles</CardTitle>
        <CardDescription>What this person can do, and where.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {revoke.isError && <Alert variant="error" title={revoke.error.message} />}
        {user.roles.length === 0 ? (
          <p className="text-sm text-muted-foreground">No roles assigned.</p>
        ) : (
          <ul className="divide-y">
            {user.roles.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <div>
                  <p className="font-medium">{a.role_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {a.scope_type === 'product'
                      ? `Product: ${productName(a.scope_id)}`
                      : (SCOPE_LABELS[a.scope_type] ?? a.scope_type)}
                  </p>
                </div>
                {canManageRoles && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove ${a.role_name}`}
                    loading={revoke.isPending && revoke.variables === a.id}
                    onClick={() => revoke.mutate(a.id)}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {canManageRoles && <AssignRoleForm user={user} />}
        {isSelf && (
          <p className="text-xs text-muted-foreground">
            Your own roles must be changed by another administrator.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function UserDetailPage() {
  const { userId } = useParams()
  const { data: me } = useMe()
  const { data: user, isPending, isError, error, refetch } = useUser(userId)

  if (isPending) return <LoadingState label="Loading user…" />
  if (isError) return <ErrorState title="Couldn't load this user" error={error} onRetry={refetch} />

  const isSelf = user.id === me.user.id
  return (
    <>
      <Link
        to="/app/settings/users"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Users
      </Link>
      <PageHeader title={user.full_name} description={user.email} />
      <div className="mb-4 flex flex-wrap gap-2">
        <Badge variant={USER_STATUS_VARIANT[user.status]}>{user.status}</Badge>
        {user.must_change_password && <Badge variant="warning">Temporary password</Badge>}
        <span className="text-xs text-muted-foreground">
          Last sign-in: {formatDateTime(user.last_login_at, me.company.timezone)}
        </span>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <RolesCard user={user} isSelf={isSelf} />
        {!isSelf && <AccountCard user={user} />}
      </div>
    </>
  )
}
