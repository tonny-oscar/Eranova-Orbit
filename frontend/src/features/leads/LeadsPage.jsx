import { Inbox, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { formatDateTime } from '@/lib/utils'
import { LEAD_STATUS, LEAD_STATUSES, SOURCE_LABELS, useLeads } from './api'

const PAGE_SIZE = 25

function LeadsTable() {
  const { data: me } = useMe()
  const products = useProductOptions()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [productId, setProductId] = useState('')
  const [offset, setOffset] = useState(0)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch, isFetching } = useLeads({
    q,
    status,
    product_id: productId,
    limit: PAGE_SIZE,
    offset,
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
              className="w-72 pl-9"
              value={search}
              onChange={reset(setSearch)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-status">Status</Label>
          <Select id="lead-status" className="w-44" value={status} onChange={reset(setStatus)}>
            <option value="">All</option>
            {LEAD_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-product">Product</Label>
          <Select
            id="lead-product"
            className="w-48"
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
      </div>

      {isPending && <LoadingState label="Loading leads…" />}
      {isError && <ErrorState title="Couldn't load leads" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState
          icon={Inbox}
          title={q || status || productId ? 'No leads match these filters' : 'No leads yet'}
          description="Enquiries from the website contact and demo forms appear here automatically."
        />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">Leads, most recent enquiry first</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Lead
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Status
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Product
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Source
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Last enquiry
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
                      <Badge variant={LEAD_STATUS[lead.status]?.variant}>
                        {LEAD_STATUS[lead.status]?.label ?? lead.status}
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
        description="Prospects from the website and other sources. Full CRM pipeline tools arrive in the next phase."
      />
      <RequirePermission permission="lead.read">
        <LeadsTable />
      </RequirePermission>
    </>
  )
}
