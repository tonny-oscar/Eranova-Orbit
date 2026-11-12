import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'

const tabs = [
  { to: '/app/team', label: 'People', end: true },
  { to: '/app/team/departments', label: 'Departments' },
]

export function TeamTabs() {
  return (
    <nav aria-label="Team sections" className="mb-4 flex gap-1 border-b">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              '-mb-px border-b-2 px-3 py-2 text-sm',
              isActive
                ? 'border-accent text-foreground'
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
