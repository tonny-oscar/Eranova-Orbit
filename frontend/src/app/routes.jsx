import { RequireAuth } from '@/features/auth/guards'
import { LoginPage } from '@/features/auth/LoginPage'
import { NotFoundPage, RouteErrorPage } from '@/routes/ErrorPages'
import { HomePage } from '@/routes/HomePage'

// Authenticated pages are code-split so the public site and sign-in stay small.
const page = (load, name) => async () => ({ Component: (await load())[name] })

const AppLayout = page(() => import('@/layouts/AppLayout'), 'AppLayout')

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
            lazy: AppLayout,
            children: [
              {
                index: true,
                lazy: page(() => import('@/features/dashboard/OverviewPage'), 'OverviewPage'),
              },
              {
                path: 'products',
                lazy: page(() => import('@/features/products/ProductsPage'), 'ProductsPage'),
              },
              {
                path: 'products/new',
                lazy: page(() => import('@/features/products/ProductFormPages'), 'NewProductPage'),
              },
              {
                path: 'products/:productId',
                lazy: page(
                  () => import('@/features/products/ProductDetailPage'),
                  'ProductDetailPage',
                ),
              },
              {
                path: 'products/:productId/edit',
                lazy: page(() => import('@/features/products/ProductFormPages'), 'EditProductPage'),
              },
              {
                path: 'settings/profile',
                lazy: page(() => import('@/features/settings/ProfilePage'), 'ProfilePage'),
              },
              {
                path: 'settings/roles',
                lazy: page(() => import('@/features/admin/RolesPage'), 'RolesPage'),
              },
              {
                path: 'settings/audit-log',
                lazy: page(() => import('@/features/admin/AuditLogPage'), 'AuditLogPage'),
              },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
