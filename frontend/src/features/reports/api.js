import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export function useReportCatalogue() {
  return useQuery({
    queryKey: ['reports', 'catalogue'],
    queryFn: ({ signal }) => apiRequest('/api/v1/reports', { signal }),
  })
}

export function useReport(key, filters) {
  return useQuery({
    queryKey: ['reports', 'run', key, filters],
    queryFn: ({ signal }) => apiRequest(`/api/v1/reports/${key}`, { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useMyRuns() {
  return useQuery({
    queryKey: ['reports', 'runs'],
    queryFn: ({ signal }) => apiRequest('/api/v1/reports/runs', { signal }),
  })
}

export function useRun(id) {
  return useQuery({
    queryKey: ['reports', 'runs', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/reports/runs/${id}`, { signal }),
  })
}

export function useSchedules() {
  return useQuery({
    queryKey: ['reports', 'schedules'],
    queryFn: ({ signal }) => apiRequest('/api/v1/reports/schedules', { signal }),
  })
}

function useScheduleMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reports', 'schedules'] }),
  })
}

export function useCreateSchedule() {
  return useScheduleMutation((body) =>
    apiRequest('/api/v1/reports/schedules', { method: 'POST', body }),
  )
}

export function useScheduleActions() {
  return {
    update: useScheduleMutation(({ id, ...body }) =>
      apiRequest(`/api/v1/reports/schedules/${id}`, { method: 'PATCH', body }),
    ),
    remove: useScheduleMutation((id) =>
      apiRequest(`/api/v1/reports/schedules/${id}`, { method: 'DELETE' }),
    ),
  }
}

export function exportUrl(key, format, filters) {
  const params = new URLSearchParams({ format })
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v)
  return `/api/v1/reports/${key}/export?${params}`
}
