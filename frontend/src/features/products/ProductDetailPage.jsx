import { ArrowLeft, ExternalLink, Pencil, Trash2, UserPlus } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Button, buttonVariants } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Select } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState, Skeleton } from '@/components/ui/states'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import {
  useAddProductMember,
  useChangeProductStatus,
  useProduct,
  useProductHistory,
  useProductMembers,
  useRemoveProductMember,
  useSetProductPublished,
  useUserOptions,
} from './api'
import { ANALYTICS_SOURCES, LIFECYCLE_STATUSES, PRICING_INTERVALS } from './constants'
import { ProductStatusBadge, UnconfirmedBadge } from './ProductStatusBadge'

const labelFor = (options, value) => options.find((o) => o.value === value)?.label ?? value

function DetailRow({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5 py-2.5 text-sm sm:flex-row sm:justify-between sm:gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-all sm:text-right">{children ?? '—'}</dd>
    </div>
  )
}

function ExternalUrl({ href }) {
  if (!href) return null
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-accent hover:underline"
    >
      {href.replace(/^https?:\/\//, '').replace(/\/$/, '')}
      <ExternalLink className="size-3" aria-hidden="true" />
    </a>
  )
}

function StatusChanger({ product }) {
  const [status, setStatus] = useState(product.lifecycle_status)
  const [reason, setReason] = useState('')
  const change = useChangeProductStatus(product.id)
  const unchanged = status === product.lifecycle_status

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault()
        change.mutate({ status, reason: reason.trim() || null }, { onSuccess: () => setReason('') })
      }}
    >
      {change.isError && <Alert variant="error" title={change.error.message} />}
      <div className="grid gap-3 sm:grid-cols-[12rem_1fr_auto] sm:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="new-status">New status</Label>
          <Select id="new-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            {LIFECYCLE_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="status-reason">Reason (optional)</Label>
          <Input
            id="status-reason"
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={unchanged} loading={change.isPending}>
          Update status
        </Button>
      </div>
    </form>
  )
}

const PUBLIC_STATUSES = ['beta', 'live', 'maintenance']

function PublishingCard({ product }) {
  const publish = useSetProductPublished(product.id)
  const blockers = [
    !product.details_confirmed && 'Details must be confirmed by the product owner.',
    !PUBLIC_STATUSES.includes(product.lifecycle_status) &&
      'Status must be beta, live or maintenance.',
    !product.description?.trim() && 'Add a description.',
  ].filter(Boolean)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Marketplace</CardTitle>
        <CardDescription>Whether this product appears on the public website.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {product.is_public ? (
            <Badge variant="success">Public</Badge>
          ) : product.is_published ? (
            <Badge variant="warning">Published but hidden</Badge>
          ) : (
            <Badge>Not published</Badge>
          )}
          {product.is_public && (
            <a
              href={`/products/${product.slug}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              View public page <ExternalLink className="size-3" aria-hidden="true" />
            </a>
          )}
        </div>
        {product.is_published && !product.is_public && (
          <p className="text-sm text-muted-foreground">It is hidden until: {blockers.join(' ')}</p>
        )}
        {publish.isError && (
          <Alert variant="error" title={publish.error.message}>
            {publish.error.details?.map((d) => d.message).join(' ')}
          </Alert>
        )}
        {product.can_publish ? (
          product.is_published ? (
            <ConfirmButton
              confirmLabel="Confirm unpublish"
              loading={publish.isPending}
              onConfirm={() => publish.mutate(false)}
            >
              Unpublish
            </ConfirmButton>
          ) : (
            <>
              {blockers.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {blockers.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
              <Button
                variant="accent"
                size="sm"
                disabled={blockers.length > 0}
                loading={publish.isPending}
                onClick={() => publish.mutate(true)}
              >
                Publish to website
              </Button>
            </>
          )
        ) : (
          <p className="text-xs text-muted-foreground">Publishing requires approval rights.</p>
        )}
      </CardContent>
    </Card>
  )
}

function StatusHistory({ productId, timeZone }) {
  const { data, isPending, isError, error, refetch } = useProductHistory(productId)
  if (isPending) return <Skeleton className="h-20" />
  if (isError) return <ErrorState title="Couldn't load history" error={error} onRetry={refetch} />
  return (
    <ol className="space-y-3">
      {data.map((entry) => (
        <li key={entry.id} className="text-sm">
          <div className="flex flex-wrap items-center gap-2">
            {entry.from_status && (
              <>
                <ProductStatusBadge status={entry.from_status} />
                <span aria-hidden="true">→</span>
              </>
            )}
            <ProductStatusBadge status={entry.to_status} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatDateTime(entry.created_at, timeZone)}
            {entry.changed_by ? ` · ${entry.changed_by.full_name}` : ' · System'}
            {entry.reason ? ` · ${entry.reason}` : ''}
          </p>
        </li>
      ))}
    </ol>
  )
}

function TeamCard({ product }) {
  const members = useProductMembers(product.id)
  const users = useUserOptions()
  const add = useAddProductMember(product.id)
  const remove = useRemoveProductMember(product.id)
  const [userId, setUserId] = useState('')
  const [teamRole, setTeamRole] = useState('')
  const canEdit = product.can_manage && users.enabled
  const memberIds = new Set((members.data ?? []).map((m) => m.user.id))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Team</CardTitle>
        <CardDescription>
          The product roster. Access rights come from roles assigned at this product's scope.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {members.isPending && <Skeleton className="h-16" />}
        {members.isError && (
          <ErrorState title="Couldn't load team" error={members.error} onRetry={members.refetch} />
        )}
        {members.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">No team members recorded.</p>
        )}
        {members.data?.length > 0 && (
          <ul className="divide-y">
            {members.data.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <div>
                  <p className="font-medium">{m.user.full_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {m.team_role} · {m.user.email}
                  </p>
                </div>
                {product.can_manage && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove ${m.user.full_name}`}
                    loading={remove.isPending && remove.variables === m.id}
                    onClick={() => remove.mutate(m.id)}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {(add.isError || remove.isError) && (
          <Alert variant="error" title={(add.error ?? remove.error).message} />
        )}
        {canEdit && (
          <form
            className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end"
            onSubmit={(event) => {
              event.preventDefault()
              add.mutate(
                { user_id: userId, team_role: teamRole.trim() || 'Member' },
                {
                  onSuccess: () => {
                    setUserId('')
                    setTeamRole('')
                  },
                },
              )
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="member-user">Add person</Label>
              <Select id="member-user" value={userId} onChange={(e) => setUserId(e.target.value)}>
                <option value="">Select a person…</option>
                {(users.data ?? [])
                  .filter((u) => !memberIds.has(u.id))
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}
                    </option>
                  ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="member-role">Team role</Label>
              <Input
                id="member-role"
                placeholder="e.g. Developer"
                maxLength={60}
                value={teamRole}
                onChange={(e) => setTeamRole(e.target.value)}
              />
            </div>
            <Button type="submit" variant="outline" disabled={!userId} loading={add.isPending}>
              <UserPlus aria-hidden="true" /> Add
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

export function ProductDetailPage() {
  const { productId } = useParams()
  const { data: me } = useMe()
  const timeZone = me.company.timezone
  const { data: product, isPending, isError, error, refetch } = useProduct(productId)

  if (isPending) return <LoadingState label="Loading product…" />
  if (isError)
    return <ErrorState title="Couldn't load this product" error={error} onRetry={refetch} />

  return (
    <>
      <Link
        to="/app/products"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Products
      </Link>
      <PageHeader
        title={product.name}
        description={product.tagline ?? product.slug}
        actions={
          product.can_update && (
            <Link
              to={`/app/products/${product.id}/edit`}
              className={buttonVariants({ variant: 'outline' })}
            >
              <Pencil aria-hidden="true" /> Edit
            </Link>
          )
        }
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <ProductStatusBadge status={product.lifecycle_status} />
        <UnconfirmedBadge confirmed={product.details_confirmed} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-line text-sm text-muted-foreground">
                {product.description || 'No description recorded yet.'}
              </p>
              <dl className="mt-4 divide-y">
                <DetailRow label="Category">{product.category}</DetailRow>
                <DetailRow label="Owner">{product.owner?.full_name ?? 'Unassigned'}</DetailRow>
                <DetailRow label="Launch date">{product.launch_date}</DetailRow>
                <DetailRow label="Registered">
                  {formatDateTime(product.created_at, timeZone)}
                </DetailRow>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Links and operations</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="divide-y">
                <DetailRow label="Website">
                  <ExternalUrl href={product.website_url} />
                </DetailRow>
                <DetailRow label="Repository">
                  <ExternalUrl href={product.repository_url} />
                </DetailRow>
                <DetailRow label="Documentation">
                  <ExternalUrl href={product.docs_url} />
                </DetailRow>
                <DetailRow label="Status page">
                  <ExternalUrl href={product.status_page_url} />
                </DetailRow>
                <DetailRow label="Deployment">{product.deployment_ref}</DetailRow>
                <DetailRow label="Support email">{product.support_email}</DetailRow>
                <DetailRow label="Analytics">
                  {product.analytics_source
                    ? `${labelFor(ANALYTICS_SOURCES, product.analytics_source)}${
                        product.analytics_property_id ? ` · ${product.analytics_property_id}` : ''
                      }`
                    : null}
                </DetailRow>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Pricing</CardTitle>
            </CardHeader>
            <CardContent>
              {product.pricing.length === 0 ? (
                <p className="text-sm text-muted-foreground">No pricing recorded.</p>
              ) : (
                <ul className="divide-y">
                  {product.pricing.map((plan) => (
                    <li key={plan.name} className="flex justify-between gap-3 py-2.5 text-sm">
                      <span className="font-medium">{plan.name}</span>
                      <span className="text-muted-foreground">
                        {plan.amount
                          ? `${plan.currency ?? ''} ${plan.amount}`.trim()
                          : 'Price on request'}
                        {plan.interval ? ` · ${labelFor(PRICING_INTERVALS, plan.interval)}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <PublishingCard product={product} />
          {product.can_update && (
            <Card>
              <CardHeader>
                <CardTitle>Lifecycle</CardTitle>
              </CardHeader>
              <CardContent>
                <StatusChanger key={product.lifecycle_status} product={product} />
              </CardContent>
            </Card>
          )}
          <TeamCard product={product} />
          <Card>
            <CardHeader>
              <CardTitle>Status history</CardTitle>
            </CardHeader>
            <CardContent>
              <StatusHistory productId={product.id} timeZone={timeZone} />
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
