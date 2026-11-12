import { Compass } from 'lucide-react'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router'
import { buttonVariants } from '@/components/ui/button'
import { EmptyState, ErrorState } from '@/components/ui/states'

export function NotFoundPage() {
  return (
    <div className="grid min-h-[60dvh] place-items-center p-6">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="The page you requested doesn't exist or has moved."
      >
        <Link to="/app" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          Go to overview
        </Link>
      </EmptyState>
    </div>
  )
}

export function RouteErrorPage() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFoundPage />
  return (
    <div className="grid min-h-dvh place-items-center p-6">
      <ErrorState
        title="This page failed to load"
        error={{ message: 'An unexpected error occurred. Reload the page or try again later.' }}
        onRetry={() => window.location.reload()}
      />
    </div>
  )
}
