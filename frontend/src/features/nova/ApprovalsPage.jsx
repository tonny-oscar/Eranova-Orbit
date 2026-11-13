import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Select } from '@/components/ui/form-controls'
import { Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { useApprovals } from './api'
import { ApprovalCard } from './ApprovalCard'

export function ApprovalsPage() {
  const { data: me } = useMe()
  const [status, setStatus] = useState('pending')
  const { data, isPending, isError, error, refetch } = useApprovals(status || undefined)
  return (
    <>
      <Link
        to="/app/nova"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> NOVA
      </Link>
      <PageHeader
        title="NOVA approvals"
        description="Actions NOVA prepared that need a person to confirm or approve. Each is bound to the exact parameters shown."
      />
      <div className="mb-4 space-y-1.5">
        <Label htmlFor="approval-status">Show</Label>
        <Select
          id="approval-status"
          className="w-48"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="pending">Pending</option>
          <option value="executed">Done</option>
          <option value="rejected">Rejected</option>
          <option value="failed">Failed</option>
          <option value="expired">Expired</option>
          <option value="">Everything</option>
        </Select>
      </div>
      {isPending && <LoadingState label="Loading approvals…" />}
      {isError && <ErrorState title="Couldn't load approvals" error={error} onRetry={refetch} />}
      {data?.length === 0 && (
        <EmptyState
          icon={ShieldCheck}
          title="Nothing here"
          description="No approvals match this view."
        />
      )}
      <div className="space-y-3">
        {(data ?? []).map((a) => (
          <ApprovalCard key={a.id} approval={a} timeZone={me.company.timezone} />
        ))}
      </div>
    </>
  )
}
