import {
  Building,
  Workflow,
  Boxes,
  Globe,
  Inbox,
  LayoutDashboard,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  UsersRound,
} from 'lucide-react'

/**
 * Command-centre navigation. Only modules that are actually delivered appear
 * here; Products, Analytics, CRM, Projects, Team, Marketing, Finance, Support
 * and NOVA are added as each phase ships, rather than as placeholder links.
 *
 * `permission` hides items the user cannot use (UX only — the API enforces access).
 */
export const NAV_SECTIONS = [
  {
    label: 'Command centre',
    items: [
      { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/app/products', label: 'Products', icon: Boxes, permission: 'product.read' },
      { to: '/app/leads', label: 'Leads', icon: Inbox, permission: 'lead.read' },
      { to: '/app/customers', label: 'Customers', icon: Building, permission: 'customer.read' },
      { to: '/app/website', label: 'Website', icon: Globe, permission: 'content.read' },
      { to: '/app/team', label: 'Team', icon: UsersRound, permission: 'employee.read' },
    ],
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
