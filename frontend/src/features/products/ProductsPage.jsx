import { Boxes, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { buttonVariants, Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { formatDateTime } from '@/lib/utils'
import { useProducts } from './api'
import { LIFECYCLE_STATUSES } from './constants'
import { ProductStatusBadge, UnconfirmedBadge } from './ProductStatusBadge'

const PAGE_SIZE = 25

export function ProductsPage() {
  const { has } = usePermissions()
  const { data: me } = useMe()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const q = useDebounced(search.trim())
  const filters = { q, status, limit: PAGE_SIZE, offset }
  const { data, isPending, isError, error, refetch, isFetching } = useProducts(filters)

  const resetPage = (setter) => (event) => {
    setter(event.target.value)
    setOffset(0)
  }

  return (
    <>
      <PageHeader
        title="Products"
        description="The Eranova product registry. Each product keeps its own repository, deployment and data."
        actions={
          has('product.create') && (
            <Link to="/app/products/new" className={buttonVariants()}>
              <Plus aria-hidden="true" /> Register product
            </Link>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="product-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="product-search"
              type="search"
              placeholder="Name, slug or category"
              value={search}
              onChange={resetPage(setSearch)}
              className="w-72 pl-9"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="product-status">Status</Label>
          <Select
            id="product-status"
            value={status}
            onChange={resetPage(setStatus)}
            className="w-48"
          >
            <option value="">All statuses</option>
            {LIFECYCLE_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {isPending && <LoadingState label="Loading products…" />}
      {isError && <ErrorState title="Couldn't load products" error={error} onRetry={refetch} />}
      {data && data.items.length === 0 && (
        <EmptyState
          icon={Boxes}
          title={q || status ? 'No products match these filters' : 'No products registered yet'}
          description={
            q || status
              ? 'Try a different search or status.'
              : has('product.create')
                ? 'Register the first product to start building the company registry.'
                : 'Products you have access to will appear here.'
          }
        />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-busy={isFetching}>
              <caption className="sr-only">Registered products</caption>
              <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Product
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                    Category
                  </th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    Status
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Owner
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((product) => (
                  <tr key={product.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link
                        to={`/app/products/${product.id}`}
                        className="font-medium hover:text-accent"
                      >
                        {product.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {product.tagline ?? product.slug}
                      </p>
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                      {product.category ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <ProductStatusBadge status={product.lifecycle_status} />
                        <UnconfirmedBadge confirmed={product.details_confirmed} />
                      </div>
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                      {product.owner?.full_name ?? 'Unassigned'}
                    </td>
                    <td className="hidden whitespace-nowrap px-4 py-3 text-muted-foreground lg:table-cell">
                      {formatDateTime(product.updated_at, me.company.timezone)}
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
