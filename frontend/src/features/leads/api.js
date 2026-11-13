import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const PRIORITIES = ['low', 'medium', 'high']
export const SOURCE_LABELS = {
  website_contact: 'Website contact form',
  website_demo: 'Website demo request',
  manual: 'Added by staff',
}
export const ACTIVITY_TYPES = [
  { value: 'call', label: 'Call' },
  { value: 'email', label: 'Email' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'sms', label: 'SMS' },
  { value: 'note', label: 'Note' },
]

export function stageVariant(stage) {
  if (!stage) return 'default'
  if (stage.is_won) return 'success'
  if (stage.is_lost) return 'destructive'
  return stage.position === 0 ? 'accent' : 'default'
}

export function useStages() {
  return useQuery({
    queryKey: ['crm', 'stages'],
    queryFn: ({ signal }) => apiRequest('/api/v1/crm/stages', { signal }),
    staleTime: 60_000,
  })
}

export function useStageMap() {
  const { data } = useStages()
  return Object.fromEntries((data ?? []).map((s) => [s.key, s]))
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

function useLeadMutation(id, mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: (lead) => {
      if (lead?.id) queryClient.setQueryData(['leads', 'detail', lead.id], lead)
      queryClient.invalidateQueries({ queryKey: ['leads', 'list'] })
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useUpdateLead(id) {
  return useLeadMutation(id, (payload) =>
    apiRequest(`/api/v1/leads/${id}`, { method: 'PATCH', body: payload }),
  )
}

export function useCreateLead() {
  return useLeadMutation(null, (payload) =>
    apiRequest('/api/v1/leads', { method: 'POST', body: payload }),
  )
}

export function useAddLeadActivity(id) {
  return useLeadMutation(id, (payload) =>
    apiRequest(`/api/v1/leads/${id}/activities`, { method: 'POST', body: payload }),
  )
}

export function useConvertLead(id) {
  return useLeadMutation(id, (payload) =>
    apiRequest(`/api/v1/leads/${id}/convert`, { method: 'POST', body: payload }),
  )
}

export function useStageMutations() {
  const queryClient = useQueryClient()
  const done = { onSuccess: () => queryClient.invalidateQueries({ queryKey: ['crm', 'stages'] }) }
  return {
    create: useMutation({
      mutationFn: (payload) => apiRequest('/api/v1/crm/stages', { method: 'POST', body: payload }),
      ...done,
    }),
    update: useMutation({
      mutationFn: ({ id, ...payload }) =>
        apiRequest(`/api/v1/crm/stages/${id}`, { method: 'PATCH', body: payload }),
      ...done,
    }),
    remove: useMutation({
      mutationFn: (id) => apiRequest(`/api/v1/crm/stages/${id}`, { method: 'DELETE' }),
      ...done,
    }),
  }
}
