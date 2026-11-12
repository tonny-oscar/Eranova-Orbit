import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'
import { LogoMark } from '@/components/brand/Logo'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldError, Input, Label } from '@/components/ui/input'
import { LoadingState } from '@/components/ui/states'
import { safeNextPath } from './redirects'
import { useLogin, useMe } from './hooks'

const loginSchema = z.object({
  email: z.email({ message: 'Enter a valid email address.' }).max(320),
  password: z.string().min(1, { message: 'Enter your password.' }).max(128),
})

export function LoginPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('next'))
  const { data: me, isPending: checkingSession } = useMe()
  const loginMutation = useLogin()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } })

  if (checkingSession) return <LoadingState className="min-h-dvh" />
  if (me) return <Navigate to={next} replace />

  const onSubmit = handleSubmit((values) => {
    loginMutation.mutate(values, { onSuccess: () => navigate(next, { replace: true }) })
  })

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden px-4 py-10">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.18),transparent_60%)]"
      />
      <div className="relative w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <LogoMark className="size-11" />
          <div>
            <p className="text-lg font-semibold tracking-tight">Eranova Orbit</p>
            <p className="text-sm text-muted-foreground">One company. One command centre.</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle as="h1">Sign in</CardTitle>
            <CardDescription>Use your Eranova staff account.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} noValidate className="space-y-4">
              {loginMutation.isError && (
                <Alert variant="error" title={loginMutation.error.message} />
              )}

              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  autoFocus
                  aria-invalid={errors.email ? 'true' : undefined}
                  aria-describedby={errors.email ? 'email-error' : undefined}
                  {...register('email')}
                />
                <FieldError id="email-error">{errors.email?.message}</FieldError>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={errors.password ? 'true' : undefined}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  {...register('password')}
                />
                <FieldError id="password-error">{errors.password?.message}</FieldError>
              </div>

              <Button type="submit" className="w-full" loading={loginMutation.isPending}>
                Sign in
              </Button>
            </form>
            <p className="mt-4 text-center text-xs text-muted-foreground">
              Forgot your password? Contact your Orbit administrator to reset it.
            </p>
          </CardContent>
        </Card>

        <p className="text-center text-sm">
          <Link to="/" className="text-muted-foreground hover:text-foreground">
            ← Back to home
          </Link>
        </p>
      </div>
    </main>
  )
}
