import { Building, Download, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { usePermissions } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { CUSTOMER_STATUS, CUSTOMER_STATUSES, useCreateCustomer, useCustomers } from './api'

const PAGE_SIZE = 25

function NewCustomer({ onClose }) {
  const navigate = useNavigate()
  const create = useCreateCustomer()
  const [name, setName] = useState('')
  const [industry, setIndustry] = useState('')
  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              { name: name.trim(), industry: industry.trim() || null },
              { onSuccess: (c) => navigate(`/app/customers/${c.id}`) },
            )
          }}
        >
          {create.isError && (
            <div className="w-full">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="new-customer-name">Customer name</Label>
            <Input
              id="new-customer-name"
              className="w-72"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-customer-industry">Industry</Label>
            <Input
              id="new-customer-industry"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
            />
          </div>
          <Button type="submit" loading={create.isPending} disabled={name.trim().length < 2}>
            Create
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function CustomersTable() {
  const { has } = usePermissions()
  const products = useProductOptions()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [productId, setProductId] = useState('')
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch, isFetching } = useCustomers({
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
          <Label htmlFor="customer-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="customer-search"
              type="search"
              className="w-64 pl-9"
              placeholder="Name or email"
              value={search}
              onChange={reset(setSearch)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="customer-status">Status</Label>
          <Select id="customer-status" className="w-40" value={status} onChange={reset(setStatus)}>
            <option value="">All</option>
            {CUSTOMER_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="customer-product">Product</Label>
          <Select
            id="customer-product"
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
        <div className="ml-auto flex gap-2">
          {has('customer.export') && (
            <a
              href="/api/v1/customers/export.csv"
              className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs hover:bg-muted"
            >
              <Download className="size-4" aria-hidden="true" /> Export CSV
            </a>
          )}
          {has('customer.create') && !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" /> New customer
            </Button>
          )}
        </div>
      </div>
      {creating && <NewCustomer onClose={() => setCreating(false)} />}
      {isPending && <LoadingState label="Loading customers…" />}
      {isError && <ErrorState title="Couldn't load customers" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState
          icon={Building}
          title="No customers yet"
          description="Convert a lead or add a customer directly."
        />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">Customers</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Customer
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Status
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Products
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Account manager
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Next renewal
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((c) => (
                  <tr key={c.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link to={`/app/customers/${c.id}`} className="font-medium hover:text-accent">
                        {c.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">{c.industry ?? c.email ?? ''}</p>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={CUSTOMER_STATUS[c.status]?.variant}>
                        {CUSTOMER_STATUS[c.status]?.label}
                      </Badge>
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                      {c.products.map((p) => p.name).join(', ') || '—'}
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                      {c.account_manager?.name ?? 'Unassigned'}
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                      {c.next_renewal ?? '—'}
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

export function CustomersPage() {
  return (
    <>
      <PageHeader
        title="Customers"
        description="Organisations using Eranova products, their contacts, subscriptions and history."
      />
      <RequirePermission permission="customer.read">
        <CustomersTable />
      </RequirePermission>
    </>
  )
}
