import { useSearchParams } from 'react-router'
import { usePageMeta } from '@/hooks/usePageMeta'
import { usePublicPage } from '../api'
import { Container, PageIntro, Sections } from '../components'
import { EnquiryForm } from '../EnquiryForm'

export function ContactPage() {
  const [params] = useSearchParams()
  const page = usePublicPage('contact')
  usePageMeta('Contact', page.data?.seo_description || 'Contact the Eranova team.')
  return (
    <>
      <PageIntro
        eyebrow="Contact"
        title={page.data?.title ?? 'Talk to our team'}
        summary={
          page.data?.summary ?? 'Send us a message and the right person will get back to you.'
        }
      />
      <Container className="grid gap-10 py-12 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <EnquiryForm type="contact" defaultProduct={params.get('product') ?? ''} />
        {page.data?.sections?.length > 0 && <Sections sections={page.data.sections} />}
      </Container>
    </>
  )
}

export function DemoPage() {
  const [params] = useSearchParams()
  usePageMeta('Request a demo', 'Book a demo of an Eranova product.')
  return (
    <>
      <PageIntro
        eyebrow="Demo"
        title="Request a demo"
        summary="Tell us which product you are interested in and when suits you. We will confirm a time."
      />
      <Container className="max-w-3xl py-12">
        <EnquiryForm type="demo" defaultProduct={params.get('product') ?? ''} />
      </Container>
    </>
  )
}
