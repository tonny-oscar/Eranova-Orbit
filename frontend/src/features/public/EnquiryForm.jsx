import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox, Select, Textarea } from '@/components/ui/form-controls'
import { FieldError, Input, Label } from '@/components/ui/input'
import { usePublicProducts, useSubmitEnquiry } from './api'
import { getAttribution } from './attribution'

const today = () => new Date().toISOString().slice(0, 10)

function buildSchema(type) {
  return z.object({
    full_name: z.string().trim().min(2, { message: 'Enter your name.' }).max(200),
    email: z.email({ message: 'Enter a valid email address.' }),
    phone: z
      .string()
      .max(40)
      .regex(/^[0-9+()\-\s]*$/, { message: 'Use digits, spaces and + ( ) - only.' }),
    organization: z.string().max(200),
    product_slug: z.string(),
    message:
      type === 'contact'
        ? z
            .string()
            .trim()
            .min(10, { message: 'Tell us a little more (at least 10 characters).' })
            .max(3000)
        : z.string().max(3000),
    preferred_date: z
      .string()
      .refine((v) => !v || v >= today(), { message: 'Choose today or a future date.' }),
    consent_privacy: z.literal(true, { message: 'Please accept the privacy notice to continue.' }),
    consent_marketing: z.boolean(),
    website: z.string(),
  })
}

export function EnquiryForm({ type, defaultProduct = '' }) {
  const startedAt = useRef(0)
  useEffect(() => {
    startedAt.current = Date.now()
  }, [])
  const products = usePublicProducts()
  const submit = useSubmitEnquiry()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(buildSchema(type)),
    defaultValues: {
      full_name: '',
      email: '',
      phone: '',
      organization: '',
      product_slug: defaultProduct,
      message: '',
      preferred_date: '',
      consent_privacy: false,
      consent_marketing: false,
      website: '',
    },
  })

  if (submit.isSuccess) {
    return (
      <div
        role="status"
        className="flex flex-col items-center gap-3 rounded-xl border bg-card p-10 text-center"
      >
        <CheckCircle2 className="size-10 text-success" aria-hidden="true" />
        <p className="text-lg font-semibold">
          Thank you, we received your {type === 'demo' ? 'demo request' : 'message'}.
        </p>
        <p className="max-w-md text-sm text-muted-foreground">{submit.data?.message}</p>
        <Link to="/products" className="text-sm text-accent hover:underline">
          Continue browsing products
        </Link>
      </div>
    )
  }

  const send = (values) => {
    submit.mutate({
      type,
      full_name: values.full_name.trim(),
      email: values.email,
      phone: values.phone.trim() || null,
      organization: values.organization.trim() || null,
      product_slug: values.product_slug || null,
      message: values.message.trim(),
      preferred_date: values.preferred_date || null,
      consent_privacy: values.consent_privacy,
      consent_marketing: values.consent_marketing,
      website: values.website,
      elapsed_ms: Date.now() - startedAt.current,
      attribution: getAttribution(),
    })
  }

  const field = (name) => ({
    id: `enquiry-${name}`,
    'aria-invalid': errors[name] ? 'true' : undefined,
    'aria-describedby': errors[name] ? `enquiry-${name}-error` : undefined,
    ...register(name),
  })

  return (
    <form
      onSubmit={(event) => handleSubmit(send)(event)}
      noValidate
      className="space-y-4 rounded-xl border bg-card p-6"
    >
      {submit.isError && <Alert variant="error" title={submit.error.message} />}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="enquiry-full_name">Full name</Label>
          <Input autoComplete="name" {...field('full_name')} />
          <FieldError id="enquiry-full_name-error">{errors.full_name?.message}</FieldError>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="enquiry-email">Email</Label>
          <Input type="email" autoComplete="email" {...field('email')} />
          <FieldError id="enquiry-email-error">{errors.email?.message}</FieldError>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="enquiry-phone">Phone (optional)</Label>
          <Input type="tel" autoComplete="tel" {...field('phone')} />
          <FieldError id="enquiry-phone-error">{errors.phone?.message}</FieldError>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="enquiry-organization">Organisation (optional)</Label>
          <Input autoComplete="organization" {...field('organization')} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="enquiry-product_slug">Product of interest</Label>
          <Select {...field('product_slug')}>
            <option value="">Not sure yet</option>
            {(products.data ?? []).map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name}
              </option>
            ))}
          </Select>
        </div>
        {type === 'demo' && (
          <div className="space-y-1.5">
            <Label htmlFor="enquiry-preferred_date">Preferred demo date (optional)</Label>
            <Input type="date" min={today()} {...field('preferred_date')} />
            <FieldError id="enquiry-preferred_date-error">
              {errors.preferred_date?.message}
            </FieldError>
          </div>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="enquiry-message">
          {type === 'demo' ? 'What would you like to see? (optional)' : 'How can we help?'}
        </Label>
        <Textarea rows={5} {...field('message')} />
        <FieldError id="enquiry-message-error">{errors.message?.message}</FieldError>
      </div>

      {/* Honeypot: hidden from people and assistive tech; bots tend to fill it. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label htmlFor="enquiry-website">Website</label>
        <input id="enquiry-website" tabIndex={-1} autoComplete="off" {...register('website')} />
      </div>

      <div className="space-y-3 border-t pt-4">
        <div>
          <Checkbox
            id="enquiry-consent_privacy"
            label={
              <>
                I have read the{' '}
                <Link to="/privacy" target="_blank" className="text-accent underline">
                  privacy notice
                </Link>{' '}
                and agree that Eranova may use these details to respond to my enquiry.
              </>
            }
            {...register('consent_privacy')}
          />
          <FieldError id="enquiry-consent_privacy-error">
            {errors.consent_privacy?.message}
          </FieldError>
        </div>
        <Checkbox
          id="enquiry-consent_marketing"
          label="Send me occasional product updates (optional)"
          {...register('consent_marketing')}
        />
      </div>

      <Button type="submit" size="lg" loading={submit.isPending}>
        {type === 'demo' ? 'Request demo' : 'Send message'}
      </Button>
    </form>
  )
}
