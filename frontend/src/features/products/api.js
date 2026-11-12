import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { usePermissions } from '@/features/auth/hooks'
import { apiRequest } from '@/lib/api/client'

const BASE = '/api/v1/products'

export const productKeys = {
  all: ['products'],
  list: (filters) => ['products', 'list', filters],
  detail: (id) => ['products', 'detail', id],
  history: (id) => ['products', 'history', id],
  members: (id) => ['products', 'members', id],
}

export function useProducts(filters) {
  return useQuery({
    queryKey: productKeys.list(filters),
    queryFn: ({ signal }) => apiRequest(BASE, { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useProduct(id) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: ({ signal }) => apiRequest(`${BASE}/${id}`, { signal }),
  })
}

export function useProductHistory(id) {
  return useQuery({
    queryKey: productKeys.history(id),
    queryFn: ({ signal }) => apiRequest(`${BASE}/${id}/status-history`, { signal }),
  })
}

export function useProductMembers(id) {
  return useQuery({
    queryKey: productKeys.members(id),
    queryFn: ({ signal }) => apiRequest(`${BASE}/${id}/members`, { signal }),
  })
}

function useProductMutation(mutationFn, invalidate) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (data, variables) => {
      if (data?.id && data?.slug) queryClient.setQueryData(productKeys.detail(data.id), data)
      for (const key of invalidate(data, variables))
        queryClient.invalidateQueries({ queryKey: key })
    },
  })
}

export function useCreateProduct() {
  return useProductMutation(
    (payload) => apiRequest(BASE, { method: 'POST', body: payload }),
    () => [['products', 'list'], ['dashboard']],
  )
}

export function useUpdateProduct(id) {
  return useProductMutation(
    (payload) => apiRequest(`${BASE}/${id}`, { method: 'PATCH', body: payload }),
    () => [['products', 'list']],
  )
}

export function useChangeProductStatus(id) {
  return useProductMutation(
    (payload) => apiRequest(`${BASE}/${id}/status`, { method: 'POST', body: payload }),
    () => [['products', 'list'], productKeys.history(id), ['dashboard']],
  )
}

export function useAddProductMember(id) {
  return useProductMutation(
    (payload) => apiRequest(`${BASE}/${id}/members`, { method: 'POST', body: payload }),
    () => [productKeys.members(id)],
  )
}

export function useRemoveProductMember(id) {
  return useProductMutation(
    (memberId) => apiRequest(`${BASE}/${id}/members/${memberId}`, { method: 'DELETE' }),
    () => [productKeys.members(id)],
  )
}

/** Active users for owner/member pickers; only fetched when the caller may list users. */
export function useUserOptions() {
  const { has } = usePermissions()
  const enabled = has('user.read')
  const query = useQuery({
    queryKey: ['users', 'options'],
    queryFn: ({ signal }) => apiRequest('/api/v1/users', { query: { limit: 100 }, signal }),
    enabled,
    select: (page) => page.items.filter((u) => u.status === 'active'),
  })
  return { ...query, enabled }
}
