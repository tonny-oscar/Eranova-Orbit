import { zodResolver } from '@hookform/resolvers/zod'
import { Search, UserPlus, Users } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { FieldError, Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { usePermissions } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { useCreateUser, useUsers } from './api'
import { USER_STATUS_VARIANT } from './constants'
import { TemporaryPasswordNotice } from './TemporaryPasswordNotice'

const PAGE_SIZE = 25

const createSchema = z.object({
  full_name: z.string().trim().min(1, { message: 'Enter a name.' }).max(200),
  email: z.email({ message: 'Enter a valid email address.' }),
})

function CreateUserCard({ onClose }) {
  const create = useCreateUser()
  const [issued, setIssued] = useState(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(createSchema), defaultValues: { full_name: '', email: '' } })

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>Add a user</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {issued ? (
          <TemporaryPasswordNotice
            email={issued.user.email}
            password={issued.temporary_password}
            onDismiss={() => {
              setIssued(null)
              onClose()
            }}
          />
        ) : (
          <form
            noValidate
            className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-start"
            onSubmit={handleSubmit((values) =>
              create.mutate(values, {
                onSuccess: (data) => {
                  reset()
                  setIssued(data)
                },
              }),
            )}
          >
            {create.isError && (
              <div className="md:col-span-3">
                <Alert variant="error" title={create.error.message} />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="new-user-name">Full name</Label>
              <Input id="new-user-name" {...register('full_name')} />
              <FieldError>{errors.full_name?.message}</FieldError>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-user-email">Work email</Label>
              <Input id="new-user-email" type="email" {...register('email')} />
              <FieldError>{errors.email?.message}</FieldError>
            </div>
            <div className="flex gap-2 md:pt-7">
              <Button type="submit" loading={create.isPending}>
                Create user
              </Button>
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
            </div>
          </form>
        )}
        {!issued && (
          <p className="text-xs text-muted-foreground">
            Orbit generates a one-time temporary password. Assign roles after creating the account.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function UsersTable() {
  const { has } = usePermissions()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch, isFetching } = useUsers({
    q,
    status,
    limit: PAGE_SIZE,
    offset,
  })

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="user-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="user-search"
              type="search"
              placeholder="Name or email"
              className="w-72 pl-9"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setOffset(0)
              }}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="user-status">Status</Label>
          <Select
            id="user-status"
            className="w-40"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </Select>
        </div>
        {has('user.create') && !creating && (
          <Button className="ml-auto" onClick={() => setCreating(true)}>
            <UserPlus aria-hidden="true" /> Add user
          </Button>
        )}
      </div>

      {creating && <CreateUserCard onClose={() => setCreating(false)} />}

      {isPending && <LoadingState label="Loading users…" />}
      {isError && <ErrorState title="Couldn't load users" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState icon={Users} title="No users match" description="Try a different search." />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">User accounts</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Name
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Roles
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((u) => (
                  <tr key={u.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link
                        to={`/app/settings/users/${u.id}`}
                        className="font-medium hover:text-accent"
                      >
                        {u.full_name}
                      </Link>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                      {u.role_names.length ? u.role_names.join(', ') : 'No roles'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <Badge variant={USER_STATUS_VARIANT[u.status]}>{u.status}</Badge>
                        {u.must_change_password && (
                          <Badge variant="warning">Temporary password</Badge>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <span>
              {data.offset + 1}–{data.offset + data.items.length} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={data.offset + data.items.length >= data.total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  )
}

export function UsersPage() {
  return (
    <>
      <PageHeader title="Users" description="Staff accounts, their status and roles." />
      <RequirePermission permission="user.read">
        <UsersTable />
      </RequirePermission>
    </>
  )
}
