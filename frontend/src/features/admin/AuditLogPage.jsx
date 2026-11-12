import { ScrollText } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { useAuditLogs } from './api'

const PAGE_SIZE = 25
const OUTCOME_VARIANT = { success: 'success', failure: 'warning', denied: 'destructive' }

function AuditLogTable() {
  const { data: me } = useMe()
  const [actionInput, setActionInput] = useState('')
  const [filters, setFilters] = useState({ limit: PAGE_SIZE, offset: 0, action: '' })
  const { data, isPending, isError, error, refetch, isFetching } = useAuditLogs(filters)

  const applyFilter = (event) => {
    event.preventDefault()
    setFilters({ limit: PAGE_SIZE, offset: 0, action: actionInput.trim() })
  }

  return (
    <div className="space-y-4">
      <form onSubmit={applyFilter} className="flex flex-wrap items-end gap-2">
        <div className="space-y-1.5">
          <Label htmlFor="audit-action">Action</Label>
          <Input
            id="audit-action"
            placeholder="e.g. auth.login.failed"
            value={actionInput}
            onChange={(e) => setActionInput(e.target.value)}
            className="w-64"
          />
        </div>
        <Button type="submit" variant="outline">
          Filter
        </Button>
      </form>

      {isPending && <LoadingState label="Loading audit events…" />}
      {isError && <ErrorState title="Couldn't load audit events" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState
          icon={ScrollText}
          title="No audit events match"
          description="Try a different action filter."
        />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">Audit events, newest first</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Time
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Action
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Outcome
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Actor
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Resource
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    IP
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((event) => (
                  <tr key={event.id} className="hover:bg-muted/30">
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                      {formatDateTime(event.created_at, me.company.timezone)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{event.action}</td>
                    <td className="px-4 py-3">
                      <Badge variant={OUTCOME_VARIANT[event.outcome]}>{event.outcome}</Badge>
                    </td>
                    <td className="hidden px-4 py-3 font-mono text-xs text-muted-foreground md:table-cell">
                      {event.actor_type}
                      {event.actor_user_id ? ` · ${event.actor_user_id.slice(0, 8)}` : ''}
                    </td>
                    <td className="hidden px-4 py-3 font-mono text-xs text-muted-foreground lg:table-cell">
                      {event.resource_type
                        ? `${event.resource_type} · ${event.resource_id?.slice(0, 8)}`
                        : '—'}
                    </td>
                    <td className="hidden px-4 py-3 font-mono text-xs text-muted-foreground lg:table-cell">
                      {event.ip_address ?? '—'}
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
                disabled={data.offset === 0}
                onClick={() =>
                  setFilters((f) => ({ ...f, offset: Math.max(0, f.offset - PAGE_SIZE) }))
                }
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={data.offset + data.items.length >= data.total}
                onClick={() => setFilters((f) => ({ ...f, offset: f.offset + PAGE_SIZE }))}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

export function AuditLogPage() {
  return (
    <>
      <PageHeader
        title="Audit log"
        description="Append-only record of sign-ins, access denials and privileged changes."
      />
      <RequirePermission permission="audit_log.read">
        <AuditLogTable />
      </RequirePermission>
    </>
  )
}
