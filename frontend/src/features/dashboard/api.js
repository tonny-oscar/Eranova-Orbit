import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ApiError, apiRequest } from '@/lib/api/client'

async function fetchReadiness({ signal }) {
  const checkedAt = new Date().toISOString()
  try {
    const data = await apiRequest('/ready', { signal })
    return { ...data, checkedAt }
  } catch (error) {
    // 503 means the API is up but a dependency is not; report it rather than fail.
    if (error instanceof ApiError && error.status === 503) {
      return { status: 'not_ready', checks: { database: 'unavailable' }, checkedAt }
    }
    throw error
  }
}

export function useReadiness() {
  return useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: fetchReadiness,
    refetchInterval: 60_000,
  })
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: ({ signal }) => apiRequest('/api/v1/dashboard/summary', { signal }),
    refetchInterval: 120_000,
  })
}

export function useGlobalSearch(q) {
  return useQuery({
    queryKey: ['search', q],
    queryFn: ({ signal }) => apiRequest('/api/v1/search', { query: { q }, signal }),
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  })
}
