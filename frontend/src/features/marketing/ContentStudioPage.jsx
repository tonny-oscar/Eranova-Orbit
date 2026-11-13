import { FileText, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
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
import { useMe, usePermissions } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import {
  CHANNELS,
  CONTENT_KIND,
  CONTENT_KINDS,
  CONTENT_STATUS,
  CONTENT_STATUSES,
  useCampaigns,
  useContentList,
  useCreateContent,
} from './api'
import { MarketingNav } from './MarketingNav'

function NewContent({ campaignId, onClose }) {
  const navigate = useNavigate()
  const create = useCreateContent()
  const campaigns = useCampaigns({ limit: 100 })
  const products = useProductOptions()
  const [form, setForm] = useState({
    title: '',
    kind: 'social_caption',
    channel: '',
    campaign_id: campaignId ?? '',
    product_id: '',
  })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                title: form.title.trim(),
                kind: form.kind,
                channel: form.channel || null,
                campaign_id: form.campaign_id || null,
                product_id: form.campaign_id ? null : form.product_id || null,
              },
              { onSuccess: (item) => navigate(`/app/marketing/content/${item.id}`) },
            )
          }}
        >
          {create.isError && (
            <div className="md:col-span-3">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5 md:col-span-3">
            <Label htmlFor="content-title">Title</Label>
            <Input id="content-title" value={form.title} onChange={set('title')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="content-kind">Type</Label>
            <Select id="content-kind" value={form.kind} onChange={set('kind')}>
              {CONTENT_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="content-channel">Channel</Label>
            <Select id="content-channel" value={form.channel} onChange={set('channel')}>
              <option value="">Not set</option>
              {CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="content-campaign">Campaign</Label>
            <Select id="content-campaign" value={form.campaign_id} onChange={set('campaign_id')}>
              <option value="">None</option>
              {(campaigns.data?.items ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
          {!form.campaign_id && (
            <div className="space-y-1.5">
              <Label htmlFor="content-product">Product</Label>
              <Select id="content-product" value={form.product_id} onChange={set('product_id')}>
                <option value="">Company-wide</option>
                {(products.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex items-end gap-2 md:col-span-3">
            <Button
              type="submit"
              loading={create.isPending}
              disabled={form.title.trim().length < 2}
            >
              Create draft
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

function ContentList() {
  const { has } = usePermissions()
  const { data: me } = useMe()
  const [params, setParams] = useSearchParams()
  const [status, setStatus] = useState('')
  const [kind, setKind] = useState('')
  const { data, isPending, isError, error, refetch } = useContentList({ status, kind, limit: 100 })
  const creating = params.get('new') === '1'
  const closeNew = () => setParams({})
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="content-filter-status">Status</Label>
          <Select
            id="content-filter-status"
            className="w-40"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            {CONTENT_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="content-filter-kind">Type</Label>
          <Select
            id="content-filter-kind"
            className="w-48"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="">All</option>
            {CONTENT_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </Select>
        </div>
        {has('campaign.create') && !creating && (
          <Button size="sm" className="ml-auto" onClick={() => setParams({ new: '1' })}>
            <Plus aria-hidden="true" /> New content
          </Button>
        )}
      </div>
      {creating && <NewContent campaignId={params.get('campaign')} onClose={closeNew} />}
      {isPending && <LoadingState label="Loading content…" />}
      {isError && <ErrorState title="Couldn't load content" error={error} onRetry={refetch} />}
      {data?.items.length === 0 && (
        <EmptyState
          icon={FileText}
          title="No content yet"
          description="Draft captions, emails, blog posts and announcements here, then send them for review."
        />
      )}
      {data?.items.length > 0 && (
        <Card className="overflow-hidden">
          <ul className="divide-y">
            {data.items.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
              >
                <div>
                  <Link
                    to={`/app/marketing/content/${item.id}`}
                    className="font-medium hover:text-accent"
                  >
                    {item.title}
                  </Link>
                  <p className="text-xs text-muted-foreground">
                    {CONTENT_KIND[item.kind]?.label}
                    {item.channel ? ` · ${item.channel}` : ''}
                    {item.campaign ? ` · ${item.campaign.name}` : ''}
                    {item.scheduled_for && item.status === 'scheduled'
                      ? ` · ${formatDateTime(item.scheduled_for, me.company.timezone)}`
                      : ''}
                  </p>
                </div>
                <Badge variant={CONTENT_STATUS[item.status]?.variant}>
                  {CONTENT_STATUS[item.status]?.label}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  )
}

export function ContentStudioPage() {
  return (
    <>
      <PageHeader title="Marketing" description="Campaigns, content and the publishing calendar." />
      <MarketingNav />
      <RequirePermission permission="campaign.read">
        <ContentList />
      </RequirePermission>
    </>
  )
}
