import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from '@/features/auth/hooks'
import { formatDateTime, formatNumber } from '@/lib/utils'
import {
  CAMPAIGN_STATUS,
  CAMPAIGN_STATUSES,
  CHANNELS,
  CONTENT_KIND,
  CONTENT_STATUS,
  useCampaign,
  useCampaignActions,
  useContentList,
} from './api'

function CampaignForm({ campaign }) {
  const { update } = useCampaignActions(campaign.id)
  const [form, setForm] = useState({
    objective: campaign.objective,
    audience: campaign.audience,
    channels: campaign.channels,
    budget_amount: campaign.budget_amount ?? '',
    budget_currency: campaign.budget_currency ?? '',
    start_date: campaign.start_date ?? '',
    end_date: campaign.end_date ?? '',
    status: campaign.status,
    notes: campaign.notes,
  })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const toggle = (channel) =>
    setForm({
      ...form,
      channels: form.channels.includes(channel)
        ? form.channels.filter((c) => c !== channel)
        : [...form.channels, channel],
    })
  return (
    <form
      className="grid gap-4 md:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault()
        update.mutate({
          ...form,
          budget_amount: form.budget_amount === '' ? null : form.budget_amount,
          budget_currency: form.budget_currency.trim().toUpperCase() || null,
          start_date: form.start_date || null,
          end_date: form.end_date || null,
        })
      }}
    >
      {update.isError && (
        <div className="md:col-span-2">
          <Alert variant="error" title={update.error.message} />
        </div>
      )}
      {update.isSuccess && (
        <div className="md:col-span-2">
          <Alert variant="success" title="Saved" />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="c-status">Status</Label>
        <Select id="c-status" value={form.status} onChange={set('status')}>
          {CAMPAIGN_STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="c-start">Start</Label>
          <Input id="c-start" type="date" value={form.start_date} onChange={set('start_date')} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-end">End</Label>
          <Input id="c-end" type="date" value={form.end_date} onChange={set('end_date')} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="c-objective">Objective</Label>
        <Textarea id="c-objective" rows={3} value={form.objective} onChange={set('objective')} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="c-audience">Audience</Label>
        <Textarea id="c-audience" rows={3} value={form.audience} onChange={set('audience')} />
      </div>
      <fieldset className="space-y-1.5 md:col-span-2">
        <legend className="text-sm font-medium">Channels</legend>
        <div className="flex flex-wrap gap-2">
          {CHANNELS.map((ch) => (
            <label key={ch} className="flex items-center gap-1.5 text-sm capitalize">
              <input
                type="checkbox"
                checked={form.channels.includes(ch)}
                onChange={() => toggle(ch)}
              />
              {ch}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="c-budget">Budget</Label>
          <Input
            id="c-budget"
            type="number"
            min="0"
            step="0.01"
            value={form.budget_amount}
            onChange={set('budget_amount')}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-currency">Currency</Label>
          <Input
            id="c-currency"
            maxLength={3}
            placeholder="KES"
            value={form.budget_currency}
            onChange={set('budget_currency')}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="c-notes">Notes</Label>
        <Textarea id="c-notes" rows={3} value={form.notes} onChange={set('notes')} />
      </div>
      <div className="md:col-span-2">
        <Button type="submit" loading={update.isPending}>
          Save campaign
        </Button>
      </div>
    </form>
  )
}

function Metrics({ campaign, timeZone }) {
  const { addMetric, removeMetric } = useCampaignActions(campaign.id)
  const [form, setForm] = useState({ metric: '', value: '', source: '', period_end: '' })
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance</CardTitle>
        <CardDescription>
          Figures you record from ad managers, email tools or analytics. Each shows its source.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {campaign.metrics.length === 0 ? (
          <p className="text-muted-foreground">No results recorded yet.</p>
        ) : (
          <ul className="divide-y">
            {campaign.metrics.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-3 py-2">
                <div>
                  <p>
                    <span className="font-medium">{formatNumber(Number(m.value))}</span> {m.metric}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {m.source}
                    {m.period_end ? ` · to ${m.period_end}` : ''} · recorded by{' '}
                    {m.recorded_by?.name ?? 'unknown'} {formatDateTime(m.created_at, timeZone)}
                  </p>
                </div>
                {campaign.can_update && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove ${m.metric}`}
                    onClick={() => removeMetric.mutate(m.id)}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {addMetric.isError && <Alert variant="error" title={addMetric.error.message} />}
        {campaign.can_update && (
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault()
              addMetric.mutate(
                { ...form, period_end: form.period_end || null },
                { onSuccess: () => setForm({ metric: '', value: '', source: '', period_end: '' }) },
              )
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="m-name">Metric</Label>
              <Input
                id="m-name"
                placeholder="Leads generated"
                value={form.metric}
                onChange={set('metric')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-value">Value</Label>
              <Input
                id="m-value"
                type="number"
                step="0.01"
                value={form.value}
                onChange={set('value')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-source">Source</Label>
              <Input
                id="m-source"
                placeholder="e.g. Meta Ads Manager"
                value={form.source}
                onChange={set('source')}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="m-end">Period end</Label>
              <Input id="m-end" type="date" value={form.period_end} onChange={set('period_end')} />
            </div>
            <div>
              <Button
                type="submit"
                variant="outline"
                size="sm"
                loading={addMetric.isPending}
                disabled={!form.metric || form.value === '' || form.source.length < 2}
              >
                <Plus aria-hidden="true" /> Record result
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

export function CampaignDetailPage() {
  const { campaignId } = useParams()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { has } = usePermissions()
  const { data: c, isPending, isError, error, refetch } = useCampaign(campaignId)
  const content = useContentList({ campaign_id: campaignId, limit: 100 })
  const { remove } = useCampaignActions(campaignId)
  if (isPending) return <LoadingState label="Loading campaign…" />
  if (isError) return <ErrorState title="Couldn't load campaign" error={error} onRetry={refetch} />
  return (
    <>
      <Link
        to="/app/marketing"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Campaigns
      </Link>
      <PageHeader
        title={c.name}
        description={`${c.product?.name ?? 'Company-wide'} · owner ${c.owner?.name ?? 'unassigned'}`}
        actions={
          has('campaign.create') && (
            <Link
              to={`/app/marketing/content?new=1&campaign=${c.id}`}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm text-primary-foreground"
            >
              <Plus className="size-4" aria-hidden="true" /> New content
            </Link>
          )
        }
      />
      <div className="mb-4">
        <Badge variant={CAMPAIGN_STATUS[c.status]?.variant}>
          {CAMPAIGN_STATUS[c.status]?.label}
        </Badge>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Plan</CardTitle>
            </CardHeader>
            <CardContent>
              {c.can_update ? (
                <CampaignForm key={c.id} campaign={c} />
              ) : (
                <dl className="space-y-2 text-sm">
                  <div>
                    <dt className="text-muted-foreground">Objective</dt>
                    <dd>{c.objective || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Audience</dt>
                    <dd>{c.audience || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Channels</dt>
                    <dd className="capitalize">{c.channels.join(', ') || '—'}</dd>
                  </div>
                </dl>
              )}
            </CardContent>
          </Card>
          <Metrics campaign={c} timeZone={me.company.timezone} />
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Content</CardTitle>
            </CardHeader>
            <CardContent>
              {content.data?.items.length === 0 && (
                <p className="text-sm text-muted-foreground">No content for this campaign yet.</p>
              )}
              <ul className="divide-y">
                {(content.data?.items ?? []).map((item) => (
                  <li
                    key={item.id}
                    className="flex items-center justify-between gap-2 py-2 text-sm"
                  >
                    <Link to={`/app/marketing/content/${item.id}`} className="hover:text-accent">
                      {item.title}
                      <span className="block text-xs text-muted-foreground">
                        {CONTENT_KIND[item.kind]?.label}
                        {item.channel ? ` · ${item.channel}` : ''}
                      </span>
                    </Link>
                    <Badge variant={CONTENT_STATUS[item.status]?.variant}>
                      {CONTENT_STATUS[item.status]?.label}
                    </Badge>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          {has('campaign.delete') && (
            <Card>
              <CardContent className="pt-5">
                {remove.isError && <Alert variant="error" title={remove.error.message} />}
                <ConfirmButton
                  confirmLabel="Confirm delete"
                  loading={remove.isPending}
                  onConfirm={() =>
                    remove.mutate(undefined, { onSuccess: () => navigate('/app/marketing') })
                  }
                >
                  Delete campaign
                </ConfirmButton>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
