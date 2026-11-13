import { ListChecks, Search } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useDebounced } from '@/hooks/useDebounced'
import { TASK_STATUS, useTasks } from './api'
import { TaskTable } from './TaskList'

const PAGE_SIZE = 50

export function TasksPage() {
  const [scope, setScope] = useState('mine')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch } = useTasks({
    mine: scope === 'mine',
    open_only: scope !== 'all' && !status,
    overdue: scope === 'overdue',
    status,
    q,
    limit: PAGE_SIZE,
    offset,
  })
  const reset = (setter) => (e) => {
    setter(e.target.value)
    setOffset(0)
  }

  return (
    <>
      <PageHeader
        title="Tasks"
        description="Your assignments and the work you can see across projects."
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="task-scope">Show</Label>
          <Select id="task-scope" className="w-48" value={scope} onChange={reset(setScope)}>
            <option value="mine">My open tasks</option>
            <option value="open">All open tasks</option>
            <option value="overdue">Overdue</option>
            <option value="all">Everything</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="task-status">Status</Label>
          <Select id="task-status" className="w-48" value={status} onChange={reset(setStatus)}>
            <option value="">Any</option>
            {Object.entries(TASK_STATUS).map(([value, meta]) => (
              <option key={value} value={value}>
                {meta.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="task-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="task-search"
              type="search"
              className="w-64 pl-9"
              value={search}
              onChange={reset(setSearch)}
            />
          </div>
        </div>
      </div>
      {isPending && <LoadingState label="Loading tasks…" />}
      {isError && <ErrorState title="Couldn't load tasks" error={error} onRetry={refetch} />}
      {data?.items.length === 0 && (
        <EmptyState
          icon={ListChecks}
          title="Nothing here"
          description="No tasks match this view."
        />
      )}
      {data?.items.length > 0 && (
        <>
          <TaskTable tasks={data.items} />
          <div className="mt-3 flex justify-end gap-2">
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
        </>
      )}
    </>
  )
}
