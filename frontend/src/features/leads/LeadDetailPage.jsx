import { ArrowLeft, Mail, Phone, UserCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { ActivityTimeline } from '@/components/ui/activity-timeline'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { useUserOptions } from '@/features/products/api'
import { formatDateTime } from '@/lib/utils'
import {
  PRIORITIES,
  SOURCE_LABELS,
  stageVariant,
  useAddLeadActivity,
  useConvertLead,
  useLead,
  useStages,
  useUpdateLead,
} from './api'

function ManageCard({ lead, stages }) {
  const users = useUserOptions()
  const update = useUpdateLead(lead.id)
  const [values, setValues] = useState({
    status: lead.status,
    priority: lead.priority,
    owner_user_id: lead.owner?.id ?? '',
    next_follow_up: lead.next_follow_up ?? '',
    notes: lead.notes,
  })
  const set = (key) => (e) => setValues((v) => ({ ...v, [key]: e.target.value }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manage</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            update.mutate({
              status: values.status,
              priority: values.priority,
              owner_user_id: values.owner_user_id || null,
              next_follow_up: values.next_follow_up || null,
              notes: values.notes,
            })
          }}
        >
          {update.isError && <Alert variant="error" title={update.error.message} />}
          {update.isSuccess && <Alert variant="success" title="Lead updated" />}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="lead-status-edit">Stage</Label>
              <Select id="lead-status-edit" value={values.status} onChange={set('status')}>
                {stages.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-priority">Priority</Label>
              <Select id="lead-priority" value={values.priority} onChange={set('priority')}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p[0].toUpperCase() + p.slice(1)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-owner">Owner</Label>
              {users.enabled ? (
                <Select
                  id="lead-owner"
                  value={values.owner_user_id}
                  onChange={set('owner_user_id')}
                >
                  <option value="">Unassigned</option>
                  {(users.data ?? []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}
                    </option>
                  ))}
                </Select>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {lead.owner?.full_name ?? 'Unassigned'}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-follow-up">Next follow-up</Label>
              <Input
                id="lead-follow-up"
                type="date"
                value={values.next_follow_up}
                onChange={set('next_follow_up')}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="lead-notes">Internal notes</Label>
            <Textarea
              id="lead-notes"
              rows={4}
              maxLength={10000}
              value={values.notes}
              onChange={set('notes')}
            />
          </div>
          <Button type="submit" loading={update.isPending}>
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function ConvertCard({ lead }) {
  const convert = useConvertLead(lead.id)
  const [name, setName] = useState(lead.organization ?? lead.full_name)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserCheck className="size-4 text-accent" aria-hidden="true" /> Convert to customer
        </CardTitle>
        <CardDescription>
          Creates the customer, adds this person as a contact and keeps all enquiries and activities
          linked.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            convert.mutate({ customer_name: name.trim() })
          }}
        >
          {convert.isError && (
            <div className="w-full">
              <Alert variant="error" title={convert.error.message} />
            </div>
          )}
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="convert-name">Customer name</Label>
            <Input id="convert-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <Button
            type="submit"
            variant="accent"
            loading={convert.isPending}
            disabled={name.trim().length < 2}
          >
            Convert
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export function LeadDetailPage() {
  const { leadId } = useParams()
  const { data: me } = useMe()
  const stages = useStages()
  const stageMap = Object.fromEntries((stages.data ?? []).map((s) => [s.key, s]))
  const { data: lead, isPending, isError, error, refetch } = useLead(leadId)
  const addActivity = useAddLeadActivity(leadId)
  const tz = me.company.timezone

  if (isPending || stages.isPending) return <LoadingState label="Loading lead…" />
  if (isError) return <ErrorState title="Couldn't load this lead" error={error} onRetry={refetch} />

  return (
    <>
      <Link
        to="/app/leads"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Leads
      </Link>
      <PageHeader title={lead.full_name} description={lead.organization ?? undefined} />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <Badge variant={stageVariant(stageMap[lead.status])}>
          {stageMap[lead.status]?.name ?? lead.status}
        </Badge>
        <Badge>{lead.priority} priority</Badge>
        {lead.marketing_consent ? (
          <Badge variant="success">Opted in to updates</Badge>
        ) : (
          <Badge>No marketing consent</Badge>
        )}
        {lead.converted_customer && (
          <Link
            to={`/app/customers/${lead.converted_customer.id}`}
            className="text-accent hover:underline"
          >
            Customer: {lead.converted_customer.name}
          </Link>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Contact</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p className="flex items-center gap-2">
                <Mail className="size-4 text-muted-foreground" aria-hidden="true" />
                <a href={`mailto:${lead.email}`} className="text-accent hover:underline">
                  {lead.email}
                </a>
              </p>
              {lead.phone && (
                <p className="flex items-center gap-2">
                  <Phone className="size-4 text-muted-foreground" aria-hidden="true" />
                  {lead.phone}
                </p>
              )}
              <p className="text-muted-foreground">
                Product: {lead.product?.name ?? 'Not specified'}
              </p>
              <p className="text-muted-foreground">
                Source: {SOURCE_LABELS[lead.source] ?? lead.source}
              </p>
              <p className="text-muted-foreground">
                First seen: {formatDateTime(lead.created_at, tz)}
              </p>
            </CardContent>
          </Card>
          {lead.can_convert && <ConvertCard lead={lead} />}
          {lead.can_update ? (
            <ManageCard key={`${lead.status}-${lead.notes}`} lead={lead} stages={stages.data} />
          ) : (
            <Card>
              <CardContent className="pt-5 text-sm text-muted-foreground">
                {lead.notes || 'No notes.'}
              </CardContent>
            </Card>
          )}
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Activity</CardTitle>
              <CardDescription>Calls, emails, meetings and notes.</CardDescription>
            </CardHeader>
            <CardContent>
              <ActivityTimeline
                idPrefix="lead-activity"
                activities={lead.activities ?? []}
                timeZone={tz}
                adding={addActivity.isPending}
                error={addActivity.error}
                onAdd={
                  lead.can_update
                    ? (payload, done) => addActivity.mutate(payload, { onSuccess: done })
                    : undefined
                }
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Website enquiries</CardTitle>
            </CardHeader>
            <CardContent>
              {lead.enquiries.length === 0 ? (
                <p className="text-sm text-muted-foreground">No website enquiries.</p>
              ) : (
                <ol className="space-y-4">
                  {lead.enquiries.map((e) => (
                    <li key={e.id} className="rounded-lg border p-3 text-sm">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <Badge variant={e.type === 'demo' ? 'accent' : 'default'}>
                          {e.type === 'demo' ? 'Demo request' : 'Contact'}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatDateTime(e.created_at, tz)}
                        </span>
                      </div>
                      {e.message && <p className="whitespace-pre-line">{e.message}</p>}
                      {e.preferred_date && (
                        <p className="mt-1 text-muted-foreground">
                          Preferred date: {e.preferred_date}
                        </p>
                      )}
                      <p className="mt-2 text-xs text-muted-foreground">
                        Consent: privacy notice {e.privacy_notice_version}
                        {e.consent_marketing ? ' · marketing opt-in' : ''}
                        {e.utm_source
                          ? ` · source ${e.utm_source}${e.utm_medium ? `/${e.utm_medium}` : ''}`
                          : ''}
                        {e.utm_campaign ? ` · campaign ${e.utm_campaign}` : ''}
                        {e.landing_page ? ` · landed on ${e.landing_page}` : ''}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
