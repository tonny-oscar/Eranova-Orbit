import { ShieldOff } from 'lucide-react'
import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { LogoMark } from '@/components/brand/Logo'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states'
import { ChangePasswordForm } from '@/features/settings/ChangePasswordForm'
import { useDevLogin, useDevLoginStatus, useMe, usePermissions } from './hooks'

function ForcedPasswordChange({ me }) {
  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="flex justify-center">
          <LogoMark className="size-11" />
        </div>
        <Card>
          <CardHeader>
            <CardTitle as="h1">Set your password</CardTitle>
            <CardDescription>
              Welcome, {me.user.full_name}. You signed in with a temporary password. Choose your own
              before continuing.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChangePasswordForm currentLabel="Temporary password" />
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

/**
 * UX guard only. Every protected API enforces authentication and permissions
 * on the server; hiding UI is never the security boundary.
 */
export function RequireAuth() {
  const location = useLocation()
  const { data: me, isPending, isError, error, refetch } = useMe()
  const devStatus = useDevLoginStatus({ enabled: !isPending && !me })
  const devLogin = useDevLogin()
  const autoSignIn = !me && devStatus.data?.enabled && !devLogin.isError

  useEffect(() => {
    if (autoSignIn && devLogin.isIdle) devLogin.mutate()
  }, [autoSignIn, devLogin])

  if (isPending || (!me && devStatus.isPending) || autoSignIn) {
    return <LoadingState label="Checking your session…" className="min-h-dvh" />
  }
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
  if (me.user.must_change_password) return <ForcedPasswordChange me={me} />
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
