import { FolderKanban, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { usePermissions } from '@/features/auth/hooks'
import { PROJECT_STATUSES, useCreateProject, useProjects } from './api'

const statusVariant = {
  active: 'success',
  planned: 'accent',
  on_hold: 'warning',
  completed: 'default',
  cancelled: 'destructive',
}

function NewProject({ onClose }) {
  const navigate = useNavigate()
  const products = useProductOptions()
  const create = useCreateProject()
  const [values, setValues] = useState({
    name: '',
    product_id: '',
    priority: 'medium',
    due_date: '',
  })
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))
  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
        <form
          className="grid gap-3 md:grid-cols-5 md:items-end"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                name: values.name.trim(),
                product_id: values.product_id || null,
                priority: values.priority,
                due_date: values.due_date || null,
                status: 'active',
              },
              { onSuccess: (p) => navigate(`/app/projects/${p.id}`) },
            )
          }}
        >
          {create.isError && (
            <div className="md:col-span-5">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="np-name">Project name</Label>
            <Input id="np-name" value={values.name} onChange={set('name')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="np-product">Product</Label>
            <Select id="np-product" value={values.product_id} onChange={set('product_id')}>
              <option value="">Internal / none</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="np-due">Due date</Label>
            <Input id="np-due" type="date" value={values.due_date} onChange={set('due_date')} />
          </div>
          <div className="flex gap-2">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={values.name.trim().length < 2}
            >
              Create
            </Button>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function ProjectGrid() {
  const { has } = usePermissions()
  const [status, setStatus] = useState('')
  const [creating, setCreating] = useState(false)
  const { data, isPending, isError, error, refetch } = useProjects({ status, limit: 100 })
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="project-status">Status</Label>
          <Select
            id="project-status"
            className="w-40"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            {PROJECT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace('_', ' ')}
              </option>
            ))}
          </Select>
        </div>
        {has('project.create') && !creating && (
          <Button className="ml-auto" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" /> New project
          </Button>
        )}
      </div>
      {creating && <NewProject onClose={() => setCreating(false)} />}
      {isPending && <LoadingState label="Loading projects…" />}
      {isError && <ErrorState title="Couldn't load projects" error={error} onRetry={refetch} />}
      {data?.items.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Create a project to plan work for a product."
        />
      )}
      {data?.items.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.items.map((p) => (
            <Link
              key={p.id}
              to={`/app/projects/${p.id}`}
              className="rounded-xl border bg-card p-5 transition-colors hover:border-accent/50"
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <p className="font-semibold">{p.name}</p>
                <Badge variant={statusVariant[p.status]}>{p.status.replace('_', ' ')}</Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {p.product?.name ?? 'Internal'} · {p.manager?.name ?? 'No manager'}
              </p>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                <div>
                  <p className="text-lg font-semibold tabular-nums">{p.tasks.open}</p>
                  <p className="text-muted-foreground">open</p>
                </div>
                <div>
                  <p
                    className={`text-lg font-semibold tabular-nums ${p.tasks.overdue ? 'text-destructive' : ''}`}
                  >
                    {p.tasks.overdue}
                  </p>
                  <p className="text-muted-foreground">overdue</p>
                </div>
                <div>
                  <p className="text-lg font-semibold tabular-nums">{p.tasks.awaiting_review}</p>
                  <p className="text-muted-foreground">in review</p>
                </div>
              </div>
              {p.due_date && <p className="mt-3 text-xs text-muted-foreground">Due {p.due_date}</p>}
            </Link>
          ))}
        </div>
      )}
    </>
  )
}

export function ProjectsPage() {
  return (
    <>
      <PageHeader
        title="Projects"
        description="Delivery work across products, with milestones and task status."
      />
      <RequirePermission permission="project.read">
        <ProjectGrid />
      </RequirePermission>
    </>
  )
}
