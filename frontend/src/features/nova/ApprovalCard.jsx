import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { APPROVAL_STATUS, useDecideApproval } from './api'

export function ApprovalCard({ approval, timeZone }) {
  const decide = useDecideApproval()
  const [note, setNote] = useState('')
  const status = APPROVAL_STATUS[approval.status] ?? { label: approval.status }
  const result = decide.data ?? approval
  const selfConfirm = approval.policy === 'self_confirm'
  return (
    <div className="space-y-2 rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="flex items-center gap-2 font-medium">
          <ShieldCheck className="size-4 text-warning" aria-hidden="true" />
          {approval.summary}
        </p>
        <Badge variant={(APPROVAL_STATUS[result.status] ?? status).variant}>
          {(APPROVAL_STATUS[result.status] ?? status).label}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        {approval.reason} Requested by {approval.requester?.name ?? 'someone'} ·{' '}
        {selfConfirm ? 'needs your confirmation' : 'needs another administrator'} · expires{' '}
        {new Date(approval.expires_at).toLocaleString(undefined, { timeZone })}
      </p>
      <details className="text-xs">
        <summary className="cursor-pointer text-muted-foreground">Exact parameters</summary>
        <pre className="mt-1 overflow-x-auto rounded bg-muted/50 p-2">
          {JSON.stringify(approval.arguments, null, 2)}
        </pre>
      </details>
      {result.result_summary && (
        <p className={result.status === 'failed' ? 'text-destructive' : 'text-success'}>
          {result.result_summary}
        </p>
      )}
      {decide.isError && <Alert variant="error" title={decide.error.message} />}
      {approval.can_decide && result.status === 'pending' && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-48 flex-1 space-y-1">
            <Label htmlFor={`note-${approval.id}`} className="text-xs">
              Note (optional)
            </Label>
            <Input
              id={`note-${approval.id}`}
              value={note}
              maxLength={500}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            loading={decide.isPending && decide.variables?.approve}
            onClick={() => decide.mutate({ id: approval.id, approve: true, note })}
          >
            {selfConfirm ? 'Confirm' : 'Approve'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            loading={decide.isPending && decide.variables?.approve === false}
            onClick={() => decide.mutate({ id: approval.id, approve: false, note })}
          >
            {selfConfirm ? 'Cancel' : 'Reject'}
          </Button>
        </div>
      )}
    </div>
  )
}
