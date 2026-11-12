import { AuditLogPage } from '@/features/admin/AuditLogPage'
import { RolesPage } from '@/features/admin/RolesPage'
import { RequireAuth } from '@/features/auth/guards'
import { LoginPage } from '@/features/auth/LoginPage'
import { OverviewPage } from '@/features/dashboard/OverviewPage'
import { ProfilePage } from '@/features/settings/ProfilePage'
import { AppLayout } from '@/layouts/AppLayout'
import { NotFoundPage, RouteErrorPage } from '@/routes/ErrorPages'
import { HomePage } from '@/routes/HomePage'

export const routes = [
  {
    errorElement: <RouteErrorPage />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage /> },
      {
        path: '/app',
        element: <RequireAuth />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { index: true, element: <OverviewPage /> },
              { path: 'settings/profile', element: <ProfilePage /> },
              { path: 'settings/roles', element: <RolesPage /> },
              { path: 'settings/audit-log', element: <AuditLogPage /> },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
