import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const TICKET_STATUSES = [
  { value: 'new', label: 'New', variant: 'accent' },
  { value: 'open', label: 'Open', variant: 'accent' },
  { value: 'assigned', label: 'Assigned', variant: 'default' },
  { value: 'in_progress', label: 'In progress', variant: 'warning' },
  { value: 'waiting_customer', label: 'Waiting for customer', variant: 'default' },
  { value: 'resolved', label: 'Resolved', variant: 'success' },
  { value: 'closed', label: 'Closed', variant: 'default' },
]
export const TICKET_STATUS = Object.fromEntries(TICKET_STATUSES.map((s) => [s.value, s]))
export const PRIORITIES = ['low', 'medium', 'high', 'urgent']
export const PRIORITY_VARIANT = {
  low: 'default',
  medium: 'default',
  high: 'warning',
  urgent: 'destructive',
}
export const CATEGORIES = [
  'bug',
  'question',
  'billing',
  'feature_request',
  'account',
  'outage',
  'other',
]
export const CHANNELS = ['email', 'phone', 'whatsapp', 'web', 'in_person', 'product', 'other']
export const label = (value) => value.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())

export function useTickets(filters) {
  return useQuery({
    queryKey: ['support', 'tickets', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/support/tickets', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useTicket(id) {
  return useQuery({
    queryKey: ['support', 'ticket', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/support/tickets/${id}`, { signal }),
  })
}

export function useSupportMetrics(days = 30) {
  return useQuery({
    queryKey: ['support', 'metrics', days],
    queryFn: ({ signal }) => apiRequest('/api/v1/support/metrics', { query: { days }, signal }),
  })
}

function useTicketMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (ticket) => {
      if (ticket?.id) queryClient.setQueryData(['support', 'ticket', ticket.id], ticket)
      queryClient.invalidateQueries({ queryKey: ['support', 'tickets'] })
      queryClient.invalidateQueries({ queryKey: ['support', 'metrics'] })
    },
  })
}

export function useCreateTicket() {
  return useTicketMutation((body) =>
    apiRequest('/api/v1/support/tickets', { method: 'POST', body }),
  )
}

export function useTicketActions(id) {
  const base = `/api/v1/support/tickets/${id}`
  return {
    update: useTicketMutation((body) => apiRequest(base, { method: 'PATCH', body })),
    transition: useTicketMutation((body) =>
      apiRequest(`${base}/transition`, { method: 'POST', body }),
    ),
    message: useTicketMutation((body) => apiRequest(`${base}/messages`, { method: 'POST', body })),
  }
}
