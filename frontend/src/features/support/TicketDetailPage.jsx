import { ArrowLeft, Lock } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { useUserOptions } from '@/features/products/api'
import { cn, formatDateTime } from '@/lib/utils'
import {
  CATEGORIES,
  PRIORITIES,
  PRIORITY_VARIANT,
  TICKET_STATUS,
  label,
  useTicket,
  useTicketActions,
} from './api'

function Composer({ ticket }) {
  const { message } = useTicketActions(ticket.id)
  const [body, setBody] = useState('')
  const [mode, setMode] = useState('reply')
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        message.mutate(
          { body, internal: mode === 'note', from_customer: mode === 'customer' },
          { onSuccess: () => setBody('') },
        )
      }}
    >
      {message.isError && <Alert variant="error" title={message.error.message} />}
      <div className="flex gap-1 text-xs" role="radiogroup" aria-label="Message type">
        {[
          ['reply', 'Reply sent to customer'],
          ['note', 'Internal note'],
          ['customer', 'Log customer message'],
        ].map(([value, text]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={mode === value}
            onClick={() => setMode(value)}
            className={cn(
              'rounded-md border px-2 py-1',
              mode === value ? 'border-accent bg-accent/15' : 'border-input text-muted-foreground',
            )}
          >
            {text}
          </button>
        ))}
      </div>
      <Label htmlFor="ticket-message" className="sr-only">
        Message
      </Label>
      <Textarea
        id="ticket-message"
        rows={4}
        value={body}
        placeholder={mode === 'note' ? 'Only staff can see this.' : 'Write a message…'}
        onChange={(e) => setBody(e.target.value)}
      />
      <p className="text-xs text-muted-foreground">
        Orbit records the conversation. Send the reply through your usual channel (email, WhatsApp,
        phone) until a messaging integration is connected.
      </p>
      <Button type="submit" size="sm" loading={message.isPending} disabled={!body.trim()}>
        Add {mode === 'note' ? 'note' : 'message'}
      </Button>
    </form>
  )
}

function StatusControl({ ticket }) {
  const { transition } = useTicketActions(ticket.id)
  const [target, setTarget] = useState('')
  const [resolution, setResolution] = useState(ticket.resolution ?? '')
  const needsResolution = target === 'resolved' || target === 'closed'
  if (!ticket.allowed_statuses.length) return null
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        transition.mutate(
          { status: target, resolution: needsResolution ? resolution : null },
          { onSuccess: () => setTarget('') },
        )
      }}
    >
      {transition.isError && <Alert variant="error" title={transition.error.message} />}
      <Label htmlFor="ticket-status">Move to</Label>
      <Select id="ticket-status" value={target} onChange={(e) => setTarget(e.target.value)}>
        <option value="">Choose a status…</option>
        {ticket.allowed_statuses.map((s) => (
          <option key={s} value={s}>
            {TICKET_STATUS[s]?.label}
          </option>
        ))}
      </Select>
      {needsResolution && (
        <>
          <Label htmlFor="ticket-resolution">Resolution</Label>
          <Textarea
            id="ticket-resolution"
            rows={3}
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
          />
        </>
      )}
      <Button
        type="submit"
        size="sm"
        disabled={!target || (needsResolution && !resolution.trim())}
        loading={transition.isPending}
      >
        Update status
      </Button>
    </form>
  )
}

function Properties({ ticket }) {
  const { update } = useTicketActions(ticket.id)
  const users = useUserOptions()
  const change = (field) => (e) => update.mutate({ [field]: e.target.value || null })
  return (
    <div className="space-y-3 text-sm">
      {update.isError && <Alert variant="error" title={update.error.message} />}
      {users.enabled && (
        <div className="space-y-1.5">
          <Label htmlFor="ticket-assignee">Assignee</Label>
          <Select
            id="ticket-assignee"
            value={ticket.assignee?.id ?? ''}
            disabled={!ticket.can_update}
            onChange={change('assignee_user_id')}
          >
            <option value="">Unassigned</option>
            {(users.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </Select>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <Label htmlFor="ticket-priority">Priority</Label>
          <Select
            id="ticket-priority"
            value={ticket.priority}
            disabled={!ticket.can_update}
            onChange={change('priority')}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {label(p)}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ticket-category">Category</Label>
          <Select
            id="ticket-category"
            value={ticket.category}
            disabled={!ticket.can_update}
            onChange={change('category')}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {label(c)}
              </option>
            ))}
          </Select>
        </div>
      </div>
    </div>
  )
}

export function TicketDetailPage() {
  const { ticketId } = useParams()
  const { data: me } = useMe()
  const tz = me.company.timezone
  const { data: t, isPending, isError, error, refetch } = useTicket(ticketId)
  if (isPending) return <LoadingState label="Loading ticket…" />
  if (isError) return <ErrorState title="Couldn't load ticket" error={error} onRetry={refetch} />
  return (
    <>
      <Link
        to="/app/support"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Support
      </Link>
      <PageHeader
        title={`${t.reference} · ${t.subject}`}
        description={[t.product?.name, t.customer?.name, t.requester_name, t.requester_email]
          .filter(Boolean)
          .join(' · ')}
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Badge variant={TICKET_STATUS[t.status]?.variant}>{TICKET_STATUS[t.status]?.label}</Badge>
        <Badge variant={PRIORITY_VARIANT[t.priority]}>{label(t.priority)}</Badge>
        <Badge>{label(t.category)}</Badge>
        <Badge>via {label(t.channel)}</Badge>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Conversation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {t.description && (
                <div className="rounded-md bg-muted/40 p-3 text-sm">
                  <p className="mb-1 text-xs text-muted-foreground">
                    Original request · {formatDateTime(t.created_at, tz)}
                  </p>
                  <p className="whitespace-pre-wrap">{t.description}</p>
                </div>
              )}
              <ol className="space-y-3">
                {t.messages.map((m) => (
                  <li
                    key={m.id}
                    className={cn(
                      'rounded-md border p-3 text-sm',
                      m.internal && 'border-warning/40 bg-warning/5',
                      m.from_customer && 'bg-muted/40',
                    )}
                  >
                    <p className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
                      {m.internal && <Lock className="size-3" aria-label="Internal note" />}
                      {m.from_customer ? 'Customer' : (m.author?.name ?? 'Staff')}
                      {m.from_customer && m.author ? ` (logged by ${m.author.name})` : ''} ·{' '}
                      {formatDateTime(m.created_at, tz)}
                    </p>
                    <p className="whitespace-pre-wrap">{m.body}</p>
                  </li>
                ))}
              </ol>
              {t.can_update && <Composer ticket={t} />}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Ticket</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Properties ticket={t} />
              <StatusControl key={t.status} ticket={t} />
              {t.resolution && (
                <div className="text-sm">
                  <p className="text-muted-foreground">Resolution</p>
                  <p className="whitespace-pre-wrap">{t.resolution}</p>
                </div>
              )}
              <dl className="space-y-1 text-xs text-muted-foreground">
                <div>
                  First response:{' '}
                  {t.first_response_at ? formatDateTime(t.first_response_at, tz) : 'not yet'}
                </div>
                {t.resolved_at && <div>Resolved: {formatDateTime(t.resolved_at, tz)}</div>}
                {t.closed_at && <div>Closed: {formatDateTime(t.closed_at, tz)}</div>}
              </dl>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-1.5 text-xs">
                {t.events.map((e) => (
                  <li key={e.id}>
                    <span className="text-muted-foreground">
                      {formatDateTime(e.created_at, tz)}
                    </span>{' '}
                    {e.actor?.name ?? 'System'}{' '}
                    {e.kind === 'created'
                      ? 'created the ticket'
                      : e.kind === 'assignee'
                        ? 'changed the assignee'
                        : `changed ${e.kind} ${e.from_value ? `from ${label(e.from_value)} ` : ''}to ${label(e.to_value ?? '')}`}
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
