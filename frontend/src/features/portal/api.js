import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export function useMyWork() {
  return useQuery({
    queryKey: ['me', 'work'],
    queryFn: ({ signal }) => apiRequest('/api/v1/me/work', { signal }),
    refetchInterval: 120_000,
  })
}

export function useAttendance(team) {
  return useQuery({
    queryKey: ['attendance', team],
    queryFn: ({ signal }) => apiRequest('/api/v1/attendance', { query: { team }, signal }),
  })
}

function usePortalMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me', 'work'] })
      queryClient.invalidateQueries({ queryKey: ['attendance'] })
    },
  })
}

export const usePortalActions = () => ({
  requestLeave: usePortalMutation((payload) =>
    apiRequest('/api/v1/leave-requests', { method: 'POST', body: payload }),
  ),
  decideLeave: usePortalMutation(({ id, ...payload }) =>
    apiRequest(`/api/v1/leave-requests/${id}/decision`, { method: 'POST', body: payload }),
  ),
  cancelLeave: usePortalMutation((id) =>
    apiRequest(`/api/v1/leave-requests/${id}/cancel`, { method: 'POST' }),
  ),
  checkIn: usePortalMutation((note) =>
    apiRequest('/api/v1/attendance/check-in', { method: 'POST', body: { note } }),
  ),
  checkOut: usePortalMutation(() => apiRequest('/api/v1/attendance/check-out', { method: 'POST' })),
})

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: ({ signal }) => apiRequest('/api/v1/notifications', { query: { limit: 15 }, signal }),
    refetchInterval: 60_000,
  })
}

export function useMarkNotificationsRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id) =>
      apiRequest(id ? `/api/v1/notifications/${id}/read` : '/api/v1/notifications/read-all', {
        method: 'POST',
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}
