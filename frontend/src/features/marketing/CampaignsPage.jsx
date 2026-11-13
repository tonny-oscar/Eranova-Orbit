import { Download, Megaphone, Plus } from 'lucide-react'
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
import { CAMPAIGN_STATUS, CAMPAIGN_STATUSES, useCampaigns, useCreateCampaign } from './api'
import { MarketingNav } from './MarketingNav'

function NewCampaign({ onClose }) {
  const navigate = useNavigate()
  const create = useCreateCampaign()
  const products = useProductOptions()
  const [form, setForm] = useState({ name: '', product_id: '', start_date: '', end_date: '' })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return (
    <Card className="mb-4">
      <CardContent className="pt-5">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate(
              {
                name: form.name.trim(),
                product_id: form.product_id || null,
                start_date: form.start_date || null,
                end_date: form.end_date || null,
              },
              { onSuccess: (c) => navigate(`/app/marketing/campaigns/${c.id}`) },
            )
          }}
        >
          {create.isError && (
            <div className="w-full">
              <Alert variant="error" title={create.error.message} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="campaign-name">Campaign name</Label>
            <Input id="campaign-name" className="w-64" value={form.name} onChange={set('name')} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="campaign-product">Product</Label>
            <Select id="campaign-product" value={form.product_id} onChange={set('product_id')}>
              <option value="">Company-wide</option>
              {(products.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="campaign-start">Start</Label>
            <Input
              id="campaign-start"
              type="date"
              value={form.start_date}
              onChange={set('start_date')}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="campaign-end">End</Label>
            <Input id="campaign-end" type="date" value={form.end_date} onChange={set('end_date')} />
          </div>
          <Button type="submit" loading={create.isPending} disabled={form.name.trim().length < 2}>
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

function CampaignList() {
  const { has } = usePermissions()
  const [status, setStatus] = useState('')
  const [creating, setCreating] = useState(false)
  const { data, isPending, isError, error, refetch } = useCampaigns({ status, limit: 100 })
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="campaign-status">Status</Label>
          <Select
            id="campaign-status"
            className="w-40"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            {CAMPAIGN_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-auto flex gap-2">
          {has('campaign.export') && (
            <a
              href="/api/v1/marketing/campaigns/export.csv"
              className="inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs hover:bg-muted"
            >
              <Download className="size-4" aria-hidden="true" /> Export CSV
            </a>
          )}
          {has('campaign.create') && !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" /> New campaign
            </Button>
          )}
        </div>
      </div>
      {creating && <NewCampaign onClose={() => setCreating(false)} />}
      {isPending && <LoadingState label="Loading campaigns…" />}
      {isError && <ErrorState title="Couldn't load campaigns" error={error} onRetry={refetch} />}
      {data?.items.length === 0 && (
        <EmptyState
          icon={Megaphone}
          title="No campaigns yet"
          description="Plan a campaign to organise content, budget and results."
        />
      )}
      {data?.items.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.items.map((c) => (
            <Link key={c.id} to={`/app/marketing/campaigns/${c.id}`}>
              <Card className="h-full transition-colors hover:border-accent/60">
                <CardContent className="space-y-2 pt-5 text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{c.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {c.product?.name ?? 'Company-wide'}
                        {c.start_date ? ` · ${c.start_date} → ${c.end_date ?? 'open'}` : ''}
                      </p>
                    </div>
                    <Badge variant={CAMPAIGN_STATUS[c.status]?.variant}>
                      {CAMPAIGN_STATUS[c.status]?.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {Object.values(c.content_counts).reduce((a, b) => a + b, 0)} content items ·{' '}
                    {c.content_counts.published ?? 0} published
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  )
}

export function CampaignsPage() {
  return (
    <>
      <PageHeader title="Marketing" description="Campaigns, content and the publishing calendar." />
      <MarketingNav />
      <RequirePermission permission="campaign.read">
        <CampaignList />
      </RequirePermission>
    </>
  )
}
