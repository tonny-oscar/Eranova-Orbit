import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useUserOptions } from '@/features/products/api'
import {
  PRIORITIES,
  PROJECT_STATUSES,
  useCreateTask,
  useProject,
  useProjectActions,
  useTasks,
} from './api'
import { TaskTable } from './TaskList'

function NewTask({ project, onClose }) {
  const users = useUserOptions()
  const create = useCreateTask()
  const [values, setValues] = useState({
    title: '',
    assignee_user_id: '',
    priority: 'medium',
    due_date: '',
    milestone_id: '',
  })
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))
  return (
    <form
      className="mb-4 grid gap-3 rounded-lg border p-3 md:grid-cols-6 md:items-end"
      onSubmit={(e) => {
        e.preventDefault()
        create.mutate(
          {
            project_id: project.id,
            title: values.title.trim(),
            assignee_user_id: values.assignee_user_id || null,
            priority: values.priority,
            due_date: values.due_date || null,
            milestone_id: values.milestone_id || null,
          },
          { onSuccess: onClose },
        )
      }}
    >
      {create.isError && (
        <div className="md:col-span-6">
          <Alert variant="error" title={create.error.message} />
        </div>
      )}
      <div className="space-y-1 md:col-span-2">
        <Label htmlFor="nt-title">Task</Label>
        <Input id="nt-title" value={values.title} onChange={set('title')} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="nt-assignee">Assignee</Label>
        <Select id="nt-assignee" value={values.assignee_user_id} onChange={set('assignee_user_id')}>
          <option value="">Unassigned</option>
          {(
            users.data ?? project.members.map((m) => ({ id: m.user.id, full_name: m.user.name }))
          ).map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="nt-priority">Priority</Label>
        <Select id="nt-priority" value={values.priority} onChange={set('priority')}>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="nt-due">Due</Label>
        <Input id="nt-due" type="date" value={values.due_date} onChange={set('due_date')} />
      </div>
      <div className="flex gap-2">
        <Button
          type="submit"
          size="sm"
          loading={create.isPending}
          disabled={values.title.trim().length < 2}
        >
          Add
        </Button>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

function TeamCard({ project, actions }) {
  const users = useUserOptions()
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState('')
  const memberIds = new Set(project.members.map((m) => m.user.id))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Team</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="divide-y">
          {project.members.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                <span className="font-medium">{m.user.name}</span>{' '}
                <span className="text-muted-foreground">· {m.role_label}</span>
              </span>
              {project.can_update && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${m.user.name}`}
                  onClick={() => actions.removeMember.mutate(m.id)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              )}
            </li>
          ))}
        </ul>
        {project.can_update && users.enabled && (
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              actions.addMember.mutate(
                { user_id: userId, role_label: role.trim() || 'Member' },
                {
                  onSuccess: () => {
                    setUserId('')
                    setRole('')
                  },
                },
              )
            }}
          >
            <div className="flex-1 space-y-1">
              <Label htmlFor="pm-user">Add person</Label>
              <Select id="pm-user" value={userId} onChange={(e) => setUserId(e.target.value)}>
                <option value="">Select…</option>
                {(users.data ?? [])
                  .filter((u) => !memberIds.has(u.id))
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}
                    </option>
                  ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="pm-role">Role</Label>
              <Input
                id="pm-role"
                className="w-36"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              />
            </div>
            <Button type="submit" variant="outline" size="sm" disabled={!userId}>
              Add
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

function MilestonesCard({ project, actions }) {
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  return (
    <Card>
      <CardHeader>
        <CardTitle>Milestones</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {project.milestones.length === 0 && (
          <p className="text-sm text-muted-foreground">No milestones.</p>
        )}
        <ul className="space-y-2">
          {project.milestones.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="size-4 accent-[var(--color-primary)]"
                  checked={Boolean(m.completed_at)}
                  disabled={!project.can_update}
                  onChange={(e) =>
                    actions.updateMilestone.mutate({
                      id: m.id,
                      title: m.title,
                      due_date: m.due_date,
                      completed: e.target.checked,
                    })
                  }
                />
                <span className={m.completed_at ? 'line-through text-muted-foreground' : ''}>
                  {m.title}
                </span>
              </label>
              <span className="text-xs text-muted-foreground">{m.due_date ?? ''}</span>
            </li>
          ))}
        </ul>
        {project.can_update && (
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              actions.addMilestone.mutate(
                { title: title.trim(), due_date: due || null },
                {
                  onSuccess: () => {
                    setTitle('')
                    setDue('')
                  },
                },
              )
            }}
          >
            <div className="flex-1 space-y-1">
              <Label htmlFor="ms-title">Milestone</Label>
              <Input id="ms-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ms-due">Due</Label>
              <Input id="ms-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
            </div>
            <Button type="submit" variant="outline" size="sm" disabled={title.trim().length < 2}>
              Add
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const { data: project, isPending, isError, error, refetch } = useProject(projectId)
  const tasks = useTasks({ project_id: projectId, limit: 100 })
  const actions = useProjectActions(projectId)
  const [adding, setAdding] = useState(false)

  if (isPending) return <LoadingState label="Loading project…" />
  if (isError)
    return <ErrorState title="Couldn't load this project" error={error} onRetry={refetch} />

  return (
    <>
      <Link
        to="/app/projects"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Projects
      </Link>
      <PageHeader title={project.name} description={project.description || undefined} />
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        {project.can_update ? (
          <Select
            aria-label="Project status"
            className="h-8 w-40 text-xs"
            value={project.status}
            onChange={(e) => actions.update.mutate({ status: e.target.value })}
          >
            {PROJECT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace('_', ' ')}
              </option>
            ))}
          </Select>
        ) : (
          <Badge>{project.status}</Badge>
        )}
        <Badge>{project.priority} priority</Badge>
        {project.product && (
          <Link to={`/app/products/${project.product.id}`} className="text-accent hover:underline">
            {project.product.name}
          </Link>
        )}
        {project.due_date && <span className="text-muted-foreground">Due {project.due_date}</span>}
        {project.repository_url && (
          <a
            href={project.repository_url}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
          >
            Repository
          </a>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Tasks</h2>
            {project.can_create_tasks && !adding && (
              <Button size="sm" onClick={() => setAdding(true)}>
                <Plus aria-hidden="true" /> New task
              </Button>
            )}
          </div>
          {adding && <NewTask project={project} onClose={() => setAdding(false)} />}
          {tasks.isPending && <LoadingState />}
          {tasks.data?.items.length === 0 && (
            <EmptyState
              title="No tasks yet"
              description="Break the project into tasks and assign them."
            />
          )}
          {tasks.data?.items.length > 0 && (
            <TaskTable
              tasks={tasks.data.items}
              showProject={false}
              caption={`Tasks in ${project.name}`}
            />
          )}
        </div>
        <div className="space-y-4">
          <TeamCard project={project} actions={actions} />
          <MilestonesCard project={project} actions={actions} />
        </div>
      </div>
    </>
  )
}
