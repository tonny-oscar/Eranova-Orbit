import { zodResolver } from '@hookform/resolvers/zod'
import { Plus, Trash2 } from 'lucide-react'
import { useEffect } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox, Select, Textarea } from '@/components/ui/form-controls'
import { FieldError, Input, Label } from '@/components/ui/input'
import { useUserOptions } from './api'
import { ANALYTICS_SOURCES, LIFECYCLE_STATUSES, PRICING_INTERVALS, slugify } from './constants'

const optionalText = (max) => z.string().max(max)
const optionalUrl = z.union([
  z.literal(''),
  z.url({ protocol: /^https?$/, message: 'Enter a full http(s) URL.' }).max(500),
])

const schema = z.object({
  name: z.string().trim().min(2, { message: 'Use at least 2 characters.' }).max(120),
  slug: z
    .string()
    .min(2, { message: 'Use at least 2 characters.' })
    .max(64)
    .regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, {
      message: 'Lowercase letters, numbers and single dashes only.',
    }),
  lifecycle_status: z.string(),
  category: optionalText(60),
  tagline: optionalText(200),
  description: optionalText(10_000),
  owner_user_id: z.string(),
  website_url: optionalUrl,
  repository_url: optionalUrl,
  docs_url: optionalUrl,
  status_page_url: optionalUrl,
  logo_url: optionalUrl,
  deployment_ref: optionalText(200),
  support_email: z.union([z.literal(''), z.email({ message: 'Enter a valid email.' })]),
  analytics_source: z.string(),
  analytics_property_id: optionalText(120),
  launch_date: z.string(),
  details_confirmed: z.boolean(),
  features: z
    .array(
      z.object({
        title: z.string().trim().min(1, { message: 'Name the feature.' }).max(80),
        description: optionalText(300),
      }),
    )
    .max(20),
  pricing: z
    .array(
      z.object({
        name: z.string().trim().min(1, { message: 'Name the plan.' }).max(80),
        amount: z.union([
          z.literal(''),
          z.string().regex(/^\d{1,10}(\.\d{1,2})?$/, { message: 'Use a number like 1500.00' }),
        ]),
        currency: z.union([
          z.literal(''),
          z.string().regex(/^[A-Z]{3}$/, { message: '3-letter code, e.g. KES' }),
        ]),
        interval: z.string(),
        notes: optionalText(300),
      }),
    )
    .max(20),
})

const nullable = (value) => (value === '' ? null : value)

function toFormValues(product) {
  const text = (v) => v ?? ''
  return {
    name: text(product?.name),
    slug: text(product?.slug),
    lifecycle_status: product?.lifecycle_status ?? 'draft',
    category: text(product?.category),
    tagline: text(product?.tagline),
    description: text(product?.description),
    owner_user_id: product?.owner?.id ?? '',
    website_url: text(product?.website_url),
    repository_url: text(product?.repository_url),
    docs_url: text(product?.docs_url),
    status_page_url: text(product?.status_page_url),
    logo_url: text(product?.logo_url),
    deployment_ref: text(product?.deployment_ref),
    support_email: text(product?.support_email),
    analytics_source: text(product?.analytics_source),
    analytics_property_id: text(product?.analytics_property_id),
    launch_date: text(product?.launch_date),
    details_confirmed: product?.details_confirmed ?? false,
    features: (product?.features ?? []).map((f) => ({
      title: text(f.title),
      description: text(f.description),
    })),
    pricing: (product?.pricing ?? []).map((plan) => ({
      name: text(plan.name),
      amount: text(plan.amount),
      currency: text(plan.currency),
      interval: text(plan.interval),
      notes: text(plan.notes),
    })),
  }
}

function toPayload(values, { isEdit }) {
  const { lifecycle_status, pricing, features, ...rest } = values
  const payload = Object.fromEntries(Object.entries(rest).map(([k, v]) => [k, nullable(v)]))
  payload.name = values.name.trim()
  payload.description = values.description
  payload.details_confirmed = values.details_confirmed
  payload.pricing = pricing.map((plan) => ({
    name: plan.name.trim(),
    amount: nullable(plan.amount),
    currency: nullable(plan.currency),
    interval: nullable(plan.interval),
    notes: nullable(plan.notes),
  }))
  payload.features = features.map((f) => ({
    title: f.title.trim(),
    description: nullable(f.description.trim()),
  }))
  if (!isEdit) payload.lifecycle_status = lifecycle_status
  return payload
}

function Field({ id, label, error, hint, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      <FieldError id={`${id}-error`}>{error}</FieldError>
    </div>
  )
}

export function ProductForm({ product, onSubmit, submitting, serverError, submitLabel }) {
  const isEdit = Boolean(product)
  const users = useUserOptions()
  const {
    register,
    control,
    handleSubmit,
    setValue,
    setError,
    getFieldState,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema), defaultValues: toFormValues(product) })
  const pricing = useFieldArray({ control, name: 'pricing' })
  const features = useFieldArray({ control, name: 'features' })

  useEffect(() => {
    for (const detail of serverError?.details ?? []) {
      const field = detail.field?.replace(/^body\./, '')
      if (field && field in schema.shape) setError(field, { message: detail.message })
    }
  }, [serverError, setError])

  const aria = (name) => ({
    'aria-invalid': errors[name] ? 'true' : undefined,
    'aria-describedby': errors[name] ? `${name}-error` : undefined,
  })

  const nameField = register('name', {
    onChange: (event) => {
      if (!isEdit && !getFieldState('slug').isDirty) {
        setValue('slug', slugify(event.target.value), { shouldValidate: true })
      }
    },
  })

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => onSubmit(toPayload(values, { isEdit })))}
      className="space-y-4"
    >
      {serverError && <Alert variant="error" title={serverError.message} />}

      <Card>
        <CardHeader>
          <CardTitle>Basics</CardTitle>
          <CardDescription>
            Enter only confirmed facts. Leave fields empty rather than guessing.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Field id="name" label="Name" error={errors.name?.message}>
            <Input id="name" {...nameField} {...aria('name')} />
          </Field>
          <Field
            id="slug"
            label="Slug"
            error={errors.slug?.message}
            hint={isEdit ? 'Changing the slug changes public URLs.' : 'Used in URLs.'}
          >
            <Input id="slug" {...register('slug')} {...aria('slug')} />
          </Field>
          <Field id="category" label="Category" error={errors.category?.message}>
            <Input id="category" placeholder="e.g. Education" {...register('category')} />
          </Field>
          {!isEdit && (
            <Field id="lifecycle_status" label="Initial status">
              <Select id="lifecycle_status" {...register('lifecycle_status')}>
                {LIFECYCLE_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <div className="md:col-span-2">
            <Field id="tagline" label="Tagline" error={errors.tagline?.message}>
              <Input id="tagline" {...register('tagline')} />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field id="description" label="Description" error={errors.description?.message}>
              <Textarea id="description" rows={5} {...register('description')} />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field id="owner_user_id" label="Product owner">
              {users.enabled ? (
                <Select
                  id="owner_user_id"
                  {...register('owner_user_id')}
                  disabled={users.isPending}
                >
                  <option value="">Unassigned</option>
                  {(users.data ?? []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email})
                    </option>
                  ))}
                </Select>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {product?.owner?.full_name ?? 'Unassigned'} — changing the owner requires
                  permission to view users.
                </p>
              )}
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Links and operations</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {[
            ['website_url', 'Public website'],
            ['repository_url', 'Repository'],
            ['docs_url', 'Documentation'],
            ['status_page_url', 'Status page'],
            ['logo_url', 'Logo URL'],
          ].map(([name, label]) => (
            <Field key={name} id={name} label={label} error={errors[name]?.message}>
              <Input
                id={name}
                type="url"
                placeholder="https://"
                {...register(name)}
                {...aria(name)}
              />
            </Field>
          ))}
          <Field
            id="deployment_ref"
            label="Deployment reference"
            hint="e.g. Vercel project name"
            error={errors.deployment_ref?.message}
          >
            <Input id="deployment_ref" {...register('deployment_ref')} />
          </Field>
          <Field id="support_email" label="Support email" error={errors.support_email?.message}>
            <Input
              id="support_email"
              type="email"
              {...register('support_email')}
              {...aria('support_email')}
            />
          </Field>
          <Field id="launch_date" label="Launch date">
            <Input id="launch_date" type="date" {...register('launch_date')} />
          </Field>
          <Field id="analytics_source" label="Analytics source">
            <Select id="analytics_source" {...register('analytics_source')}>
              <option value="">Not connected</option>
              {ANALYTICS_SOURCES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            id="analytics_property_id"
            label="Analytics property ID"
            error={errors.analytics_property_id?.message}
          >
            <Input id="analytics_property_id" {...register('analytics_property_id')} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Features</CardTitle>
          <CardDescription>
            Shown on the public product page. List only features that exist today.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {features.fields.length === 0 && (
            <p className="text-sm text-muted-foreground">No features listed.</p>
          )}
          {features.fields.map((field, index) => {
            const featureErrors = errors.features?.[index] ?? {}
            return (
              <fieldset
                key={field.id}
                className="grid gap-3 rounded-lg border p-3 md:grid-cols-[1fr_2fr_auto]"
              >
                <legend className="sr-only">Feature {index + 1}</legend>
                <Field
                  id={`feature-${index}-title`}
                  label="Feature"
                  error={featureErrors.title?.message}
                >
                  <Input id={`feature-${index}-title`} {...register(`features.${index}.title`)} />
                </Field>
                <Field
                  id={`feature-${index}-description`}
                  label="Short description"
                  error={featureErrors.description?.message}
                >
                  <Input
                    id={`feature-${index}-description`}
                    {...register(`features.${index}.description`)}
                  />
                </Field>
                <div className="flex items-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => features.remove(index)}
                    aria-label={`Remove feature ${index + 1}`}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              </fieldset>
            )
          })}
          <Button
            variant="outline"
            size="sm"
            onClick={() => features.append({ title: '', description: '' })}
          >
            <Plus aria-hidden="true" /> Add feature
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pricing</CardTitle>
          <CardDescription>Only add plans that are confirmed for sale.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {pricing.fields.length === 0 && (
            <p className="text-sm text-muted-foreground">No pricing recorded.</p>
          )}
          {pricing.fields.map((field, index) => {
            const planErrors = errors.pricing?.[index] ?? {}
            return (
              <fieldset key={field.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-6">
                <legend className="sr-only">Plan {index + 1}</legend>
                <div className="md:col-span-2">
                  <Field id={`plan-${index}-name`} label="Plan" error={planErrors.name?.message}>
                    <Input id={`plan-${index}-name`} {...register(`pricing.${index}.name`)} />
                  </Field>
                </div>
                <Field
                  id={`plan-${index}-amount`}
                  label="Amount"
                  error={planErrors.amount?.message}
                >
                  <Input
                    id={`plan-${index}-amount`}
                    inputMode="decimal"
                    {...register(`pricing.${index}.amount`)}
                  />
                </Field>
                <Field
                  id={`plan-${index}-currency`}
                  label="Currency"
                  error={planErrors.currency?.message}
                >
                  <Input
                    id={`plan-${index}-currency`}
                    placeholder="KES"
                    {...register(`pricing.${index}.currency`)}
                  />
                </Field>
                <Field id={`plan-${index}-interval`} label="Billing">
                  <Select id={`plan-${index}-interval`} {...register(`pricing.${index}.interval`)}>
                    <option value="">—</option>
                    {PRICING_INTERVALS.map((i) => (
                      <option key={i.value} value={i.value}>
                        {i.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="flex items-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => pricing.remove(index)}
                    aria-label={`Remove plan ${index + 1}`}
                  >
                    <Trash2 aria-hidden="true" /> Remove
                  </Button>
                </div>
              </fieldset>
            )
          })}
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              pricing.append({ name: '', amount: '', currency: 'KES', interval: '', notes: '' })
            }
          >
            <Plus aria-hidden="true" /> Add plan
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-5">
          <Checkbox
            id="details_confirmed"
            label="Details confirmed by the product owner"
            description="Unconfirmed products are labelled 'Awaiting confirmation' everywhere they appear."
            {...register('details_confirmed')}
          />
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
