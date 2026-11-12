import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { ChangePasswordForm } from './ChangePasswordForm'

export function ProfilePage() {
  const { data: me } = useMe()
  const tz = me.company.timezone
  const rows = [
    ['Name', me.user.full_name],
    ['Email', me.user.email],
    ['Company', me.company.name],
    ['Last sign-in', formatDateTime(me.user.last_login_at, tz)],
    ['Session expires', formatDateTime(me.session_expires_at, tz)],
  ]

  return (
    <>
      <PageHeader title="Settings" description="Your account and security." />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Managed by your Orbit administrator.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="divide-y">
              {rows.map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4 py-2.5 text-sm">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="text-right">{value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Change password</CardTitle>
            <CardDescription>
              At least 12 characters. A long passphrase is stronger than a short complex password.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChangePasswordForm />
          </CardContent>
        </Card>
      </div>
    </>
  )
}
