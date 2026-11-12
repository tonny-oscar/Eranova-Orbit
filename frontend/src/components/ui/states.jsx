import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} aria-hidden="true" />
}

export function LoadingState({ label = 'Loading…', className }) {
  return (
    <div
      role="status"
      className={cn('flex items-center justify-center gap-2 p-8 text-muted-foreground', className)}
    >
      <Loader2 className="size-5 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, description, children, className }) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center',
        className,
      )}
    >
      <Icon className="size-8 text-muted-foreground" aria-hidden="true" />
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {children}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', error, onRetry, className }) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-8 text-center',
        className,
      )}
    >
      <AlertTriangle className="size-8 text-destructive" aria-hidden="true" />
      <p className="font-medium">{title}</p>
      {error?.message && <p className="max-w-md text-sm text-muted-foreground">{error.message}</p>}
      {error?.correlationId && (
        <p className="font-mono text-xs text-muted-foreground">Reference: {error.correlationId}</p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
