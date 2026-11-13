import { ArrowLeft, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { ActivityTimeline } from '@/components/ui/activity-timeline'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/form-controls'
import { Input, Label } from '@/components/ui/input'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { useProductOptions } from '@/features/admin/api'
import { useMe } from '@/features/auth/hooks'
import { useUserOptions } from '@/features/products/api'
import {
  CUSTOMER_STATUS,
  CUSTOMER_STATUSES,
  SUBSCRIPTION_STATUSES,
  useCustomer,
  useCustomerActions,
} from './api'

function DetailsCard({ customer, actions }) {
  const users = useUserOptions()
  const [values, setValues] = useState({
    status: customer.status,
    email: customer.email ?? '',
    phone: customer.phone ?? '',
    website: customer.website ?? '',
    account_manager_user_id: customer.account_manager?.id ?? '',
    notes: customer.notes,
  })
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))
  const readOnly = !customer.can_update
  return (
    <Card>
      <CardHeader>
        <CardTitle>Details</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            actions.update.mutate({
              status: values.status,
              email: values.email || null,
              phone: values.phone || null,
              website: values.website || null,
              account_manager_user_id: values.account_manager_user_id || null,
              notes: values.notes,
            })
          }}
        >
          {actions.update.isError && <Alert variant="error" title={actions.update.error.message} />}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cust-status">Status</Label>
              <Select
                id="cust-status"
                value={values.status}
                onChange={set('status')}
                disabled={readOnly}
              >
                {CUSTOMER_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cust-manager">Account manager</Label>
              <Select
                id="cust-manager"
                value={values.account_manager_user_id}
                onChange={set('account_manager_user_id')}
                disabled={readOnly || !users.enabled}
              >
                <option value="">Unassigned</option>
                {(users.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cust-email">Email</Label>
              <Input
                id="cust-email"
                type="email"
                value={values.email}
                onChange={set('email')}
                disabled={readOnly}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cust-phone">Phone</Label>
              <Input
                id="cust-phone"
                value={values.phone}
                onChange={set('phone')}
                disabled={readOnly}
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="cust-website">Website</Label>
              <Input
                id="cust-website"
                value={values.website}
                onChange={set('website')}
                disabled={readOnly}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cust-notes">Notes</Label>
            <Textarea
              id="cust-notes"
              rows={3}
              value={values.notes}
              onChange={set('notes')}
              disabled={readOnly}
            />
          </div>
          {!readOnly && (
            <Button type="submit" loading={actions.update.isPending}>
              Save
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

function ContactsCard({ customer, actions }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [title, setTitle] = useState('')
  return (
    <Card>
      <CardHeader>
        <CardTitle>Contacts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {customer.contacts.length === 0 && (
          <p className="text-sm text-muted-foreground">No contacts.</p>
        )}
        <ul className="divide-y">
          {customer.contacts.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <div>
                <p className="font-medium">
                  {c.full_name} {c.is_primary && <Badge variant="accent">Primary</Badge>}
                </p>
                <p className="text-xs text-muted-foreground">
                  {[c.job_title, c.email, c.phone].filter(Boolean).join(' · ')}
                </p>
              </div>
              {customer.can_update && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${c.full_name}`}
                  onClick={() => actions.removeContact.mutate(c.id)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              )}
            </li>
          ))}
        </ul>
        {customer.can_update && (
          <form
            className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
            onSubmit={(e) => {
              e.preventDefault()
              actions.addContact.mutate(
                {
                  full_name: name.trim(),
                  email: email.trim() || null,
                  job_title: title.trim() || null,
                },
                {
                  onSuccess: () => {
                    setName('')
                    setEmail('')
                    setTitle('')
                  },
                },
              )
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="contact-name">Name</Label>
              <Input id="contact-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-email">Email</Label>
              <Input
                id="contact-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-title">Job title</Label>
              <Input id="contact-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={name.trim().length < 2}
              loading={actions.addContact.isPending}
            >
              Add
            </Button>
          </form>
        )}
        {actions.addContact.isError && (
          <Alert variant="error" title={actions.addContact.error.message} />
        )}
      </CardContent>
    </Card>
  )
}

function SubscriptionsCard({ customer, actions }) {
  const products = useProductOptions()
  const [productId, setProductId] = useState('')
  const [status, setStatus] = useState('active')
  const [renewal, setRenewal] = useState('')
  return (
    <Card>
      <CardHeader>
        <CardTitle>Products and subscriptions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {customer.subscriptions.length === 0 && (
          <p className="text-sm text-muted-foreground">No products recorded.</p>
        )}
        <ul className="divide-y">
          {customer.subscriptions.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <div>
                <p className="font-medium">
                  {s.product.name} <Badge>{s.status}</Badge>
                </p>
                <p className="text-xs text-muted-foreground">
                  {[s.plan_name, s.renewal_date && `renews ${s.renewal_date}`]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              </div>
              {customer.can_update && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${s.product.name}`}
                  onClick={() => actions.removeSubscription.mutate(s.id)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              )}
            </li>
          ))}
        </ul>
        {customer.can_update && (
          <form
            className="grid gap-2 sm:grid-cols-[1fr_8rem_10rem_auto] sm:items-end"
            onSubmit={(e) => {
              e.preventDefault()
              actions.setSubscription.mutate({
                product_id: productId,
                status,
                renewal_date: renewal || null,
              })
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="sub-product">Product</Label>
              <Select
                id="sub-product"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
              >
                <option value="">Select…</option>
                {(products.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="sub-status">Status</Label>
              <Select id="sub-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                {SUBSCRIPTION_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="sub-renewal">Renewal date</Label>
              <Input
                id="sub-renewal"
                type="date"
                value={renewal}
                onChange={(e) => setRenewal(e.target.value)}
              />
            </div>
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={!productId}
              loading={actions.setSubscription.isPending}
            >
              Save
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

export function CustomerDetailPage() {
  const { customerId } = useParams()
  const { data: me } = useMe()
  const { data: customer, isPending, isError, error, refetch } = useCustomer(customerId)
  const actions = useCustomerActions(customerId)

  if (isPending) return <LoadingState label="Loading customer…" />
  if (isError)
    return <ErrorState title="Couldn't load this customer" error={error} onRetry={refetch} />

  return (
    <>
      <Link
        to="/app/customers"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Customers
      </Link>
      <PageHeader title={customer.name} description={customer.industry ?? undefined} />
      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        <Badge variant={CUSTOMER_STATUS[customer.status]?.variant}>
          {CUSTOMER_STATUS[customer.status]?.label}
        </Badge>
        {customer.source_leads.map((l) => (
          <Link key={l.id} to={`/app/leads/${l.id}`} className="text-accent hover:underline">
            Converted from lead: {l.name}
          </Link>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <DetailsCard
            key={customer.status + customer.notes}
            customer={customer}
            actions={actions}
          />
          <SubscriptionsCard customer={customer} actions={actions} />
        </div>
        <div className="space-y-4">
          <ContactsCard customer={customer} actions={actions} />
          <Card>
            <CardHeader>
              <CardTitle>Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <ActivityTimeline
                idPrefix="customer-activity"
                activities={customer.activities}
                timeZone={me.company.timezone}
                adding={actions.addActivity.isPending}
                error={actions.addActivity.error}
                onAdd={
                  customer.can_update
                    ? (payload, done) => actions.addActivity.mutate(payload, { onSuccess: done })
                    : undefined
                }
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
