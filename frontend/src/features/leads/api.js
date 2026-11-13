import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const LEAD_STATUSES = [
  { value: 'new', label: 'New', variant: 'accent' },
  { value: 'contacted', label: 'Contacted', variant: 'default' },
  { value: 'interested', label: 'Interested', variant: 'default' },
  { value: 'demo_scheduled', label: 'Demo scheduled', variant: 'accent' },
  { value: 'negotiation', label: 'Negotiation', variant: 'warning' },
  { value: 'converted', label: 'Converted', variant: 'success' },
  { value: 'lost', label: 'Lost', variant: 'destructive' },
]
export const LEAD_STATUS = Object.fromEntries(LEAD_STATUSES.map((s) => [s.value, s]))
export const PRIORITIES = ['low', 'medium', 'high']
export const SOURCE_LABELS = {
  website_contact: 'Website contact form',
  website_demo: 'Website demo request',
}

export function useLeads(filters) {
  return useQuery({
    queryKey: ['leads', 'list', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/leads', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useLead(id) {
  return useQuery({
    queryKey: ['leads', 'detail', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/leads/${id}`, { signal }),
  })
}

export function useUpdateLead(id) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => apiRequest(`/api/v1/leads/${id}`, { method: 'PATCH', body: payload }),
    onSuccess: (lead) => {
      queryClient.setQueryData(['leads', 'detail', id], lead)
      queryClient.invalidateQueries({ queryKey: ['leads', 'list'] })
    },
  })
}
