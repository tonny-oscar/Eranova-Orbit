import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { usePermissions } from '@/features/auth/hooks'
import { apiRequest } from '@/lib/api/client'

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: ({ signal }) => apiRequest('/api/v1/roles', { signal }),
  })
}

export function useRole(roleId) {
  return useQuery({
    queryKey: ['roles', roleId],
    queryFn: ({ signal }) => apiRequest(`/api/v1/roles/${roleId}`, { signal }),
    enabled: Boolean(roleId),
  })
}

export function usePermissionCatalogue() {
  return useQuery({
    queryKey: ['permissions'],
    queryFn: ({ signal }) => apiRequest('/api/v1/authz/permissions', { signal }),
    staleTime: 5 * 60_000,
  })
}

function useInvalidatingMutation(mutationFn, keys) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => keys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey })),
  })
}

export function useCreateRole() {
  return useInvalidatingMutation(
    (payload) => apiRequest('/api/v1/roles', { method: 'POST', body: payload }),
    [['roles']],
  )
}

export function useUpdateRole(roleId) {
  return useInvalidatingMutation(
    (payload) => apiRequest(`/api/v1/roles/${roleId}`, { method: 'PATCH', body: payload }),
    [['roles'], ['auth', 'me']],
  )
}

export function useDeleteRole(roleId) {
  return useInvalidatingMutation(
    () => apiRequest(`/api/v1/roles/${roleId}`, { method: 'DELETE' }),
    [['roles']],
  )
}

export function useAuditLogs(filters) {
  return useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/audit-logs', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useUsers(filters) {
  return useQuery({
    queryKey: ['users', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/users', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useUser(userId) {
  return useQuery({
    queryKey: ['users', 'detail', userId],
    queryFn: ({ signal }) => apiRequest(`/api/v1/users/${userId}`, { signal }),
  })
}

export function useCreateUser() {
  return useInvalidatingMutation(
    (payload) => apiRequest('/api/v1/users', { method: 'POST', body: payload }),
    [['users'], ['dashboard']],
  )
}

export function useUpdateUser(userId) {
  return useInvalidatingMutation(
    (payload) => apiRequest(`/api/v1/users/${userId}`, { method: 'PATCH', body: payload }),
    [['users']],
  )
}

export function useResetUserPassword(userId) {
  return useMutation({
    mutationFn: () => apiRequest(`/api/v1/users/${userId}/reset-password`, { method: 'POST' }),
  })
}

export function useAssignRole(userId) {
  return useInvalidatingMutation(
    (payload) => apiRequest(`/api/v1/users/${userId}/roles`, { method: 'POST', body: payload }),
    [['users'], ['roles']],
  )
}

export function useRevokeRole(userId) {
  return useInvalidatingMutation(
    (assignmentId) =>
      apiRequest(`/api/v1/users/${userId}/roles/${assignmentId}`, { method: 'DELETE' }),
    [['users'], ['roles']],
  )
}

/** Product choices for product-scoped role assignments. */
export function useProductOptions() {
  const { has } = usePermissions()
  return useQuery({
    queryKey: ['products', 'options'],
    queryFn: ({ signal }) => apiRequest('/api/v1/products', { query: { limit: 100 }, signal }),
    enabled: has('product.read'),
    select: (page) => page.items,
  })
}
