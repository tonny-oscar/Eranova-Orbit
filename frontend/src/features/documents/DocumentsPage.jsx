import { FolderOpen, Lock, Search, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { RequirePermission } from '@/features/auth/guards'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { useDebounced } from '@/hooks/useDebounced'
import { formatDateTime } from '@/lib/utils'
import {
  ACCEPT,
  CATEGORIES,
  CATEGORY,
  MAX_BYTES,
  formatBytes,
  useDocuments,
  useUploadDocument,
} from './api'

function UploadForm({ onClose }) {
  const navigate = useNavigate()
  const upload = useUploadDocument()
  const products = useProductOptions()
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({
    title: '',
    category: 'other',
    description: '',
    visibility: 'scoped',
    product_id: '',
  })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const tooBig = file && file.size > MAX_BYTES
  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            const data = new FormData()
            data.set('file', file)
            for (const [k, v] of Object.entries(form))
              if (v) data.set(k, k === 'title' ? v.trim() : v)
            upload.mutate(data, { onSuccess: (d) => navigate(`/app/documents/${d.id}`) })
          }}
        >
          {upload.isError && (
            <div className="md:col-span-2">
              <Alert variant="error" title={upload.error.message} />
            </div>
          )}
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="doc-file">File (up to 10 MB)</Label>
            <Input
              id="doc-file"
              type="file"
              accept={ACCEPT}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null
                setFile(f)
                if (f && !form.title) setForm({ ...form, title: f.name.replace(/\.[^.]+$/, '') })
              }}
            />
            {tooBig && <p className="text-xs text-destructive">This file is larger than 10 MB.</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doc-title">Title</Label>
            <Input id="doc-title" value={form.title} onChange={set('title')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doc-category">Category</Label>
            <Select id="doc-category" value={form.category} onChange={set('category')}>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doc-product">Product</Label>
            <Select id="doc-product" value={form.product_id} onChange={set('product_id')}>
              <option value="">Not product-specific</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="doc-visibility">Who can see it</Label>
            <Select id="doc-visibility" value={form.visibility} onChange={set('visibility')}>
              <option value="scoped">Everyone with document access to this area</option>
              <option value="restricted">Only me and people I add</option>
            </Select>
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="doc-description">Description</Label>
            <Textarea
              id="doc-description"
              rows={2}
              value={form.description}
              onChange={set('description')}
            />
          </div>
          <div className="flex gap-2 md:col-span-2">
            <Button
              type="submit"
              loading={upload.isPending}
              disabled={!file || tooBig || form.title.trim().length < 2}
            >
              <Upload aria-hidden="true" /> Upload
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

function DocumentList() {
  const { has } = usePermissions()
  const { data: me } = useMe()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [uploading, setUploading] = useState(false)
  const q = useDebounced(search.trim())
  const { data, isPending, isError, error, refetch } = useDocuments({ q, category, limit: 100 })
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="doc-search">Search</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="doc-search"
              type="search"
              className="w-64 pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="doc-filter-category">Category</Label>
          <Select
            id="doc-filter-category"
            className="w-48"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All</option>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </Select>
        </div>
        {has('document.create') && !uploading && (
          <Button size="sm" className="ml-auto" onClick={() => setUploading(true)}>
            <Upload aria-hidden="true" /> Upload document
          </Button>
        )}
      </div>
      {uploading && <UploadForm onClose={() => setUploading(false)} />}
      {isPending && <LoadingState label="Loading documents…" />}
      {isError && <ErrorState title="Couldn't load documents" error={error} onRetry={refetch} />}
      {data?.items.length === 0 && (
        <EmptyState
          icon={FolderOpen}
          title="No documents"
          description="Contracts, policies, proposals and minutes you can access appear here."
        />
      )}
      {data?.items.length > 0 && (
        <Card className="overflow-hidden">
          <ul className="divide-y">
            {data.items.map((d) => (
              <li
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
              >
                <div>
                  <Link to={`/app/documents/${d.id}`} className="font-medium hover:text-accent">
                    {d.visibility === 'restricted' && (
                      <Lock className="mr-1 inline size-3" aria-label="Restricted" />
                    )}
                    {d.title}
                  </Link>
                  <p className="text-xs text-muted-foreground">
                    {d.filename} · {formatBytes(d.size_bytes)} · v{d.current_version} · updated{' '}
                    {formatDateTime(d.updated_at, me.company.timezone)}
                  </p>
                </div>
                <div className="flex gap-2">
                  {d.product && <Badge>{d.product.name}</Badge>}
                  <Badge variant="accent">{CATEGORY[d.category]}</Badge>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  )
}

export function DocumentsPage() {
  return (
    <>
      <PageHeader
        title="Documents"
        description="Company documents. You only see what your role and membership allow."
      />
      <RequirePermission permission="document.read">
        <DocumentList />
      </RequirePermission>
    </>
  )
}
