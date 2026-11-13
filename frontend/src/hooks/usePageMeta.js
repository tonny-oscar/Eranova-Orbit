import { useEffect } from 'react'

const SITE = 'Eranova Technologies'

/** Sets the document title and meta description for public pages. */
export function usePageMeta(title, description) {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE}` : SITE
    let tag = document.querySelector('meta[name="description"]')
    if (!tag) {
      tag = document.createElement('meta')
      tag.setAttribute('name', 'description')
      document.head.appendChild(tag)
    }
    if (description) tag.setAttribute('content', description)
  }, [title, description])
}
