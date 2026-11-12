import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: ({ signal }) => apiRequest('/api/v1/roles', { signal }),
  })
}

export function useAuditLogs(filters) {
  return useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/audit-logs', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}
