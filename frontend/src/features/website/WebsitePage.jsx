import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { ErrorState, LoadingState } from '@/components/ui/states'
import { RequirePermission } from '@/features/auth/guards'
import { useMe } from '@/features/auth/hooks'
import { formatDateTime } from '@/lib/utils'
import { useContentPages } from './api'
import { PUBLIC_PATHS } from './paths'

function PagesTable() {
  const { data: me } = useMe()
  const { data, isPending, isError, error, refetch } = useContentPages()
  if (isPending) return <LoadingState label="Loading pages…" />
  if (isError) return <ErrorState title="Couldn't load pages" error={error} onRetry={refetch} />

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Website pages</caption>
          <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Page
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Last published
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                <span className="sr-only">Public link</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.map((page) => (
              <tr key={page.slug} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <Link to={`/app/website/${page.slug}`} className="font-medium hover:text-accent">
                    {page.label}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {page.is_published ? (
                      <Badge variant="success">Published</Badge>
                    ) : (
                      <Badge>Not published</Badge>
                    )}
                    {page.has_unpublished_changes && (
                      <Badge variant="warning">Unpublished changes</Badge>
                    )}
                  </div>
                </td>
                <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                  {page.published_at ? formatDateTime(page.published_at, me.company.timezone) : '—'}
                </td>
                <td className="px-4 py-3 text-right">
                  <a
                    href={PUBLIC_PATHS[page.slug]}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                  >
                    View <ExternalLink className="size-3" aria-hidden="true" />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function WebsitePage() {
  return (
    <>
      <PageHeader
        title="Website"
        description="Edit public pages. Changes stay in draft until someone with approval rights publishes them. Product pages are managed from each product."
      />
      <RequirePermission permission="content.read">
        <PagesTable />
      </RequirePermission>
    </>
  )
}
