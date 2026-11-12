import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { usePermissions } from '@/features/auth/hooks'
import { apiRequest } from '@/lib/api/client'

export const EMPLOYMENT_TYPES = [
  { value: 'full_time', label: 'Full-time' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'intern', label: 'Intern' },
]

export function useEmployees(filters) {
  return useQuery({
    queryKey: ['employees', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/employees', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useEmployee(userId) {
  return useQuery({
    queryKey: ['employees', 'detail', userId],
    queryFn: ({ signal }) => apiRequest(`/api/v1/employees/${userId}`, { signal }),
  })
}

export function useDepartments() {
  const { has } = usePermissions()
  return useQuery({
    queryKey: ['departments'],
    queryFn: ({ signal }) => apiRequest('/api/v1/departments', { signal }),
    enabled: has('employee.read'),
  })
}

function useInvalidating(mutationFn, keys) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => keys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey })),
  })
}

export function useUpdateEmployee(userId) {
  return useInvalidating(
    (payload) => apiRequest(`/api/v1/employees/${userId}`, { method: 'PUT', body: payload }),
    [['employees'], ['departments'], ['users']],
  )
}

export function useCreateDepartment() {
  return useInvalidating(
    (payload) => apiRequest('/api/v1/departments', { method: 'POST', body: payload }),
    [['departments']],
  )
}

export function useUpdateDepartment() {
  return useInvalidating(
    ({ id, ...payload }) =>
      apiRequest(`/api/v1/departments/${id}`, { method: 'PATCH', body: payload }),
    [['departments'], ['employees']],
  )
}
