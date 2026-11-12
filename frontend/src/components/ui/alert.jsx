import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

const styles = {
  info: 'border-orbit-blue/40 bg-orbit-blue/10',
  success: 'border-success/40 bg-success/10',
  error: 'border-destructive/40 bg-destructive/10',
}

const icons = { info: Info, success: CheckCircle2, error: AlertTriangle }

export function Alert({ variant = 'info', title, children, className }) {
  const Icon = icons[variant]
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-lg border p-3 text-sm', styles[variant], className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="space-y-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="text-muted-foreground">{children}</div>}
      </div>
    </div>
  )
}
