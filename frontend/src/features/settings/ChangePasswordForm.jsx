import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { FieldError, Input, Label } from '@/components/ui/input'
import { useChangePassword } from '@/features/auth/hooks'

const schema = z
  .object({
    current_password: z.string().min(1, { message: 'Enter your current password.' }),
    new_password: z
      .string()
      .min(12, { message: 'Use at least 12 characters.' })
      .max(128, { message: 'Use at most 128 characters.' }),
    confirm_password: z.string(),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ['confirm_password'],
    message: 'Passwords do not match.',
  })

const fields = [
  { name: 'current_password', label: 'Current password', autoComplete: 'current-password' },
  { name: 'new_password', label: 'New password', autoComplete: 'new-password' },
  { name: 'confirm_password', label: 'Confirm new password', autoComplete: 'new-password' },
]

export function ChangePasswordForm() {
  const mutation = useChangePassword()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema) })

  const onSubmit = handleSubmit(({ current_password, new_password }) => {
    mutation.mutate({ current_password, new_password }, { onSuccess: () => reset() })
  })

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-md space-y-4">
      {mutation.isSuccess && (
        <Alert variant="success" title="Password updated">
          Your other signed-in sessions have been signed out.
        </Alert>
      )}
      {mutation.isError && (
        <Alert variant="error" title={mutation.error.message}>
          {mutation.error.details?.length > 0 && (
            <ul className="list-disc pl-4">
              {mutation.error.details.map((d) => (
                <li key={d.message}>{d.message}</li>
              ))}
            </ul>
          )}
        </Alert>
      )}
      {fields.map(({ name, label, autoComplete }) => (
        <div key={name} className="space-y-1.5">
          <Label htmlFor={name}>{label}</Label>
          <Input
            id={name}
            type="password"
            autoComplete={autoComplete}
            aria-invalid={errors[name] ? 'true' : undefined}
            aria-describedby={errors[name] ? `${name}-error` : undefined}
            {...register(name)}
          />
          <FieldError id={`${name}-error`}>{errors[name]?.message}</FieldError>
        </div>
      ))}
      <Button type="submit" loading={mutation.isPending}>
        Update password
      </Button>
    </form>
  )
}
