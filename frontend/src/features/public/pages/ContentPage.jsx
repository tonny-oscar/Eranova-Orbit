import { ErrorState, LoadingState } from '@/components/ui/states'
import { usePageMeta } from '@/hooks/usePageMeta'
import { ApiError } from '@/lib/api/client'
import { usePublicPage } from '../api'
import { BeingPrepared, Container, PageIntro, Sections } from '../components'

const DEFAULT_TITLES = {
  solutions: 'Solutions',
  resources: 'Resources',
  about: 'About Eranova',
  careers: 'Careers',
  support: 'Support',
  privacy: 'Privacy notice',
}

/** Generic renderer for CMS-managed pages; shows an honest placeholder until published. */
export function ContentPage({ slug }) {
  const { data, isPending, isError, error, refetch } = usePublicPage(slug)
  const notPublished = isError && error instanceof ApiError && error.status === 404
  const title = data?.title ?? DEFAULT_TITLES[slug]
  usePageMeta(title, data?.seo_description || data?.summary)

  return (
    <>
      <PageIntro title={title} summary={data?.summary} />
      <Container className="py-12">
        {isPending && <LoadingState />}
        {notPublished && slug === 'privacy' && (
          <div className="max-w-3xl space-y-3 text-muted-foreground">
            <p>Our full privacy notice is being finalised.</p>
            <p>
              Details you send through our contact and demo forms are used only to respond to your
              enquiry. If you opt in, we may also send you product updates, and you can opt out at
              any time by contacting us.
            </p>
          </div>
        )}
        {notPublished && slug !== 'privacy' && <BeingPrepared />}
        {isError && !notPublished && (
          <ErrorState title="This page couldn't load" error={error} onRetry={refetch} />
        )}
        {data && <Sections sections={data.sections} />}
      </Container>
    </>
  )
}
