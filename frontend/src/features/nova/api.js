import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const STATUS_LABELS = {
  succeeded: { label: 'Done', variant: 'success' },
  pending_approval: { label: 'Waiting for approval', variant: 'warning' },
  denied: { label: 'Not allowed', variant: 'destructive' },
  failed: { label: 'Failed', variant: 'destructive' },
  invalid: { label: 'Rejected', variant: 'destructive' },
}

export const APPROVAL_STATUS = {
  pending: { label: 'Pending', variant: 'warning' },
  approved: { label: 'Approved', variant: 'accent' },
  executed: { label: 'Done', variant: 'success' },
  rejected: { label: 'Rejected', variant: 'default' },
  expired: { label: 'Expired', variant: 'default' },
  failed: { label: 'Failed', variant: 'destructive' },
}

export function useNovaStatus() {
  return useQuery({
    queryKey: ['nova', 'status'],
    queryFn: ({ signal }) => apiRequest('/api/v1/nova/status', { signal }),
    staleTime: 60_000,
  })
}

export function useConversations() {
  return useQuery({
    queryKey: ['nova', 'conversations'],
    queryFn: ({ signal }) => apiRequest('/api/v1/nova/conversations', { signal }),
  })
}

export function useConversation(id) {
  return useQuery({
    queryKey: ['nova', 'conversation', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/nova/conversations/${id}`, { signal }),
    enabled: Boolean(id),
  })
}

export function useApprovals(status) {
  return useQuery({
    queryKey: ['nova', 'approvals', status ?? 'all'],
    queryFn: ({ signal }) => apiRequest('/api/v1/nova/approvals', { query: { status }, signal }),
  })
}

export function useNovaUsage() {
  return useQuery({
    queryKey: ['nova', 'usage'],
    queryFn: ({ signal }) => apiRequest('/api/v1/nova/usage', { signal }),
  })
}

export function useCreateConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiRequest('/api/v1/nova/conversations', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nova', 'conversations'] }),
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id) => apiRequest(`/api/v1/nova/conversations/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nova', 'conversations'] }),
  })
}

export function useSendMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ conversationId, ...body }) =>
      apiRequest(`/api/v1/nova/conversations/${conversationId}/messages`, {
        method: 'POST',
        body,
      }),
    onSettled: (_data, _error, { conversationId }) => {
      queryClient.invalidateQueries({ queryKey: ['nova', 'conversation', conversationId] })
      queryClient.invalidateQueries({ queryKey: ['nova', 'conversations'] })
      queryClient.invalidateQueries({ queryKey: ['nova', 'approvals'] })
      queryClient.invalidateQueries({ queryKey: ['nova', 'usage'] })
    },
  })
}

export function useDecideApproval() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, approve, note }) =>
      apiRequest(`/api/v1/nova/approvals/${id}/decision`, {
        method: 'POST',
        body: { approve, note: note || null },
      }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['nova'] }),
  })
}
