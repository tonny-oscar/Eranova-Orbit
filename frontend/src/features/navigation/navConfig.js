import {
  Boxes,
  Briefcase,
  Building,
  FolderKanban,
  Globe,
  Inbox,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  UsersRound,
  Workflow,
} from 'lucide-react'

/**
 * Command-centre navigation. Only delivered modules appear; each later phase
 * adds its items here rather than shipping placeholder links.
 *
 * `permission` hides items the user cannot use (UX only — the API enforces access).
 */
export const NAV_SECTIONS = [
  {
    label: 'Command centre',
    items: [
      { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/app/me', label: 'My work', icon: Briefcase },
    ],
  },
  {
    label: 'Business',
    items: [
      { to: '/app/products', label: 'Products', icon: Boxes, permission: 'product.read' },
      { to: '/app/leads', label: 'Leads', icon: Inbox, permission: 'lead.read' },
      { to: '/app/customers', label: 'Customers', icon: Building, permission: 'customer.read' },
      { to: '/app/website', label: 'Website', icon: Globe, permission: 'content.read' },
    ],
  },
  {
    label: 'Delivery',
    items: [
      { to: '/app/projects', label: 'Projects', icon: FolderKanban, permission: 'project.read' },
      { to: '/app/tasks', label: 'Tasks', icon: ListChecks },
    ],
  },
  {
    label: 'People',
    items: [{ to: '/app/team', label: 'Team', icon: UsersRound, permission: 'employee.read' }],
  },
  {
    label: 'Administration',
    items: [
      { to: '/app/settings/users', label: 'Users', icon: Users, permission: 'user.read' },
      { to: '/app/settings/roles', label: 'Roles', icon: ShieldCheck, permission: 'role.read' },
      {
        to: '/app/settings/pipeline',
        label: 'Sales pipeline',
        icon: Workflow,
        permission: 'lead.manage',
      },
      {
        to: '/app/settings/audit-log',
        label: 'Audit log',
        icon: ScrollText,
        permission: 'audit_log.read',
      },
      { to: '/app/settings/profile', label: 'Settings', icon: Settings },
    ],
  },
]

export function visibleSections(has) {
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.permission || has(item.permission)),
  })).filter((section) => section.items.length > 0)
}
