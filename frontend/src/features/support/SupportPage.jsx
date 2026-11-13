import { Download, LifeBuoy, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState, Skeleton } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { formatDateTime } from '@/lib/utils'
import {
  CATEGORIES,
  CHANNELS,
  PRIORITIES,
  PRIORITY_VARIANT,
  TICKET_STATUS,
  TICKET_STATUSES,
  label,
  useCreateTicket,
  useSupportMetrics,
  useTickets,
} from './api'

function Metrics() {
  const { data, isPending } = useSupportMetrics(30)
  if (isPending) return <Skeleton className="mb-4 h-20" />
  if (!data) return null
  const hours = (v) => (v == null ? '—' : `${v} h`)
  const tiles = [
    ['Open now', data.open],
    ['Created (30 days)', data.created],
    ['Resolved (30 days)', data.resolved],
    ['Median first response', hours(data.median_first_response_hours)],
    ['Median time to resolve', hours(data.median_resolution_hours)],
  ]
  return (
    <dl className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
      {tiles.map(([title, value]) => (
        <Card key={title}>
          <CardContent className="pt-4">
            <dt className="text-xs text-muted-foreground">{title}</dt>
            <dd className="text-xl font-semibold">{value}</dd>
          </CardContent>
        </Card>
      ))}
    </dl>
  )
}

function NewTicket({ onClose }) {
  const navigate = useNavigate()
  const create = useCreateTicket()
  const products = useProductOptions()
  const [form, setForm] = useState({
    subject: '',
    description: '',
    requester_name: '',
    requester_email: '',
    product_id: '',
    category: 'question',
    priority: 'medium',
    channel: 'email',
  })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                ...form,
                subject: form.subject.trim(),
                requester_name: form.requester_name.trim() || null,
                requester_email: form.requester_email.trim() || null,
                product_id: form.product_id || null,
              },
              { onSuccess: (t) => navigate(`/app/support/${t.id}`) },
            )
          }}
        >
          {create.isError && (
            <div className="md:col-span-2">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="t-subject">Subject</Label>
            <Input id="t-subject" value={form.subject} onChange={set('subject')} />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="t-description">Description</Label>
            <Textarea
              id="t-description"
              rows={4}
              value={form.description}
              onChange={set('description')}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="t-name">Requester name</Label>
            <Input id="t-name" value={form.requester_name} onChange={set('requester_name')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="t-email">Requester email</Label>
            <Input
              id="t-email"
              type="email"
              value={form.requester_email}
              onChange={set('requester_email')}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="t-product">Product</Label>
            <Select id="t-product" value={form.product_id} onChange={set('product_id')}>
              <option value="">Not product-specific</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              ['category', CATEGORIES],
              ['priority', PRIORITIES],
              ['channel', CHANNELS],
            ].map(([key, options]) => (
              <div key={key} className="space-y-1.5">
                <Label htmlFor={`t-${key}`}>{label(key)}</Label>
                <Select id={`t-${key}`} value={form[key]} onChange={set(key)}>
                  {options.map((o) => (
                    <option key={o} value={o}>
                      {label(o)}
                    </option>
                  ))}
                </Select>
              </div>
            ))}
          </div>
          <div className="flex gap-2 md:col-span-2">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={form.subject.trim().length < 3}
            >
              Create ticket
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

function TicketQueue() {
  const { has } = usePermissions()
  const { data: me } = useMe()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [view, setView] = useState('open')
  const [creating, setCreating] = useState(false)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch } = useTickets({
    q,
    status,
    open_only: view === 'open' && !status ? true : undefined,
    assignee: view === 'me' || view === 'unassigned' ? view : undefined,
    limit: 100,
  })
  return (
    <>
      <Metrics />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="ticket-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="ticket-search"
              type="search"
              className="w-60 pl-9"
              placeholder="T-1001, subject or email"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ticket-view">View</Label>
          <Select
            id="ticket-view"
            className="w-40"
            value={view}
            onChange={(e) => setView(e.target.value)}
          >
            <option value="open">All open</option>
            <option value="me">Assigned to me</option>
            <option value="unassigned">Unassigned</option>
            <option value="all">Everything</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ticket-status">Status</Label>
          <Select
            id="ticket-status"
            className="w-48"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Any</option>
            {TICKET_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-auto flex gap-2">
          {has('ticket.export') && (
            <a
              href="/api/v1/support/tickets/export.csv"
              className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs hover:bg-muted"
            >
              <Download className="size-4" aria-hidden="true" /> Export CSV
            </a>
          )}
          {has('ticket.create') && !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" /> New ticket
            </Button>
          )}
        </div>
      </div>
      {creating && <NewTicket onClose={() => setCreating(false)} />}
      {isPending && <LoadingState label="Loading tickets…" />}
      {isError && <ErrorState title="Couldn't load tickets" error={error} onRetry={refetch} />}
      {data?.items.length === 0 && (
        <EmptyState
          icon={LifeBuoy}
          title="No tickets here"
          description="Nothing matches this view."
        />
      )}
      {data?.items.length > 0 && (
        <Card className="overflow-hidden">
          <ul className="divide-y">
            {data.items.map((t) => (
              <li
                key={t.id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
              >
                <div className="min-w-0">
                  <Link to={`/app/support/${t.id}`} className="font-medium hover:text-accent">
                    <span className="text-muted-foreground">{t.reference}</span> {t.subject}
                  </Link>
                  <p className="text-xs text-muted-foreground">
                    {[
                      t.product?.name,
                      t.customer?.name ?? t.requester_email,
                      t.assignee?.name ?? 'Unassigned',
                    ]
                      .filter(Boolean)
                      .join(' · ')}{' '}
                    · updated {formatDateTime(t.updated_at, me.company.timezone)}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Badge variant={PRIORITY_VARIANT[t.priority]}>{label(t.priority)}</Badge>
                  <Badge variant={TICKET_STATUS[t.status]?.variant}>
                    {TICKET_STATUS[t.status]?.label}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  )
}

export function SupportPage() {
  return (
    <>
      <PageHeader title="Support" description="Customer tickets across every product." />
      <RequirePermission permission="ticket.read">
        <TicketQueue />
      </RequirePermission>
    </>
  )
}
