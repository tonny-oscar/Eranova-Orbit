import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { useUserOptions } from '@/features/products/api'
import { formatDateTime } from '@/lib/utils'
import { LINK_KINDS, PRIORITIES, TRANSITION_LABELS, useTask, useTaskActions, useTasks } from './api'
import { TaskStatusBadge } from './TaskList'

function WorkflowCard({ task, actions }) {
  const [note, setNote] = useState('')
  const [comment, setComment] = useState('')
  const error = actions.transition.error ?? actions.review.error
  return (
    <Card>
      <CardHeader>
        <CardTitle>Workflow</CardTitle>
        <CardDescription>
          Linked pull requests are evidence; completion needs a human review.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && <Alert variant="error" title={error.message} />}
        {task.allowed_transitions.length > 0 && (
          <>
            {task.allowed_transitions.includes('submitted') && (
              <div className="space-y-1">
                <Label htmlFor="transition-note">Note for the reviewer (optional)</Label>
                <Textarea
                  id="transition-note"
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {task.allowed_transitions.map((to) => (
                <Button
                  key={to}
                  size="sm"
                  variant={to === 'cancelled' ? 'outline' : 'default'}
                  loading={actions.transition.isPending && actions.transition.variables?.to === to}
                  onClick={() =>
                    actions.transition.mutate(
                      { to, note: note.trim() || null },
                      { onSuccess: () => setNote('') },
                    )
                  }
                >
                  {TRANSITION_LABELS[to]}
                </Button>
              ))}
            </div>
          </>
        )}
        {task.can_review && (
          <div className="space-y-2 border-t pt-3">
            <Label htmlFor="review-comment">Review comment</Label>
            <Textarea
              id="review-comment"
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="accent"
                loading={actions.review.isPending}
                onClick={() => actions.review.mutate({ decision: 'approved', comment })}
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!comment.trim()}
                onClick={() => actions.review.mutate({ decision: 'revision_requested', comment })}
              >
                Request revision
              </Button>
            </div>
          </div>
        )}
        {task.allowed_transitions.length === 0 && !task.can_review && (
          <p className="text-sm text-muted-foreground">
            No workflow actions available to you right now.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function DetailsCard({ task, actions }) {
  const users = useUserOptions()
  const [values, setValues] = useState({
    assignee_user_id: task.assignee?.id ?? '',
    priority: task.priority,
    due_date: task.due_date ?? '',
    estimate_hours: task.estimate_hours ?? '',
  })
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Details</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            actions.update.mutate({
              assignee_user_id: values.assignee_user_id || null,
              priority: values.priority,
              due_date: values.due_date || null,
              estimate_hours: values.estimate_hours === '' ? null : values.estimate_hours,
            })
          }}
        >
          {actions.update.isError && <Alert variant="error" title={actions.update.error.message} />}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="td-assignee">Assignee</Label>
              <Select
                id="td-assignee"
                value={values.assignee_user_id}
                onChange={set('assignee_user_id')}
                disabled={!task.can_update || !users.enabled}
              >
                <option value="">
                  {users.enabled ? 'Unassigned' : (task.assignee?.name ?? 'Unassigned')}
                </option>
                {(users.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="td-priority">Priority</Label>
              <Select
                id="td-priority"
                value={values.priority}
                onChange={set('priority')}
                disabled={!task.can_update}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="td-due">Due date</Label>
              <Input
                id="td-due"
                type="date"
                value={values.due_date}
                onChange={set('due_date')}
                disabled={!task.can_update}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="td-estimate">Estimate (hours)</Label>
              <Input
                id="td-estimate"
                inputMode="decimal"
                value={values.estimate_hours}
                onChange={set('estimate_hours')}
                disabled={!task.can_update}
              />
            </div>
          </div>
          {task.can_update && (
            <Button type="submit" size="sm" loading={actions.update.isPending}>
              Save
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

function DependenciesCard({ task, actions }) {
  const siblings = useTasks({ project_id: task.project.id, limit: 100, top_level: false })
  const [dep, setDep] = useState('')
  const taken = new Set([task.id, ...task.depends_on.map((d) => d.id)])
  return (
    <Card>
      <CardHeader>
        <CardTitle>Depends on</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {actions.addDependency.isError && (
          <Alert variant="error" title={actions.addDependency.error.message} />
        )}
        {task.depends_on.length === 0 && (
          <p className="text-sm text-muted-foreground">No dependencies.</p>
        )}
        <ul className="space-y-1 text-sm">
          {task.depends_on.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2">
              <Link to={`/app/tasks/${d.id}`} className="hover:text-accent">
                {d.title}
              </Link>
              <TaskStatusBadge status={d.status} />
            </li>
          ))}
        </ul>
        {task.can_update && (
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              actions.addDependency.mutate(dep, { onSuccess: () => setDep('') })
            }}
          >
            <Select
              aria-label="Add dependency"
              value={dep}
              onChange={(e) => setDep(e.target.value)}
            >
              <option value="">Add a task this depends on…</option>
              {(siblings.data?.items ?? [])
                .filter((t) => !taken.has(t.id))
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
            </Select>
            <Button type="submit" size="sm" variant="outline" disabled={!dep}>
              Add
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

function LinksCard({ task, actions }) {
  const [kind, setKind] = useState('github_pr')
  const [url, setUrl] = useState('')
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence and links</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {actions.addLink.isError && <Alert variant="error" title={actions.addLink.error.message} />}
        {task.links.length === 0 && <p className="text-sm text-muted-foreground">No links yet.</p>}
        <ul className="space-y-1 text-sm">
          {task.links.map((l) => (
            <li key={l.id}>
              <a
                href={l.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-accent hover:underline"
              >
                {l.title ?? l.url} <ExternalLink className="size-3" aria-hidden="true" />
              </a>{' '}
              <span className="text-xs text-muted-foreground">
                ({LINK_KINDS.find((k) => k.value === l.kind)?.label})
              </span>
            </li>
          ))}
        </ul>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            actions.addLink.mutate({ kind, url: url.trim() }, { onSuccess: () => setUrl('') })
          }}
        >
          <Select
            aria-label="Link type"
            className="w-36"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            {LINK_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </Select>
          <Input
            aria-label="Link URL"
            className="flex-1"
            placeholder="https://"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <Button type="submit" size="sm" variant="outline" disabled={!url.startsWith('http')}>
            Add
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export function TaskDetailPage() {
  const { taskId } = useParams()
  const { data: me } = useMe()
  const { data: task, isPending, isError, error, refetch } = useTask(taskId)
  const actions = useTaskActions(taskId)
  const [comment, setComment] = useState('')
  const tz = me.company.timezone

  if (isPending) return <LoadingState label="Loading task…" />
  if (isError) return <ErrorState title="Couldn't load this task" error={error} onRetry={refetch} />

  return (
    <>
      <Link
        to={`/app/projects/${task.project.id}`}
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> {task.project.name}
      </Link>
      <PageHeader title={task.title} />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <TaskStatusBadge status={task.status} />
        <Badge>{task.priority} priority</Badge>
        {task.is_overdue && <Badge variant="destructive">Overdue</Badge>}
        <span className="text-muted-foreground">
          Reported by {task.reporter?.name ?? 'unknown'}
        </span>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-line text-sm text-muted-foreground">
                {task.description || 'No description.'}
              </p>
            </CardContent>
          </Card>
          {task.subtasks.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Subtasks</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 text-sm">
                  {task.subtasks.map((s) => (
                    <li key={s.id} className="flex justify-between gap-2">
                      <Link to={`/app/tasks/${s.id}`} className="hover:text-accent">
                        {s.title}
                      </Link>
                      <TaskStatusBadge status={s.status} />
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>Discussion</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {task.comments.length === 0 && (
                <p className="text-sm text-muted-foreground">No comments yet.</p>
              )}
              <ol className="space-y-3">
                {task.comments.map((c) => (
                  <li key={c.id} className="text-sm">
                    <p className="font-medium">
                      {c.author?.name ?? 'Someone'}{' '}
                      <span className="text-xs font-normal text-muted-foreground">
                        {formatDateTime(c.created_at, tz)}
                      </span>
                    </p>
                    <p className="whitespace-pre-line text-muted-foreground">{c.body}</p>
                  </li>
                ))}
              </ol>
              <form
                className="space-y-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  actions.comment.mutate(comment.trim(), { onSuccess: () => setComment('') })
                }}
              >
                <Label htmlFor="task-comment">Add a comment</Label>
                <Textarea
                  id="task-comment"
                  rows={2}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
                <Button
                  type="submit"
                  size="sm"
                  variant="outline"
                  disabled={!comment.trim()}
                  loading={actions.comment.isPending}
                >
                  Comment
                </Button>
              </form>
            </CardContent>
          </Card>
          {task.reviews.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Review history</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2 text-sm">
                  {task.reviews.map((r) => (
                    <li key={r.id}>
                      <Badge variant={r.decision === 'approved' ? 'success' : 'destructive'}>
                        {r.decision.replace('_', ' ')}
                      </Badge>{' '}
                      by {r.reviewer?.name ?? 'reviewer'} · {formatDateTime(r.created_at, tz)}
                      {r.comment && <p className="mt-1 text-muted-foreground">{r.comment}</p>}
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}
        </div>
        <div className="space-y-4">
          <WorkflowCard task={task} actions={actions} />
          <DetailsCard key={task.updated_at} task={task} actions={actions} />
          <DependenciesCard task={task} actions={actions} />
          <LinksCard task={task} actions={actions} />
          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-1 text-xs text-muted-foreground">
                {task.events.map((e) => (
                  <li key={e.id}>
                    {formatDateTime(e.created_at, tz)} · {e.actor?.name ?? 'System'} · {e.kind}
                    {e.to_value ? `: ${e.from_value ? `${e.from_value} → ` : ''}${e.to_value}` : ''}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
