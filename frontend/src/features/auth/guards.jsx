import { ShieldOff } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { useMe, usePermissions } from './hooks'

/**
 * UX guard only. Every protected API enforces authentication and permissions
 * on the server; hiding UI is never the security boundary.
 */
export function RequireAuth() {
  const location = useLocation()
  const { data: me, isPending, isError, error, refetch } = useMe()

  if (isPending) return <LoadingState label="Checking your session…" className="min-h-dvh" />
  if (isError) {
    return (
      <div className="grid min-h-dvh place-items-center p-6">
        <ErrorState title="We couldn't load your session" error={error} onRetry={refetch} />
      </div>
    )
  }
  if (!me) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return <Outlet />
}

export function RequirePermission({ permission, children }) {
  const { has } = usePermissions()
  if (!has(permission)) {
    return (
      <EmptyState
        icon={ShieldOff}
        title="You don't have access to this page"
        description="Ask a Super Admin if you need this access for your work."
      />
    )
  }
  return children
}
