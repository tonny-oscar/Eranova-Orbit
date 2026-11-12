import { cn } from '@/lib/utils'

const fieldBase =
  'w-full rounded-md border border-input bg-navy-900/60 px-3 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive'

export function Select({ className, children, ...props }) {
  return (
    <select className={cn(fieldBase, 'h-10 py-2', className)} {...props}>
      {children}
    </select>
  )
}

export function Textarea({ className, rows = 4, ...props }) {
  return (
    <textarea
      rows={rows}
      className={cn(fieldBase, 'py-2 placeholder:text-muted-foreground', className)}
      {...props}
    />
  )
}

export function Checkbox({ id, label, description, className, ...props }) {
  return (
    <div className={cn('flex items-start gap-3', className)}>
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 size-4 rounded border-input accent-[var(--color-primary)]"
        {...props}
      />
      <label htmlFor={id} className="text-sm">
        <span className="font-medium">{label}</span>
        {description && <span className="block text-muted-foreground">{description}</span>}
      </label>
    </div>
  )
}
