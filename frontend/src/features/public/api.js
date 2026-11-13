import { useMutation, useQuery } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

const BASE = '/api/v1/public'

export function useSiteInfo() {
  return useQuery({
    queryKey: ['public', 'site'],
    queryFn: ({ signal }) => apiRequest(`${BASE}/site`, { signal }),
    staleTime: 5 * 60_000,
  })
}

export function usePublicProducts(filters = {}) {
  return useQuery({
    queryKey: ['public', 'products', filters],
    queryFn: ({ signal }) => apiRequest(`${BASE}/products`, { query: filters, signal }),
    staleTime: 60_000,
  })
}

export function usePublicProduct(slug) {
  return useQuery({
    queryKey: ['public', 'product', slug],
    queryFn: ({ signal }) => apiRequest(`${BASE}/products/${slug}`, { signal }),
    staleTime: 60_000,
  })
}

export function usePublicPage(slug) {
  return useQuery({
    queryKey: ['public', 'page', slug],
    queryFn: ({ signal }) => apiRequest(`${BASE}/pages/${slug}`, { signal }),
    staleTime: 60_000,
  })
}

export function useSubmitEnquiry() {
  return useMutation({
    mutationFn: (payload) => apiRequest(`${BASE}/enquiries`, { method: 'POST', body: payload }),
  })
}
