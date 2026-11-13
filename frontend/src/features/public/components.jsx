import { ArrowRight, Hammer } from 'lucide-react'
import { Link } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function Container({ className, children }) {
  return <div className={cn('mx-auto max-w-6xl px-4 sm:px-6', className)}>{children}</div>
}

export function PageIntro({ eyebrow, title, summary }) {
  return (
    <section className="border-b bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.12),transparent_60%)]">
      <Container className="py-14 sm:py-20">
        {eyebrow && (
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
            {eyebrow}
          </p>
        )}
        <h1 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        {summary && <p className="mt-4 max-w-2xl text-muted-foreground">{summary}</p>}
      </Container>
    </section>
  )
}

/** Renders CMS sections as plain text: no HTML from content is ever injected. */
export function Sections({ sections }) {
  return (
    <div className="space-y-10">
      {sections.map((section, index) => (
        <section key={`${section.heading}-${index}`} className="max-w-3xl">
          {section.heading && (
            <h2 className="mb-3 text-xl font-semibold tracking-tight">{section.heading}</h2>
          )}
          {section.body
            .split(/\n{2,}/)
            .filter(Boolean)
            .map((paragraph, i) => (
              <p key={i} className="mb-3 whitespace-pre-line leading-relaxed text-muted-foreground">
                {paragraph}
              </p>
            ))}
        </section>
      ))}
    </div>
  )
}

export function BeingPrepared({ what = 'This page' }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-10 text-center">
      <Hammer className="size-8 text-muted-foreground" aria-hidden="true" />
      <p className="font-medium">{what} is being prepared.</p>
      <p className="max-w-md text-sm text-muted-foreground">
        In the meantime, our team is happy to answer your questions directly.
      </p>
      <Link to="/contact" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
        Contact us
      </Link>
    </div>
  )
}

const STATUS_LABEL = { beta: 'Beta', live: null, maintenance: 'Maintenance' }

export function ProductCard({ product }) {
  const label = STATUS_LABEL[product.lifecycle_status]
  return (
    <Link
      to={`/products/${product.slug}`}
      className="group flex flex-col rounded-xl border bg-card p-5 transition-colors hover:border-accent/50"
    >
      <div className="mb-3 flex items-center gap-3">
        {product.logo_url ? (
          <img src={product.logo_url} alt="" className="size-10 rounded-lg object-contain" />
        ) : (
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-lg bg-primary/15 font-semibold text-accent"
          >
            {product.name[0]}
          </span>
        )}
        <div className="min-w-0">
          <p className="truncate font-semibold">{product.name}</p>
          {product.category && <p className="text-xs text-muted-foreground">{product.category}</p>}
        </div>
        {label && (
          <Badge variant="accent" className="ml-auto">
            {label}
          </Badge>
        )}
      </div>
      <p className="flex-1 text-sm text-muted-foreground">
        {product.tagline ?? product.description.slice(0, 140)}
      </p>
      <span className="mt-4 inline-flex items-center gap-1 text-sm text-accent">
        Learn more{' '}
        <ArrowRight
          className="size-4 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </span>
    </Link>
  )
}
