import { Search } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, Skeleton } from '@/components/ui/states'
import { useDebounced } from '@/hooks/useDebounced'
import { usePageMeta } from '@/hooks/usePageMeta'
import { usePublicProducts, useSiteInfo } from '../api'
import { Container, PageIntro, ProductCard } from '../components'

export function CatalogPage() {
  usePageMeta('Products', 'Browse Eranova products.')
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const debounced = useDebounced(q.trim())
  const site = useSiteInfo()
  const { data, isPending, isError, error, refetch } = usePublicProducts({ q: debounced, category })

  const update = (key) => (event) => {
    const next = new URLSearchParams(params)
    if (event.target.value) next.set(key, event.target.value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <PageIntro eyebrow="Products" title="Find the right product" />
      <Container className="py-10">
        <div className="mb-6 flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="catalog-search">Search</Label>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="catalog-search"
                type="search"
                className="w-72 pl-9"
                placeholder="Search products"
                value={q}
                onChange={update('q')}
              />
            </div>
          </div>
          {site.data?.categories?.length > 0 && (
            <div className="space-y-1.5">
              <Label htmlFor="catalog-category">Category</Label>
              <Select
                id="catalog-category"
                className="w-52"
                value={category}
                onChange={update('category')}
              >
                <option value="">All categories</option>
                {site.data.categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </div>
          )}
        </div>

        {isPending && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
          </div>
        )}
        {isError && <ErrorState title="Products couldn't load" error={error} onRetry={refetch} />}
        {data?.length === 0 && (
          <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
            {q || category ? 'No products match your search.' : 'Product pages are coming soon.'}
          </p>
        )}
        {data?.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>
        )}
      </Container>
    </>
  )
}
