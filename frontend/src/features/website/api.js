import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

const BASE = '/api/v1/content/pages'

export function useContentPages() {
  return useQuery({
    queryKey: ['content', 'pages'],
    queryFn: ({ signal }) => apiRequest(BASE, { signal }),
  })
}

export function useContentPage(slug) {
  return useQuery({
    queryKey: ['content', 'page', slug],
    queryFn: ({ signal }) => apiRequest(`${BASE}/${slug}`, { signal }),
  })
}

function usePageMutation(slug, mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (page) => {
      queryClient.setQueryData(['content', 'page', slug], page)
      queryClient.invalidateQueries({ queryKey: ['content', 'pages'] })
      queryClient.invalidateQueries({ queryKey: ['public'] })
    },
  })
}

export function useSaveDraft(slug) {
  return usePageMutation(slug, (payload) =>
    apiRequest(`${BASE}/${slug}`, { method: 'PUT', body: payload }),
  )
}

export function useSetPagePublished(slug) {
  return usePageMutation(slug, (published) =>
    apiRequest(`${BASE}/${slug}/${published ? 'publish' : 'unpublish'}`, { method: 'POST' }),
  )
}
