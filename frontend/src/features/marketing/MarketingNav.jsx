import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/app/marketing', label: 'Campaigns', end: true },
  { to: '/app/marketing/content', label: 'Content studio' },
  { to: '/app/marketing/calendar', label: 'Calendar' },
]

export function MarketingNav() {
  return (
    <nav aria-label="Marketing" className="mb-4 flex gap-1 border-b">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              '-mb-px border-b-2 px-3 py-2 text-sm',
              isActive
                ? 'border-accent font-medium text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
