import { cn } from '@/lib/utils'

export function LogoMark({ className }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={cn('size-8', className)}>
      <rect width="32" height="32" rx="8" className="fill-navy-800" />
      <ellipse
        cx="16"
        cy="16"
        rx="11"
        ry="5.5"
        transform="rotate(-25 16 16)"
        className="stroke-orbit-cyan"
        strokeWidth="1.6"
      />
      <circle cx="16" cy="16" r="4" className="fill-orbit-blue" />
      <circle cx="25.2" cy="11.6" r="1.8" className="fill-orbit-cyan" />
    </svg>
  )
}

export function Logo({ collapsed = false, className }) {
  return (
    <span className={cn('flex items-center gap-2.5', className)}>
      <LogoMark />
      {!collapsed && (
        <span className="leading-tight">
          <span className="block text-sm font-semibold tracking-tight">Eranova Orbit</span>
          <span className="block text-[11px] text-muted-foreground">Command centre</span>
        </span>
      )}
    </span>
  )
}
