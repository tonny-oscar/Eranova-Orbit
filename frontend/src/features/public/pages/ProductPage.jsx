import { Check, ExternalLink } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { usePageMeta } from '@/hooks/usePageMeta'
import { ApiError } from '@/lib/api/client'
import { usePublicProduct } from '../api'
import { Container } from '../components'
import { formatPrice } from '../format'

function NotFound() {
  return (
    <Container className="py-24 text-center">
      <h1 className="text-2xl font-semibold">Product not found</h1>
      <p className="mt-2 text-muted-foreground">It may have moved or is not available yet.</p>
      <Link to="/products" className={buttonVariants({ variant: 'outline', className: 'mt-6' })}>
        All products
      </Link>
    </Container>
  )
}

export function ProductPage() {
  const { slug } = useParams()
  const { data: product, isPending, isError, error, refetch } = usePublicProduct(slug)
  usePageMeta(product?.name, product?.tagline ?? product?.description?.slice(0, 160))

  if (isPending) return <LoadingState className="min-h-[50dvh]" />
  if (isError && error instanceof ApiError && error.status === 404) return <NotFound />
  if (isError) {
    return (
      <Container className="py-16">
        <ErrorState title="This product couldn't load" error={error} onRetry={refetch} />
      </Container>
    )
  }

  const contactQuery = `?product=${encodeURIComponent(product.slug)}`
  return (
    <>
      <section className="border-b bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.12),transparent_60%)]">
        <Container className="py-14 sm:py-20">
          <Link to="/products" className="text-sm text-muted-foreground hover:text-foreground">
            ← All products
          </Link>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{product.name}</h1>
            {product.lifecycle_status === 'beta' && <Badge variant="accent">Beta</Badge>}
            {product.category && <Badge>{product.category}</Badge>}
          </div>
          {product.tagline && (
            <p className="mt-3 max-w-2xl text-lg text-muted-foreground">{product.tagline}</p>
          )}
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to={`/demo${contactQuery}`} className={buttonVariants({ size: 'lg' })}>
              Request a demo
            </Link>
            <Link
              to={`/contact${contactQuery}`}
              className={buttonVariants({ size: 'lg', variant: 'outline' })}
            >
              Contact sales
            </Link>
            {product.website_url && (
              <a
                href={product.website_url}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonVariants({ size: 'lg', variant: 'ghost' })}
              >
                Visit website <ExternalLink aria-hidden="true" />
              </a>
            )}
          </div>
        </Container>
      </section>

      <Container className="grid gap-12 py-14 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-12">
          <section>
            <h2 className="mb-3 text-xl font-semibold">Overview</h2>
            <p className="whitespace-pre-line leading-relaxed text-muted-foreground">
              {product.description}
            </p>
          </section>
          {product.features.length > 0 && (
            <section>
              <h2 className="mb-4 text-xl font-semibold">Features</h2>
              <ul className="grid gap-4 sm:grid-cols-2">
                {product.features.map((feature) => (
                  <li key={feature.title} className="flex gap-3 rounded-lg border p-4">
                    <Check className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                    <div>
                      <p className="font-medium">{feature.title}</p>
                      {feature.description && (
                        <p className="mt-1 text-sm text-muted-foreground">{feature.description}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="space-y-6">
          <section className="rounded-xl border bg-card p-5">
            <h2 className="mb-3 font-semibold">Pricing</h2>
            {product.pricing.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Pricing is available on request.{' '}
                <Link to={`/contact${contactQuery}`} className="text-accent">
                  Ask our team
                </Link>
                .
              </p>
            ) : (
              <ul className="divide-y">
                {product.pricing.map((plan) => (
                  <li key={plan.name} className="py-2.5 text-sm">
                    <div className="flex justify-between gap-3">
                      <span className="font-medium">{plan.name}</span>
                      <span className="text-muted-foreground">{formatPrice(plan)}</span>
                    </div>
                    {plan.notes && (
                      <p className="mt-1 text-xs text-muted-foreground">{plan.notes}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
          {(product.docs_url || product.status_page_url || product.support_email) && (
            <section className="rounded-xl border bg-card p-5 text-sm">
              <h2 className="mb-3 font-semibold">Resources</h2>
              <ul className="space-y-2">
                {product.docs_url && (
                  <li>
                    <a
                      href={product.docs_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline"
                    >
                      Documentation
                    </a>
                  </li>
                )}
                {product.status_page_url && (
                  <li>
                    <a
                      href={product.status_page_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline"
                    >
                      Service status
                    </a>
                  </li>
                )}
                {product.support_email && (
                  <li>
                    Support:{' '}
                    <a
                      href={`mailto:${product.support_email}`}
                      className="text-accent hover:underline"
                    >
                      {product.support_email}
                    </a>
                  </li>
                )}
              </ul>
            </section>
          )}
        </aside>
      </Container>
    </>
  )
}
