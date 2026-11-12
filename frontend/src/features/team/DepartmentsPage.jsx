import { Building2, Pencil, Plus } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { usePermissions } from '@/features/auth/hooks'
import { useCreateDepartment, useDepartments, useEmployees, useUpdateDepartment } from './api'
import { TeamTabs } from './TeamTabs'

function DepartmentForm({ department, onDone }) {
  const create = useCreateDepartment()
  const update = useUpdateDepartment()
  const people = useEmployees({ limit: 100, offset: 0 })
  const mutation = department ? update : create
  const [name, setName] = useState(department?.name ?? '')
  const [description, setDescription] = useState(department?.description ?? '')
  const [headId, setHeadId] = useState(department?.head?.id ?? '')
  const prefix = department ? `dept-${department.id}` : 'dept-new'

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault()
        const payload = { name: name.trim(), description, head_user_id: headId || null }
        mutation.mutate(department ? { id: department.id, ...payload } : payload, {
          onSuccess: onDone,
        })
      }}
    >
      {mutation.isError && <Alert variant="error" title={mutation.error.message} />}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-name`}>Name</Label>
          <Input
            id={`${prefix}-name`}
            required
            minLength={2}
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-head`}>Head</Label>
          <Select id={`${prefix}-head`} value={headId} onChange={(e) => setHeadId(e.target.value)}>
            <option value="">No head assigned</option>
            {(people.data?.items ?? []).map((p) => (
              <option key={p.user.id} value={p.user.id}>
                {p.user.full_name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor={`${prefix}-description`}>Description</Label>
          <Textarea
            id={`${prefix}-description`}
            rows={2}
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
      </div>
      <div className="flex gap-2">
        <Button type="submit" loading={mutation.isPending} disabled={name.trim().length < 2}>
          {department ? 'Save' : 'Create department'}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

function DepartmentList() {
  const { has } = usePermissions()
  const canManage = has('employee.manage')
  const { data, isPending, isError, error, refetch } = useDepartments()
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState(null)

  if (isPending) return <LoadingState label="Loading departments…" />
  if (isError)
    return <ErrorState title="Couldn't load departments" error={error} onRetry={refetch} />

  return (
    <div className="space-y-4">
      {canManage && !creating && (
        <Button onClick={() => setCreating(true)}>
          <Plus aria-hidden="true" /> New department
        </Button>
      )}
      {creating && (
        <Card>
          <CardHeader>
            <CardTitle>New department</CardTitle>
          </CardHeader>
          <CardContent>
            <DepartmentForm onDone={() => setCreating(false)} />
          </CardContent>
        </Card>
      )}
      {data.length === 0 && !creating && (
        <EmptyState
          icon={Building2}
          title="No departments yet"
          description={
            canManage
              ? 'Create departments to organise people and grant department-scoped access.'
              : 'Departments will appear here once an administrator creates them.'
          }
        />
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {data.map((d) => (
          <Card key={d.id}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>{d.name}</CardTitle>
                  <CardDescription>
                    {d.member_count} {d.member_count === 1 ? 'person' : 'people'} · Head:{' '}
                    {d.head?.full_name ?? 'not assigned'}
                  </CardDescription>
                </div>
                {canManage && editingId !== d.id && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Edit ${d.name}`}
                    onClick={() => setEditingId(d.id)}
                  >
                    <Pencil aria-hidden="true" />
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {editingId === d.id ? (
                <DepartmentForm department={d} onDone={() => setEditingId(null)} />
              ) : (
                <p className="text-sm text-muted-foreground">
                  {d.description || 'No description.'}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

export function DepartmentsPage() {
  return (
    <>
      <PageHeader title="Team" description="People, departments and reporting lines." />
      <TeamTabs />
      <RequirePermission permission="employee.read">
        <DepartmentList />
      </RequirePermission>
    </>
  )
}
