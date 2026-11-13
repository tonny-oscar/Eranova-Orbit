import { Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { Logo } from '@/components/brand/Logo'
import { buttonVariants } from '@/components/ui/button'
import { captureAttribution } from '@/features/public/attribution'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/products', label: 'Products' },
  { to: '/solutions', label: 'Solutions' },
  { to: '/pricing', label: 'Pricing' },
  { to: '/resources', label: 'Resources' },
  { to: '/about', label: 'About' },
  { to: '/contact', label: 'Contact' },
]

const FOOTER = [
  { to: '/careers', label: 'Careers' },
  { to: '/support', label: 'Support' },
  { to: '/privacy', label: 'Privacy notice' },
  { to: '/login', label: 'Staff sign in' },
]

function NavItems({ onNavigate, className }) {
  return NAV.map((item) => (
    <NavLink
      key={item.to}
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'rounded-md px-3 py-2 text-sm transition-colors',
          isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
          className,
        )
      }
    >
      {item.label}
    </NavLink>
  ))
}

export function PublicLayout() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [menuPath, setMenuPath] = useState(location.pathname)
  if (menuPath !== location.pathname) {
    setMenuPath(location.pathname)
    setOpen(false)
  }

  useEffect(() => {
    captureAttribution()
  }, [])

  useEffect(() => {
    window.scrollTo?.(0, 0)
  }, [location.pathname])

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Link to="/" aria-label="Eranova home">
            <Logo />
          </Link>
          <nav aria-label="Primary" className="ml-4 hidden items-center gap-1 lg:flex">
            <NavItems />
          </nav>
          <div className="ml-auto hidden items-center gap-2 sm:flex">
            <Link to="/login" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
              Staff sign in
            </Link>
            <Link to="/demo" className={buttonVariants({ size: 'sm' })}>
              Request a demo
            </Link>
          </div>
          <button
            type="button"
            className="ml-auto rounded-md p-2 lg:hidden sm:ml-2"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
        {open && (
          <nav aria-label="Mobile" className="border-t px-4 py-3 lg:hidden">
            <div className="flex flex-col">
              <NavItems onNavigate={() => setOpen(false)} className="py-3" />
              <Link to="/demo" className={cn(buttonVariants(), 'mt-2')}>
                Request a demo
              </Link>
            </div>
          </nav>
        )}
      </header>

      <main id="content" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>© {new Date().getFullYear()} Eranova Technologies</p>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
            {FOOTER.map((item) => (
              <Link key={item.to} to={item.to} className="hover:text-foreground">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </div>
  )
}
