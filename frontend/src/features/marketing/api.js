import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '@/lib/api/client'

export const CAMPAIGN_STATUSES = [
  { value: 'planned', label: 'Planned', variant: 'default' },
  { value: 'active', label: 'Active', variant: 'success' },
  { value: 'paused', label: 'Paused', variant: 'warning' },
  { value: 'completed', label: 'Completed', variant: 'accent' },
  { value: 'cancelled', label: 'Cancelled', variant: 'destructive' },
]
export const CONTENT_STATUSES = [
  { value: 'draft', label: 'Draft', variant: 'default' },
  { value: 'in_review', label: 'In review', variant: 'accent' },
  { value: 'approved', label: 'Approved', variant: 'accent' },
  { value: 'scheduled', label: 'Scheduled', variant: 'warning' },
  { value: 'published', label: 'Published', variant: 'success' },
  { value: 'failed', label: 'Failed', variant: 'destructive' },
]
export const CONTENT_KINDS = [
  { value: 'social_caption', label: 'Social caption' },
  { value: 'email', label: 'Email' },
  { value: 'product_description', label: 'Product description' },
  { value: 'blog', label: 'Blog post' },
  { value: 'sales_script', label: 'Sales script' },
  { value: 'campaign_plan', label: 'Campaign plan' },
  { value: 'announcement', label: 'Launch announcement' },
]
export const CHANNELS = [
  'facebook',
  'instagram',
  'linkedin',
  'x',
  'tiktok',
  'whatsapp',
  'email',
  'website',
  'blog',
  'sms',
  'events',
  'other',
]
const byValue = (list) => Object.fromEntries(list.map((s) => [s.value, s]))
export const CAMPAIGN_STATUS = byValue(CAMPAIGN_STATUSES)
export const CONTENT_STATUS = byValue(CONTENT_STATUSES)
export const CONTENT_KIND = byValue(CONTENT_KINDS)

export const ACTION_LABELS = {
  submit: 'Submit for review',
  approve: 'Approve',
  request_changes: 'Request changes',
  schedule: 'Schedule',
  unschedule: 'Unschedule',
  record_published: 'Record publication',
  record_failed: 'Mark as failed',
  reopen: 'Reopen as draft',
}

export function useCampaigns(filters) {
  return useQuery({
    queryKey: ['marketing', 'campaigns', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/marketing/campaigns', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useCampaign(id) {
  return useQuery({
    queryKey: ['marketing', 'campaign', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/marketing/campaigns/${id}`, { signal }),
  })
}

export function useContentList(filters) {
  return useQuery({
    queryKey: ['marketing', 'content', filters],
    queryFn: ({ signal }) => apiRequest('/api/v1/marketing/content', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useContent(id) {
  return useQuery({
    queryKey: ['marketing', 'content-item', id],
    queryFn: ({ signal }) => apiRequest(`/api/v1/marketing/content/${id}`, { signal }),
  })
}

export function useCalendar(start, end) {
  return useQuery({
    queryKey: ['marketing', 'calendar', start, end],
    queryFn: ({ signal }) =>
      apiRequest('/api/v1/marketing/calendar', { query: { start, end }, signal }),
  })
}

function useMarketingMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['marketing'] }),
  })
}

export function useCreateCampaign() {
  return useMarketingMutation((body) =>
    apiRequest('/api/v1/marketing/campaigns', { method: 'POST', body }),
  )
}

export function useCampaignActions(id) {
  const base = `/api/v1/marketing/campaigns/${id}`
  return {
    update: useMarketingMutation((body) => apiRequest(base, { method: 'PATCH', body })),
    remove: useMarketingMutation(() => apiRequest(base, { method: 'DELETE' })),
    addMetric: useMarketingMutation((body) =>
      apiRequest(`${base}/metrics`, { method: 'POST', body }),
    ),
    removeMetric: useMarketingMutation((metricId) =>
      apiRequest(`${base}/metrics/${metricId}`, { method: 'DELETE' }),
    ),
  }
}

export function useCreateContent() {
  return useMarketingMutation((body) =>
    apiRequest('/api/v1/marketing/content', { method: 'POST', body }),
  )
}

export function useContentActions(id) {
  const base = `/api/v1/marketing/content/${id}`
  return {
    update: useMarketingMutation((body) => apiRequest(base, { method: 'PATCH', body })),
    act: useMarketingMutation((body) => apiRequest(`${base}/actions`, { method: 'POST', body })),
    remove: useMarketingMutation(() => apiRequest(base, { method: 'DELETE' })),
  }
}
