import { Link } from 'react-router'
import { ErrorState, Skeleton } from '@/components/ui/states'
import { usePageMeta } from '@/hooks/usePageMeta'
import { usePublicPage, usePublicProducts } from '../api'
import { Container, PageIntro, Sections } from '../components'
import { formatPrice } from '../format'

export function PricingPage() {
  const page = usePublicPage('pricing')
  const products = usePublicProducts()
  usePageMeta('Pricing', page.data?.seo_description || 'Pricing for Eranova products.')

  return (
    <>
      <PageIntro
        eyebrow="Pricing"
        title={page.data?.title ?? 'Pricing'}
        summary={
          page.data?.summary ?? 'Published plans for each product. Contact us for anything else.'
        }
      />
      <Container className="space-y-12 py-12">
        {products.isPending && <Skeleton className="h-40" />}
        {products.isError && (
          <ErrorState
            title="Pricing couldn't load"
            error={products.error}
            onRetry={products.refetch}
          />
        )}
        {products.data?.length === 0 && (
          <p className="text-muted-foreground">
            Pricing will be published here soon.{' '}
            <Link to="/contact" className="text-accent">
              Contact us
            </Link>{' '}
            for a quote.
          </p>
        )}
        {products.data?.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            {products.data.map((product) => (
              <section key={product.slug} className="rounded-xl border bg-card p-5">
                <div className="mb-3 flex items-baseline justify-between gap-3">
                  <h2 className="font-semibold">
                    <Link to={`/products/${product.slug}`} className="hover:text-accent">
                      {product.name}
                    </Link>
                  </h2>
                  {product.category && (
                    <span className="text-xs text-muted-foreground">{product.category}</span>
                  )}
                </div>
                {product.pricing.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Price on request.{' '}
                    <Link to={`/contact?product=${product.slug}`} className="text-accent">
                      Get a quote
                    </Link>
                  </p>
                ) : (
                  <ul className="divide-y text-sm">
                    {product.pricing.map((plan) => (
                      <li key={plan.name} className="flex justify-between gap-3 py-2">
                        <span>{plan.name}</span>
                        <span className="text-muted-foreground">{formatPrice(plan)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        )}
        {page.data?.sections?.length > 0 && <Sections sections={page.data.sections} />}
      </Container>
    </>
  )
}
