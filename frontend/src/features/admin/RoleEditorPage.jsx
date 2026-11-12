import { ArrowLeft, Lock } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { usePermissions } from '@/features/auth/hooks'
import { useCreateRole, useDeleteRole, usePermissionCatalogue, useRole, useUpdateRole } from './api'

const ACTIONS = ['read', 'create', 'update', 'delete', 'approve', 'export', 'manage']

const RESOURCE_LABELS = {
  audit_log: 'Audit log',
  settings: 'Company settings',
}

function resourceLabel(resource) {
  return RESOURCE_LABELS[resource] ?? resource.charAt(0).toUpperCase() + resource.slice(1)
}

function PermissionMatrix({ catalogue, selected, onToggle, readOnly, holds }) {
  const byResource = useMemo(() => {
    const map = new Map()
    for (const p of catalogue) {
      if (!map.has(p.resource)) map.set(p.resource, {})
      map.get(p.resource)[p.action] = p
    }
    return [...map.entries()]
  }, [catalogue])

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Permissions by resource and action</caption>
        <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Resource
            </th>
            {ACTIONS.map((a) => (
              <th key={a} scope="col" className="px-2 py-2 text-center font-medium">
                {a}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {byResource.map(([resource, actions]) => (
            <tr key={resource}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                {resourceLabel(resource)}
              </th>
              {ACTIONS.map((action) => {
                const permission = actions[action]
                if (!permission) return <td key={action} className="px-2 py-2" />
                const checked = selected.has(permission.key)
                const allowed = holds(permission.key)
                return (
                  <td key={action} className="px-2 py-2 text-center">
                    <input
                      type="checkbox"
                      className="size-4 accent-[var(--color-primary)]"
                      aria-label={permission.description}
                      title={
                        allowed
                          ? `${permission.description}${permission.is_sensitive ? ' (sensitive)' : ''}`
                          : 'You do not hold this permission, so you cannot grant it'
                      }
                      checked={checked}
                      disabled={readOnly || !allowed}
                      onChange={() => onToggle(permission.key)}
                    />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RoleEditor({ role, catalogue }) {
  const navigate = useNavigate()
  const { has } = usePermissions()
  const isNew = !role
  const readOnly = Boolean(role?.is_locked) || !has(isNew ? 'role.create' : 'role.update')
  const [name, setName] = useState(role?.name ?? '')
  const [description, setDescription] = useState(role?.description ?? '')
  const [selected, setSelected] = useState(() => new Set(role?.permissions ?? []))
  const create = useCreateRole()
  const update = useUpdateRole(role?.id)
  const remove = useDeleteRole(role?.id)
  const mutation = isNew ? create : update
  const error = mutation.error ?? remove.error

  const toggle = (key) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const submit = (event) => {
    event.preventDefault()
    const payload = { name: name.trim(), description, permissions: [...selected].sort() }
    mutation.mutate(payload, {
      onSuccess: (saved) => navigate(`/app/settings/roles/${saved.id}`, { replace: isNew }),
    })
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {error && (
        <Alert variant="error" title={error.message}>
          {error.details?.length > 0 && error.details.map((d) => d.message).join(', ')}
        </Alert>
      )}
      {mutation.isSuccess && !isNew && <Alert variant="success" title="Role saved" />}
      {role?.is_locked && (
        <Alert variant="info" title="This role is locked">
          Super Admin always holds every permission and cannot be edited.
        </Alert>
      )}
      {role && role.assignment_count > 0 && !role.is_locked && (
        <Alert variant="info" title={`Assigned to ${role.assignment_count} user(s)`}>
          Changes apply to everyone who holds this role, immediately.
        </Alert>
      )}

      <Card>
        <CardContent className="grid gap-4 pt-5 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="role-name">Name</Label>
            <Input
              id="role-name"
              required
              minLength={2}
              maxLength={100}
              value={name}
              disabled={readOnly}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="role-description">Description</Label>
            <Textarea
              id="role-description"
              rows={2}
              maxLength={500}
              value={description}
              disabled={readOnly}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Permissions</CardTitle>
          <CardDescription>
            {selected.size} selected. Where the role applies (company, product or own records) is
            chosen when assigning it to a person.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PermissionMatrix
            catalogue={catalogue}
            selected={selected}
            onToggle={toggle}
            readOnly={readOnly}
            holds={has}
          />
        </CardContent>
      </Card>

      {!readOnly && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {!isNew && !role.is_system && has('role.delete') ? (
            <ConfirmButton
              confirmLabel="Confirm delete"
              loading={remove.isPending}
              disabled={role.assignment_count > 0}
              onConfirm={() =>
                remove.mutate(undefined, { onSuccess: () => navigate('/app/settings/roles') })
              }
            >
              Delete role
            </ConfirmButton>
          ) : (
            <span />
          )}
          <Button type="submit" loading={mutation.isPending} disabled={name.trim().length < 2}>
            {isNew ? 'Create role' : 'Save changes'}
          </Button>
        </div>
      )}
    </form>
  )
}

export function RoleEditorPage() {
  const { roleId } = useParams()
  const isNew = !roleId
  const role = useRole(roleId)
  const catalogue = usePermissionCatalogue()

  const loading = catalogue.isPending || (!isNew && role.isPending)
  const failed = catalogue.isError ? catalogue : !isNew && role.isError ? role : null

  return (
    <>
      <Link
        to="/app/settings/roles"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Roles
      </Link>
      <PageHeader
        title={isNew ? 'New role' : (role.data?.name ?? 'Role')}
        actions={
          role.data?.is_locked ? (
            <Badge variant="warning">
              <Lock className="mr-1 size-3" aria-hidden="true" /> Locked
            </Badge>
          ) : role.data?.is_system ? (
            <Badge>Starter role</Badge>
          ) : null
        }
      />
      {loading && <LoadingState label="Loading role…" />}
      {failed && (
        <ErrorState title="Couldn't load this role" error={failed.error} onRetry={failed.refetch} />
      )}
      {!loading && !failed && (
        <RoleEditor
          key={role.data?.id ?? 'new'}
          role={isNew ? null : role.data}
          catalogue={catalogue.data}
        />
      )}
    </>
  )
}
