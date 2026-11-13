import { Download, Inbox, KanbanSquare, List, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { FieldError, Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { formatDateTime } from '@/lib/utils'
import {
  SOURCE_LABELS,
  stageVariant,
  useCreateLead,
  useLeads,
  useStages,
  useUpdateLead,
} from './api'

const PAGE_SIZE = 25

function NewLeadCard({ onClose }) {
  const products = useProductOptions()
  const create = useCreateLead()
  const [values, setValues] = useState({
    full_name: '',
    email: '',
    organization: '',
    phone: '',
    product_id: '',
  })
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))
  const emailInvalid = values.email && !/^\S+@\S+\.\S+$/.test(values.email)

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>New lead</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                full_name: values.full_name.trim(),
                email: values.email.trim(),
                organization: values.organization.trim() || null,
                phone: values.phone.trim() || null,
                product_id: values.product_id || null,
              },
              { onSuccess: onClose },
            )
          }}
        >
          {create.isError && (
            <div className="md:col-span-3">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="new-lead-name">Name</Label>
            <Input id="new-lead-name" value={values.full_name} onChange={set('full_name')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-lead-email">Email</Label>
            <Input
              id="new-lead-email"
              type="email"
              value={values.email}
              onChange={set('email')}
              aria-invalid={emailInvalid || undefined}
            />
            <FieldError>{emailInvalid ? 'Enter a valid email address.' : null}</FieldError>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-lead-org">Organisation</Label>
            <Input id="new-lead-org" value={values.organization} onChange={set('organization')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-lead-phone">Phone</Label>
            <Input id="new-lead-phone" value={values.phone} onChange={set('phone')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-lead-product">Product</Label>
            <Select id="new-lead-product" value={values.product_id} onChange={set('product_id')}>
              <option value="">Not specified</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-end gap-2">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={values.full_name.trim().length < 2 || !values.email || emailInvalid}
            >
              Create lead
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

function BoardCard({ lead, stages }) {
  const update = useUpdateLead(lead.id)
  return (
    <li className="space-y-2 rounded-lg border bg-card p-3 text-sm">
      <Link to={`/app/leads/${lead.id}`} className="font-medium hover:text-accent">
        {lead.full_name}
      </Link>
      <p className="text-xs text-muted-foreground">{lead.organization ?? lead.email}</p>
      {lead.product && <Badge>{lead.product.name}</Badge>}
      <Select
        aria-label={`Move ${lead.full_name} to stage`}
        className="h-8 text-xs"
        value={lead.status}
        disabled={update.isPending}
        onChange={(e) => update.mutate({ status: e.target.value })}
      >
        {stages.map((s) => (
          <option key={s.key} value={s.key}>
            {s.name}
          </option>
        ))}
      </Select>
    </li>
  )
}

function Board({ leads, stages }) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {stages.map((stage) => {
        const items = leads.filter((l) => l.status === stage.key)
        return (
          <section
            key={stage.key}
            aria-label={stage.name}
            className="w-64 shrink-0 rounded-xl bg-muted/40 p-3"
          >
            <h3 className="mb-2 flex items-center justify-between text-sm font-semibold">
              {stage.name} <Badge variant={stageVariant(stage)}>{items.length}</Badge>
            </h3>
            <ul className="space-y-2">
              {items.map((lead) => (
                <BoardCard key={lead.id} lead={lead} stages={stages} />
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

function LeadsTable() {
  const { data: me } = useMe()
  const { has } = usePermissions()
  const products = useProductOptions()
  const stages = useStages()
  const stageMap = Object.fromEntries((stages.data ?? []).map((s) => [s.key, s]))
  const [view, setView] = useState('list')
  const [creating, setCreating] = useState(false)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [productId, setProductId] = useState('')
  const [offset, setOffset] = useState(0)
  const q = useDebounced(search.trim())
  const limit = view === 'board' ? 100 : PAGE_SIZE
  const { data, isPending, isError, error, refetch, isFetching } = useLeads({
    q,
    status: view === 'board' ? '' : status,
    product_id: productId,
    limit,
    offset: view === 'board' ? 0 : offset,
  })
  const reset = (setter) => (e) => {
    setter(e.target.value)
    setOffset(0)
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="lead-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="lead-search"
              type="search"
              placeholder="Name, email or organisation"
              className="w-64 pl-9"
              value={search}
              onChange={reset(setSearch)}
            />
          </div>
        </div>
        {view === 'list' && (
          <div className="space-y-1.5">
            <Label htmlFor="lead-status">Stage</Label>
            <Select id="lead-status" className="w-44" value={status} onChange={reset(setStatus)}>
              <option value="">All</option>
              {(stages.data ?? []).map((s) => (
                <option key={s.key} value={s.key}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="lead-product">Product</Label>
          <Select
            id="lead-product"
            className="w-44"
            value={productId}
            onChange={reset(setProductId)}
          >
            <option value="">All products</option>
            {(products.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setView(view === 'list' ? 'board' : 'list')}
          >
            {view === 'list' ? <KanbanSquare aria-hidden="true" /> : <List aria-hidden="true" />}
            {view === 'list' ? 'Pipeline board' : 'List view'}
          </Button>
          {has('lead.export') && (
            <a
              href="/api/v1/leads/export.csv"
              className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs hover:bg-muted"
            >
              <Download className="size-4" aria-hidden="true" /> Export CSV
            </a>
          )}
          {has('lead.create') && !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" /> New lead
            </Button>
          )}
        </div>
      </div>

      {creating && <NewLeadCard onClose={() => setCreating(false)} />}
      {isPending && <LoadingState label="Loading leads…" />}
      {isError && <ErrorState title="Couldn't load leads" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState
          icon={Inbox}
          title={q || status || productId ? 'No leads match these filters' : 'No leads yet'}
          description="Enquiries from the website arrive here automatically, or add a lead yourself."
        />
      )}
      {data && data.items.length > 0 && view === 'board' && (
        <Board leads={data.items} stages={stages.data ?? []} />
      )}
      {data && data.items.length > 0 && view === 'list' && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">Leads, most recent activity first</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Lead
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Stage
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Product
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Source
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Last activity
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((lead) => (
                  <tr key={lead.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link to={`/app/leads/${lead.id}`} className="font-medium hover:text-accent">
                        {lead.full_name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {lead.organization ?? lead.email}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={stageVariant(stageMap[lead.status])}>
                        {stageMap[lead.status]?.name ?? lead.status}
                      </Badge>
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                      {lead.product?.name ?? 'Not specified'}
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                      {SOURCE_LABELS[lead.source] ?? lead.source}
                    </td>
                    <td className="hidden whitespace-nowrap px-4 py-3 text-muted-foreground lg:table-cell">
                      {formatDateTime(lead.last_enquiry_at ?? lead.created_at, me.company.timezone)}
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
          </div>
        </Card>
      )}
    </>
  )
}

export function LeadsPage() {
  return (
    <>
      <PageHeader
        title="Leads"
        description="Every prospect in one pipeline: website enquiries and leads added by staff."
      />
      <RequirePermission permission="lead.read">
        <LeadsTable />
      </RequirePermission>
    </>
  )
}
