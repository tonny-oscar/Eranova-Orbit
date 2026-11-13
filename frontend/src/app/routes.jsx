import { LoadingState } from '@/components/ui/states'
import { RequireAuth } from '@/features/auth/guards'
import { LoginPage } from '@/features/auth/LoginPage'
import { HomePage } from '@/features/public/pages/HomePage'
import { PublicLayout } from '@/layouts/PublicLayout'
import { NotFoundPage, RouteErrorPage } from '@/routes/ErrorPages'

// Pages other than home and sign-in are code-split to keep the first load small.
const page = (load, name) => async () => ({ Component: (await load())[name] })

const AppLayout = page(() => import('@/layouts/AppLayout'), 'AppLayout')

const contentPage = (slug) => ({
  path: slug,
  lazy: async () => {
    const { ContentPage } = await import('@/features/public/pages/ContentPage')
    return { Component: () => <ContentPage key={slug} slug={slug} /> }
  },
})

export const routes = [
  {
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement: <LoadingState className="min-h-dvh" />,
    children: [
      {
        path: '/',
        element: <PublicLayout />,
        children: [
          { index: true, element: <HomePage /> },
          {
            path: 'products',
            lazy: page(() => import('@/features/public/pages/CatalogPage'), 'CatalogPage'),
          },
          {
            path: 'products/:slug',
            lazy: page(() => import('@/features/public/pages/ProductPage'), 'ProductPage'),
          },
          {
            path: 'pricing',
            lazy: page(() => import('@/features/public/pages/PricingPage'), 'PricingPage'),
          },
          {
            path: 'contact',
            lazy: page(() => import('@/features/public/pages/EnquiryPages'), 'ContactPage'),
          },
          {
            path: 'demo',
            lazy: page(() => import('@/features/public/pages/EnquiryPages'), 'DemoPage'),
          },
          ...['solutions', 'resources', 'about', 'careers', 'support', 'privacy'].map(contentPage),
        ],
      },
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
                path: 'leads',
                lazy: page(() => import('@/features/leads/LeadsPage'), 'LeadsPage'),
              },
              {
                path: 'leads/:leadId',
                lazy: page(() => import('@/features/leads/LeadDetailPage'), 'LeadDetailPage'),
              },
              {
                path: 'me',
                lazy: page(() => import('@/features/portal/MyWorkPage'), 'MyWorkPage'),
              },
              {
                path: 'projects',
                lazy: page(() => import('@/features/work/ProjectsPage'), 'ProjectsPage'),
              },
              {
                path: 'projects/:projectId',
                lazy: page(() => import('@/features/work/ProjectDetailPage'), 'ProjectDetailPage'),
              },
              {
                path: 'tasks',
                lazy: page(() => import('@/features/work/TasksPage'), 'TasksPage'),
              },
              {
                path: 'tasks/:taskId',
                lazy: page(() => import('@/features/work/TaskDetailPage'), 'TaskDetailPage'),
              },
              {
                path: 'customers',
                lazy: page(() => import('@/features/customers/CustomersPage'), 'CustomersPage'),
              },
              {
                path: 'customers/:customerId',
                lazy: page(
                  () => import('@/features/customers/CustomerDetailPage'),
                  'CustomerDetailPage',
                ),
              },
              {
                path: 'settings/pipeline',
                lazy: page(
                  () => import('@/features/leads/PipelineSettingsPage'),
                  'PipelineSettingsPage',
                ),
              },
              {
                path: 'website',
                lazy: page(() => import('@/features/website/WebsitePage'), 'WebsitePage'),
              },
              {
                path: 'website/:slug',
                lazy: page(() => import('@/features/website/PageEditorPage'), 'PageEditorPage'),
              },
              {
                path: 'team',
                lazy: page(() => import('@/features/team/TeamPage'), 'TeamPage'),
              },
              {
                path: 'team/departments',
                lazy: page(() => import('@/features/team/DepartmentsPage'), 'DepartmentsPage'),
              },
              {
                path: 'team/:userId',
                lazy: page(() => import('@/features/team/EmployeePage'), 'EmployeePage'),
              },
              {
                path: 'settings/profile',
                lazy: page(() => import('@/features/settings/ProfilePage'), 'ProfilePage'),
              },
              {
                path: 'settings/users',
                lazy: page(() => import('@/features/admin/UsersPage'), 'UsersPage'),
              },
              {
                path: 'settings/users/:userId',
                lazy: page(() => import('@/features/admin/UserDetailPage'), 'UserDetailPage'),
              },
              {
                path: 'settings/roles',
                lazy: page(() => import('@/features/admin/RolesPage'), 'RolesPage'),
              },
              {
                path: 'settings/roles/new',
                lazy: page(() => import('@/features/admin/RoleEditorPage'), 'RoleEditorPage'),
              },
              {
                path: 'settings/roles/:roleId',
                lazy: page(() => import('@/features/admin/RoleEditorPage'), 'RoleEditorPage'),
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
