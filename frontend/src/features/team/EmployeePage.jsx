import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { usePermissions } from '@/features/auth/hooks'
import {
  EMPLOYMENT_TYPES,
  useDepartments,
  useEmployee,
  useEmployees,
  useUpdateEmployee,
} from './api'

function ProfileForm({ employee }) {
  const departments = useDepartments()
  const people = useEmployees({ limit: 100, offset: 0 })
  const update = useUpdateEmployee(employee.user.id)
  const [values, setValues] = useState({
    department_id: employee.department?.id ?? '',
    job_title: employee.job_title ?? '',
    manager_user_id: employee.manager?.id ?? '',
    employment_type: employee.employment_type ?? 'full_time',
    start_date: employee.start_date ?? '',
  })
  const set = (field) => (event) => setValues((v) => ({ ...v, [field]: event.target.value }))

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        update.mutate({
          department_id: values.department_id || null,
          job_title: values.job_title.trim() || null,
          manager_user_id: values.manager_user_id || null,
          employment_type: values.employment_type,
          start_date: values.start_date || null,
        })
      }}
    >
      {update.isError && <Alert variant="error" title={update.error.message} />}
      {update.isSuccess && <Alert variant="success" title="Profile saved" />}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="emp-title">Job title</Label>
          <Input
            id="emp-title"
            maxLength={120}
            value={values.job_title}
            onChange={set('job_title')}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="emp-department">Primary department</Label>
          <Select id="emp-department" value={values.department_id} onChange={set('department_id')}>
            <option value="">None</option>
            {(departments.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="emp-manager">Manager</Label>
          <Select id="emp-manager" value={values.manager_user_id} onChange={set('manager_user_id')}>
            <option value="">None</option>
            {(people.data?.items ?? [])
              .filter((p) => p.user.id !== employee.user.id)
              .map((p) => (
                <option key={p.user.id} value={p.user.id}>
                  {p.user.full_name}
                </option>
              ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="emp-type">Employment type</Label>
          <Select id="emp-type" value={values.employment_type} onChange={set('employment_type')}>
            {EMPLOYMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="emp-start">Start date</Label>
          <Input
            id="emp-start"
            type="date"
            value={values.start_date}
            onChange={set('start_date')}
          />
        </div>
      </div>
      <Button type="submit" loading={update.isPending}>
        Save profile
      </Button>
    </form>
  )
}

function ProfileView({ employee }) {
  const rows = [
    ['Job title', employee.job_title],
    ['Department', employee.department?.name],
    ['Manager', employee.manager?.full_name],
    ['Employment type', EMPLOYMENT_TYPES.find((t) => t.value === employee.employment_type)?.label],
    ['Start date', employee.start_date],
  ]
  return (
    <dl className="divide-y">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-4 py-2.5 text-sm">
          <dt className="text-muted-foreground">{label}</dt>
          <dd>{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function EmployeePage() {
  const { userId } = useParams()
  const { has } = usePermissions()
  const { data: employee, isPending, isError, error, refetch } = useEmployee(userId)

  if (isPending) return <LoadingState label="Loading profile…" />
  if (isError)
    return <ErrorState title="Couldn't load this profile" error={error} onRetry={refetch} />

  return (
    <>
      <Link
        to="/app/team"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Team
      </Link>
      <PageHeader
        title={employee.user.full_name}
        description={employee.user.email}
        actions={
          has('user.read') && (
            <Link
              to={`/app/settings/users/${employee.user.id}`}
              className="text-sm text-accent hover:underline"
            >
              Account and roles
            </Link>
          )
        }
      />
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Work profile</CardTitle>
          <CardDescription>
            Orbit stores only work information here. Do not add personal identifiers or sensitive
            data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {employee.can_update ? (
            <ProfileForm employee={employee} />
          ) : (
            <ProfileView employee={employee} />
          )}
        </CardContent>
      </Card>
    </>
  )
}
