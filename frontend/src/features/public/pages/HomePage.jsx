import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button'
import { ErrorState, Skeleton } from '@/components/ui/states'
import { usePageMeta } from '@/hooks/usePageMeta'
import { usePublicPage, usePublicProducts } from '../api'
import { Container, ProductCard, Sections } from '../components'

function Hero() {
  const page = usePublicPage('home')
  const title = page.data?.title ?? 'Software products from Eranova Technologies'
  const summary =
    page.data?.summary ?? 'Explore our products, or talk to our team about your needs.'
  usePageMeta(null, page.data?.seo_description || summary)

  return (
    <section className="relative overflow-hidden border-b">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(34,211,238,0.14),transparent_60%)]"
      />
      <Container className="relative py-20 text-center sm:py-28">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
          Eranova Technologies
        </p>
        {page.isPending ? (
          <Skeleton className="mx-auto h-12 max-w-2xl" />
        ) : (
          <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
            {title}
          </h1>
        )}
        <p className="mx-auto mt-5 max-w-xl text-muted-foreground">{summary}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to="/products" className={buttonVariants({ size: 'lg' })}>
            Explore products <ArrowRight aria-hidden="true" />
          </Link>
          <Link to="/demo" className={buttonVariants({ size: 'lg', variant: 'outline' })}>
            Request a demo
          </Link>
        </div>
      </Container>
    </section>
  )
}

function FeaturedProducts() {
  const { data, isPending, isError, error, refetch } = usePublicProducts()
  return (
    <Container className="py-16">
      <div className="mb-6 flex items-end justify-between gap-4">
        <h2 className="text-2xl font-semibold tracking-tight">Our products</h2>
        <Link to="/products" className="text-sm text-accent hover:underline">
          View all
        </Link>
      </div>
      {isPending && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
        </div>
      )}
      {isError && <ErrorState title="Products couldn't load" error={error} onRetry={refetch} />}
      {data?.length === 0 && (
        <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          Product pages are coming soon.{' '}
          <Link to="/contact" className="text-accent">
            Contact us
          </Link>{' '}
          to learn more.
        </p>
      )}
      {data?.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.slice(0, 6).map((p) => (
            <ProductCard key={p.slug} product={p} />
          ))}
        </div>
      )}
    </Container>
  )
}

export function HomePage() {
  const page = usePublicPage('home')
  return (
    <>
      <Hero />
      <FeaturedProducts />
      {page.data?.sections?.length > 0 && (
        <Container className="pb-16">
          <Sections sections={page.data.sections} />
        </Container>
      )}
      <section className="border-t">
        <Container className="flex flex-col items-center gap-4 py-16 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">Talk to our team</h2>
          <p className="max-w-lg text-muted-foreground">
            Tell us what you need and we will help you find the right product.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link to="/contact" className={buttonVariants()}>
              Contact sales
            </Link>
            <Link to="/demo" className={buttonVariants({ variant: 'outline' })}>
              Request a demo
            </Link>
          </div>
        </Container>
      </section>
    </>
  )
}
