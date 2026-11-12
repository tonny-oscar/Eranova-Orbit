import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import { Logo } from '@/components/brand/Logo'
import { buttonVariants } from '@/components/ui/button'

/**
 * Minimal public entry point. The product marketplace (catalogue, product
 * pages, enquiries) is delivered in Phase 2; no product claims are made here.
 */
export function HomePage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <Logo />
        <Link to="/login" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          Staff sign in
        </Link>
      </header>
      <main className="relative flex flex-1 items-center overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(34,211,238,0.10),transparent_55%)]"
        />
        <section className="relative mx-auto max-w-3xl px-6 py-24 text-center">
          <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-accent">
            Eranova Technologies
          </p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            One company. One command centre.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-muted-foreground">
            Eranova Orbit brings our products, teams, customers and operations together in one
            place. Our public product marketplace is coming soon.
          </p>
          <div className="mt-8 flex justify-center">
            <Link to="/login" className={buttonVariants({ size: 'lg' })}>
              Sign in to Orbit <ArrowRight aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>
      <footer className="px-6 py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} Eranova Technologies
      </footer>
    </div>
  )
}
