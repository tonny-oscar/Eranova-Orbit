import { Link } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { TASK_STATUS } from './api'

export function TaskStatusBadge({ status }) {
  const meta = TASK_STATUS[status] ?? { label: status, variant: 'default' }
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

export function TaskTable({ tasks, showProject = true, caption = 'Tasks' }) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Task
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
              {showProject && (
                <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                  Project
                </th>
              )}
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Assignee
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Due
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tasks.map((t) => (
              <tr key={t.id} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <Link to={`/app/tasks/${t.id}`} className="font-medium hover:text-accent">
                    {t.title}
                  </Link>
                  <p className="text-xs capitalize text-muted-foreground">{t.priority} priority</p>
                </td>
                <td className="px-4 py-3">
                  <TaskStatusBadge status={t.status} />
                </td>
                {showProject && (
                  <td className="hidden px-4 py-3 md:table-cell">
                    <Link
                      to={`/app/projects/${t.project.id}`}
                      className="text-muted-foreground hover:text-accent"
                    >
                      {t.project.name}
                    </Link>
                  </td>
                )}
                <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                  {t.assignee?.name ?? 'Unassigned'}
                </td>
                <td
                  className={
                    t.is_overdue
                      ? 'px-4 py-3 font-medium text-destructive'
                      : 'px-4 py-3 text-muted-foreground'
                  }
                >
                  {t.due_date ?? '—'}
                  {t.is_overdue ? ' (overdue)' : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
